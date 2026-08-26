"""Build the explicit FASTA reference context and verified sequence bindings."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from refcompat._compat import assert_never
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityValue,
    SequenceLengthCapability,
    SequenceOrderCapability,
    SequencePresenceCapability,
)
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.identity import (
    Md5Digest,
    RefgetSequenceId,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import (
    ReferenceContext,
    SequenceBinding,
    SequenceBindingId,
    SequenceBindingMethod,
)
from refcompat.model.resources import ResourceId


def build_reference_context(
    request: EvaluationRequest,
    anchor_snapshot: SequenceCollectionSnapshot,
) -> ReferenceContext:
    """Project the complete FASTA anchor snapshot into explicit request scope."""

    if anchor_snapshot.resource_id != request.anchor_resource_id:
        raise ValueError("anchor snapshot must belong to the evaluation FASTA anchor")

    names = tuple(sequence.local_name for sequence in anchor_snapshot.sequences)
    if not names:
        raise ValueError("FASTA anchor snapshot must contain at least one sequence")
    if len(set(names)) != len(names):
        raise ValueError("FASTA anchor snapshot sequence names must be unique")

    selected_names = request.scope.anchor_sequence_names
    if selected_names is None:
        sequences = anchor_snapshot.sequences
    else:
        selected = set(selected_names)
        if selected - set(names):
            raise ValueError("explicit anchor sequence scope references names absent from FASTA")
        sequences = tuple(
            sequence for sequence in anchor_snapshot.sequences if sequence.local_name in selected
        )

    return ReferenceContext(
        anchor_resource_id=request.anchor_resource_id,
        scope=request.scope,
        anchor_snapshot=anchor_snapshot,
        sequences=sequences,
        anchor_capabilities=_anchor_capabilities(request.anchor_resource_id, sequences),
    )


def derive_sequence_bindings(
    context: ReferenceContext,
    contracts: tuple[ResourceContract, ...],
) -> tuple[SequenceBinding, ...]:
    """Derive unique local-name bindings from shared comparable content identity.

    Peer resources never vote on the anchor. Resource-local identity evidence
    may be content-derived or an explicitly marked metadata declaration, but the
    anchor side is always reconstructed from content-derived FASTA identities. A
    binding exists only when the local identity resolves to exactly one sequence
    in the complete FASTA anchor snapshot and that target is inside the selected
    evaluation scope. Anchor-sequence scope may hide usable targets, but it must
    never manufacture uniqueness by hiding an otherwise ambiguous duplicate.
    Conflicting local identities remain unbound.
    """

    contracts_by_id = _contracts_by_id(context, contracts)
    anchor_identities = tuple(
        capability
        for sequence in context.anchor_snapshot.sequences
        for capability in _identity_capabilities_for_sequence(
            context.anchor_resource_id,
            sequence,
        )
    )
    scoped_anchor_names = {sequence.local_name for sequence in context.sequences}
    anchor_by_name = _group_by_name(anchor_identities)
    if any(_has_scheme_conflict(values) for values in anchor_by_name.values()):
        raise ValueError("anchor identity capabilities conflict for one local sequence")

    identity_index: dict[tuple[str, SequenceIdentityValue], list[SequenceIdentityCapability]] = (
        defaultdict(list)
    )
    for capability in anchor_identities:
        identity_index[(_identity_scheme(capability.identity), capability.identity)].append(
            capability
        )

    bindings: list[SequenceBinding] = []
    for resource_id in context.scope.resource_ids:
        if resource_id == context.anchor_resource_id:
            continue

        local_identities = tuple(
            capability
            for capability in contracts_by_id[resource_id].capabilities
            if isinstance(capability, SequenceIdentityCapability)
        )
        grouped_local = _group_by_name(local_identities)
        for local_name in sorted(grouped_local):
            capabilities = grouped_local[local_name]
            if _has_scheme_conflict(capabilities):
                continue

            targets: dict[
                str,
                list[tuple[SequenceIdentityCapability, SequenceIdentityCapability]],
            ] = defaultdict(list)
            for local_capability in capabilities:
                matches = identity_index.get(
                    (_identity_scheme(local_capability.identity), local_capability.identity),
                    [],
                )
                for anchor_capability in matches:
                    targets[anchor_capability.sequence_name].append(
                        (local_capability, anchor_capability)
                    )

            if len(targets) != 1:
                continue
            anchor_name, matched_pairs = next(iter(targets.items()))
            if anchor_name not in scoped_anchor_names:
                continue
            if _contradicts_target(capabilities, anchor_by_name[anchor_name]):
                continue

            identities = tuple(
                sorted(
                    {local.identity for local, _anchor in matched_pairs},
                    key=_identity_token,
                )
            )
            capability_ids = tuple(
                sorted(
                    {
                        capability_id
                        for local, anchor in matched_pairs
                        for capability_id in (local.id, anchor.id)
                    },
                    key=str,
                )
            )
            bindings.append(
                SequenceBinding(
                    id=_make_binding_id(
                        resource_id,
                        local_name,
                        context.anchor_resource_id,
                        anchor_name,
                        identities,
                    ),
                    resource_id=resource_id,
                    local_sequence_name=local_name,
                    anchor_resource_id=context.anchor_resource_id,
                    anchor_sequence_name=anchor_name,
                    method=SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
                    identity_values=identities,
                    capability_ids=capability_ids,
                )
            )

    return tuple(bindings)


def _anchor_capabilities(
    resource_id: ResourceId,
    sequences: tuple[SnapshotSequence, ...],
) -> tuple[Capability, ...]:
    capabilities: list[Capability] = []
    for sequence in sequences:
        capabilities.append(
            SequencePresenceCapability(
                id=_make_capability_id(resource_id, "presence", sequence.local_name, "true"),
                resource_id=resource_id,
                sequence_name=sequence.local_name,
                present=True,
            )
        )
        if sequence.length is not None:
            capabilities.append(
                SequenceLengthCapability(
                    id=_make_capability_id(
                        resource_id,
                        "length",
                        sequence.local_name,
                        str(sequence.length),
                    ),
                    resource_id=resource_id,
                    sequence_name=sequence.local_name,
                    length=sequence.length,
                )
            )
        capabilities.extend(_identity_capabilities_for_sequence(resource_id, sequence))

    order_names = tuple(sequence.local_name for sequence in sequences)
    capabilities.append(
        SequenceOrderCapability(
            id=_make_capability_id(
                resource_id,
                "order",
                "<collection>",
                json.dumps(order_names, ensure_ascii=True, separators=(",", ":")),
            ),
            resource_id=resource_id,
            sequence_names=order_names,
        )
    )
    return tuple(capabilities)


def _identity_capabilities_for_sequence(
    resource_id: ResourceId,
    sequence: SnapshotSequence,
) -> tuple[SequenceIdentityCapability, ...]:
    capabilities: list[SequenceIdentityCapability] = []
    for identity in (sequence.refget_id, sequence.md5):
        if identity is None:
            continue
        capabilities.append(
            SequenceIdentityCapability(
                id=_make_capability_id(
                    resource_id,
                    "identity",
                    sequence.local_name,
                    _identity_token(identity),
                ),
                resource_id=resource_id,
                sequence_name=sequence.local_name,
                identity=identity,
                provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
            )
        )
    return tuple(capabilities)


def _contracts_by_id(
    context: ReferenceContext,
    contracts: tuple[ResourceContract, ...],
) -> dict[ResourceId, ResourceContract]:
    resource_ids = tuple(contract.resource_id for contract in contracts)
    if len(set(resource_ids)) != len(resource_ids):
        raise ValueError("sequence-binding contracts must have unique resource IDs")
    if set(resource_ids) != set(context.scope.resource_ids):
        raise ValueError("sequence binding requires exactly one contract per scoped resource")
    return {contract.resource_id: contract for contract in contracts}


def _group_by_name(
    capabilities: tuple[SequenceIdentityCapability, ...],
) -> dict[str, tuple[SequenceIdentityCapability, ...]]:
    grouped: dict[str, list[SequenceIdentityCapability]] = defaultdict(list)
    for capability in capabilities:
        grouped[capability.sequence_name].append(capability)
    return {name: tuple(values) for name, values in grouped.items()}


def _has_scheme_conflict(capabilities: tuple[SequenceIdentityCapability, ...]) -> bool:
    by_scheme: dict[str, set[SequenceIdentityValue]] = defaultdict(set)
    for capability in capabilities:
        by_scheme[_identity_scheme(capability.identity)].add(capability.identity)
    return any(len(values) > 1 for values in by_scheme.values())


def _contradicts_target(
    local: tuple[SequenceIdentityCapability, ...],
    anchor: tuple[SequenceIdentityCapability, ...],
) -> bool:
    anchor_by_scheme: dict[str, set[SequenceIdentityValue]] = defaultdict(set)
    for capability in anchor:
        anchor_by_scheme[_identity_scheme(capability.identity)].add(capability.identity)
    return any(
        _identity_scheme(capability.identity) in anchor_by_scheme
        and capability.identity not in anchor_by_scheme[_identity_scheme(capability.identity)]
        for capability in local
    )


def _identity_scheme(identity: SequenceIdentityValue) -> str:
    if isinstance(identity, RefgetSequenceId):
        return "refget"
    if isinstance(identity, Md5Digest):
        return "md5"
    assert_never(identity)


def _identity_token(identity: SequenceIdentityValue) -> str:
    return f"{_identity_scheme(identity)}:{identity.value}"


def _digest(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _make_capability_id(
    resource_id: ResourceId,
    kind: str,
    sequence_name: str,
    value: str,
) -> CapabilityId:
    return CapabilityId(
        "anchor-capability:" + _digest([str(resource_id), kind, sequence_name, value])
    )


def _make_binding_id(
    resource_id: ResourceId,
    local_name: str,
    anchor_resource_id: ResourceId,
    anchor_name: str,
    identities: tuple[SequenceIdentityValue, ...],
) -> SequenceBindingId:
    return SequenceBindingId(
        "sequence-binding:"
        + _digest(
            [
                str(resource_id),
                local_name,
                str(anchor_resource_id),
                anchor_name,
                *sorted(_identity_token(identity) for identity in identities),
            ]
        )
    )
