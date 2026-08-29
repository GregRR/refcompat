"""Build the explicit FASTA reference context and verified sequence bindings."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from refcompat._compat import assert_never
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    RequirementLevel,
    ResourceContract,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequenceIdentityValue,
    SequenceLengthCapability,
    SequenceOrderCapability,
    SequencePresenceCapability,
    SequencePresenceRequirement,
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
    binding exists only when the local identity scheme is available for every
    sequence in the complete FASTA anchor snapshot, the identity resolves to
    exactly one sequence there, and every other known local identity match agrees
    on that target. The target must also be inside the selected evaluation scope.
    Anchor-sequence scope may hide usable targets, but it must never manufacture
    uniqueness by hiding an otherwise ambiguous or unobserved duplicate.
    Conflicting local identities remain unbound.
    """

    contracts_by_id = _contracts_by_id(context, contracts)
    anchor_by_name, identity_index, complete_identity_schemes = _anchor_identity_search(context)
    scoped_anchor_names = {sequence.local_name for sequence in context.sequences}

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
                scheme = _identity_scheme(local_capability.identity)
                if scheme not in complete_identity_schemes:
                    continue
                matches = identity_index.get(
                    (scheme, local_capability.identity),
                    (),
                )
                for anchor_capability in matches:
                    targets[anchor_capability.sequence_name].append(
                        (local_capability, anchor_capability)
                    )

            if len(targets) != 1:
                continue
            anchor_name, matched_pairs = next(iter(targets.items()))
            if _has_identity_match_outside_target(
                capabilities,
                identity_index,
                anchor_name,
            ):
                continue
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


def derive_sequence_identity_absences(
    context: ReferenceContext,
    contracts: tuple[ResourceContract, ...],
) -> tuple[SequenceIdentityAbsenceCapability, ...]:
    """Prove required peer sequence content absent from the complete FASTA anchor.

    Absence is derived only from peer-owned ``CONTENT_DERIVED`` identity. At
    least one such identity scheme must cover every sequence in the complete
    anchor, and none of the peer's content-derived identities may match any
    anchor sequence. Full-anchor search happens before explicit anchor-sequence
    scope is applied, so scope cannot manufacture absence.
    """

    contracts_by_id = _contracts_by_id(context, contracts)
    _anchor_by_name, identity_index, complete_identity_schemes = _anchor_identity_search(context)

    absences: list[SequenceIdentityAbsenceCapability] = []
    for resource_id in context.scope.resource_ids:
        if resource_id == context.anchor_resource_id:
            continue

        contract = contracts_by_id[resource_id]
        required_names = {
            requirement.sequence_name
            for requirement in contract.requirements
            if isinstance(requirement, SequencePresenceRequirement)
        }
        local_identities = tuple(
            capability
            for capability in contract.capabilities
            if isinstance(capability, SequenceIdentityCapability)
            and capability.provenance is SequenceIdentityProvenance.CONTENT_DERIVED
            and capability.sequence_name in required_names
        )
        grouped_local = _group_by_name(local_identities)
        for local_name in sorted(grouped_local):
            capabilities = grouped_local[local_name]
            if _has_scheme_conflict(capabilities):
                continue

            eligible = tuple(
                capability
                for capability in capabilities
                if _identity_scheme(capability.identity) in complete_identity_schemes
            )
            if not eligible:
                continue
            if any(
                identity_index.get(
                    (_identity_scheme(capability.identity), capability.identity),
                    (),
                )
                for capability in capabilities
            ):
                continue
            if _has_redundant_direct_identity_conflict(
                context,
                contract,
                local_name,
                eligible,
            ):
                continue

            identities = tuple(
                sorted(
                    {capability.identity for capability in eligible},
                    key=_identity_token,
                )
            )
            source_capability_ids = tuple(
                sorted({capability.id for capability in eligible}, key=str)
            )
            source_observation_ids = tuple(
                sorted(
                    {
                        observation_id
                        for capability in eligible
                        for observation_id in capability.source_observation_ids
                    },
                    key=str,
                )
            )
            absences.append(
                SequenceIdentityAbsenceCapability(
                    id=_make_absence_capability_id(
                        context.anchor_resource_id,
                        resource_id,
                        local_name,
                        identities,
                        source_capability_ids,
                    ),
                    resource_id=context.anchor_resource_id,
                    subject_resource_id=resource_id,
                    sequence_name=local_name,
                    identity_values=identities,
                    source_identity_capability_ids=source_capability_ids,
                    source_observation_ids=source_observation_ids,
                )
            )

    return tuple(absences)


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


