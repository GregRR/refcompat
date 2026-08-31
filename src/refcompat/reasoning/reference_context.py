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
    AnchorIdentityResolution,
    AnchorIdentityResolutionState,
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


def resolve_anchor_sequence_identity(
    context: ReferenceContext,
    identities: tuple[SequenceIdentityValue, ...],
) -> AnchorIdentityResolution:
    """Resolve content identity against the complete FASTA anchor conservatively.

    A match requires at least one identity scheme that covers every sequence in
    the complete FASTA snapshot, one unique full-anchor target, agreement from
    every other known identity match, and a target that remains inside explicit
    evaluation scope. Exhaustive absence likewise requires at least one complete
    identity scheme and no positive match from any supplied identity.
    """

    if not identities:
        raise ValueError("anchor identity resolution requires at least one identity")
    if len(set(identities)) != len(identities):
        raise ValueError("anchor identity resolution identities must be unique")

    identities_by_scheme: dict[str, set[SequenceIdentityValue]] = defaultdict(set)
    for identity in identities:
        identities_by_scheme[_identity_scheme(identity)].add(identity)
    if any(len(values) > 1 for values in identities_by_scheme.values()):
        return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)

    anchor_by_name, identity_index, complete_identity_schemes = _anchor_identity_search(context)
    scoped_anchor_names = {sequence.local_name for sequence in context.sequences}

    complete_matches: dict[str, set[SequenceIdentityValue]] = defaultdict(set)
    for identity in identities:
        scheme = _identity_scheme(identity)
        if scheme not in complete_identity_schemes:
            continue
        for anchor_capability in identity_index.get((scheme, identity), ()):
            complete_matches[anchor_capability.sequence_name].add(identity)

    if len(complete_matches) == 1:
        anchor_name, supporting_set = next(iter(complete_matches.items()))
        if _identity_values_match_outside_target(identities, identity_index, anchor_name):
            return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)
        if _identity_values_contradict_target(identities, anchor_by_name[anchor_name]):
            return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)
        if anchor_name not in scoped_anchor_names:
            return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)

        supporting = tuple(sorted(supporting_set, key=_identity_token))
        anchor_capability_ids = tuple(
            sorted(
                {
                    capability.id
                    for capability in anchor_by_name[anchor_name]
                    if capability.identity in supporting_set
                },
                key=str,
            )
        )
        return AnchorIdentityResolution(
            AnchorIdentityResolutionState.MATCHED,
            anchor_sequence_name=anchor_name,
            supporting_identity_values=supporting,
            anchor_capability_ids=anchor_capability_ids,
        )

    if complete_matches:
        return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)

    if any(
        identity_index.get((_identity_scheme(identity), identity), ()) for identity in identities
    ):
        return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)

    absence_identities = tuple(
        sorted(
            (
                identity
                for identity in identities
                if _identity_scheme(identity) in complete_identity_schemes
            ),
            key=_identity_token,
        )
    )
    if absence_identities:
        return AnchorIdentityResolution(
            AnchorIdentityResolutionState.PROVEN_ABSENT,
            supporting_identity_values=absence_identities,
        )

    return AnchorIdentityResolution(AnchorIdentityResolutionState.UNRESOLVED)


def identity_evidence_is_consistent_with_anchor_target(
    context: ReferenceContext,
    capabilities: tuple[SequenceIdentityCapability, ...],
    anchor_sequence_name: str,
) -> bool:
    """Whether peer identity evidence permits a separate naming-only target.

    This helper does not establish a sequence binding. It only prevents an
    independently supplied naming relationship from overriding stronger
    identity evidence. Conflicting same-scheme values, a known positive match
    to another sequence anywhere in the complete anchor, or a directly
    comparable mismatch against the proposed target all fail closed. Identity
    evidence that is merely unavailable or incomparable does not block a
    separately justified naming relationship.
    """

    if not anchor_sequence_name:
        raise ValueError("anchor target name must not be empty")
    if not capabilities:
        return True
    if _has_scheme_conflict(capabilities):
        return False

    anchor_by_name, identity_index, _complete_identity_schemes = _anchor_identity_search(context)
    target_identities = anchor_by_name.get(anchor_sequence_name)
    if target_identities is None:
        raise ValueError("anchor target must expose content identity in the complete FASTA")

    identities = tuple(
        sorted({capability.identity for capability in capabilities}, key=_identity_token)
    )
    if _identity_values_match_outside_target(identities, identity_index, anchor_sequence_name):
        return False
    return not _identity_values_contradict_target(identities, target_identities)


def derive_sequence_bindings(
    context: ReferenceContext,
    contracts: tuple[ResourceContract, ...],
) -> tuple[SequenceBinding, ...]:
    """Derive unique local-name bindings from shared comparable content identity.

    Peer resources never vote on the anchor. Resource-local identity evidence
    may be content-derived or an explicitly marked metadata declaration, but the
    anchor side is always reconstructed from content-derived FASTA identities. A
    binding exists only when the local identity resolves through
    :func:`resolve_anchor_sequence_identity`; explicit scope therefore cannot
    manufacture uniqueness or hide a positive match to another target.
    """

    contracts_by_id = _contracts_by_id(context, contracts)

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

            identities = tuple(
                sorted({capability.identity for capability in capabilities}, key=_identity_token)
            )
            resolution = resolve_anchor_sequence_identity(context, identities)
            if resolution.state is not AnchorIdentityResolutionState.MATCHED:
                continue
            assert resolution.anchor_sequence_name is not None

            supporting = set(resolution.supporting_identity_values)
            capability_ids = tuple(
                sorted(
                    {
                        *resolution.anchor_capability_ids,
                        *(
                            capability.id
                            for capability in capabilities
                            if capability.identity in supporting
                        ),
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
                        resolution.anchor_sequence_name,
                        resolution.supporting_identity_values,
                    ),
                    resource_id=resource_id,
                    local_sequence_name=local_name,
                    anchor_resource_id=context.anchor_resource_id,
                    anchor_sequence_name=resolution.anchor_sequence_name,
                    method=SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
                    identity_values=resolution.supporting_identity_values,
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


def _identity_values_match_outside_target(
    identities: tuple[SequenceIdentityValue, ...],
    identity_index: dict[tuple[str, SequenceIdentityValue], tuple[SequenceIdentityCapability, ...]],
    target_name: str,
) -> bool:
    return any(
        anchor.sequence_name != target_name
        for identity in identities
        for anchor in identity_index.get((_identity_scheme(identity), identity), ())
    )


def _identity_values_contradict_target(
    identities: tuple[SequenceIdentityValue, ...],
    anchor: tuple[SequenceIdentityCapability, ...],
) -> bool:
    anchor_by_scheme: dict[str, set[SequenceIdentityValue]] = defaultdict(set)
    for capability in anchor:
        anchor_by_scheme[_identity_scheme(capability.identity)].add(capability.identity)
    return any(
        _identity_scheme(identity) in anchor_by_scheme
        and identity not in anchor_by_scheme[_identity_scheme(identity)]
        for identity in identities
    )


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