def _anchor_identity_search(
    context: ReferenceContext,
) -> tuple[
    dict[str, tuple[SequenceIdentityCapability, ...]],
    dict[tuple[str, SequenceIdentityValue], tuple[SequenceIdentityCapability, ...]],
    set[str],
]:
    anchor_identities = tuple(
        capability
        for sequence in context.anchor_snapshot.sequences
        for capability in _identity_capabilities_for_sequence(
            context.anchor_resource_id,
            sequence,
        )
    )
    anchor_by_name = _group_by_name(anchor_identities)
    if any(_has_scheme_conflict(values) for values in anchor_by_name.values()):
        raise ValueError("anchor identity capabilities conflict for one local sequence")

    anchor_names = {sequence.local_name for sequence in context.anchor_snapshot.sequences}
    anchor_names_by_scheme: dict[str, set[str]] = defaultdict(set)
    index_lists: dict[tuple[str, SequenceIdentityValue], list[SequenceIdentityCapability]] = (
        defaultdict(list)
    )
    for capability in anchor_identities:
        scheme = _identity_scheme(capability.identity)
        anchor_names_by_scheme[scheme].add(capability.sequence_name)
        index_lists[(scheme, capability.identity)].append(capability)
    complete_identity_schemes = {
        scheme for scheme, names in anchor_names_by_scheme.items() if names == anchor_names
    }
    identity_index = {key: tuple(values) for key, values in index_lists.items()}
    return anchor_by_name, identity_index, complete_identity_schemes


def _has_redundant_direct_identity_conflict(
    context: ReferenceContext,
    contract: ResourceContract,
    local_name: str,
    source_capabilities: tuple[SequenceIdentityCapability, ...],
) -> bool:
    """Whether a mandatory exact-name identity constraint already proves the conflict."""

    anchor_identities = tuple(
        capability
        for capability in context.anchor_capabilities
        if isinstance(capability, SequenceIdentityCapability)
        and capability.sequence_name == local_name
    )
    if not anchor_identities:
        return False

    mandatory_identities = {
        requirement.identity
        for requirement in contract.requirements
        if isinstance(requirement, SequenceIdentityRequirement)
        and requirement.level is RequirementLevel.MANDATORY
        and requirement.sequence_name == local_name
    }
    return any(
        capability.identity in mandatory_identities
        and any(
            _identity_scheme(anchor.identity) == _identity_scheme(capability.identity)
            for anchor in anchor_identities
        )
        for capability in source_capabilities
    )


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


def _has_identity_match_outside_target(
    local: tuple[SequenceIdentityCapability, ...],
    identity_index: dict[tuple[str, SequenceIdentityValue], tuple[SequenceIdentityCapability, ...]],
    target_name: str,
) -> bool:
    return any(
        anchor.sequence_name != target_name
        for capability in local
        for anchor in identity_index.get(
            (_identity_scheme(capability.identity), capability.identity),
            (),
        )
    )


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


def _make_absence_capability_id(
    anchor_resource_id: ResourceId,
    subject_resource_id: ResourceId,
    local_name: str,
    identities: tuple[SequenceIdentityValue, ...],
    source_capability_ids: tuple[CapabilityId, ...],
) -> CapabilityId:
    return CapabilityId(
        "sequence-identity-absence:"
        + _digest(
            [
                str(anchor_resource_id),
                str(subject_resource_id),
                local_name,
                *sorted(_identity_token(identity) for identity in identities),
                *sorted(str(capability_id) for capability_id in source_capability_ids),
            ]
        )
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
