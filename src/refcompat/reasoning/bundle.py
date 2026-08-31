"""Anchor-driven orchestration across all scoped resource contracts."""

from __future__ import annotations

import hashlib
import json

from refcompat._compat import assert_never
from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.constraints import ConstraintId, capability_is_comparable
from refcompat.model.contracts import (
    Capability,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    ResourceContract,
    SequenceBindingRequirement,
    SequenceBindingValidationCapability,
    SequenceBindingValidationState,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
    SupplementalCapability,
)
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.identity import SequenceCollectionSnapshot
from refcompat.model.reference_context import (
    AnchorIdentityResolutionState,
    ReferenceContext,
    SequenceBinding,
    SequenceBindingMethod,
)
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence
from refcompat.reasoning.interpretation import interpret_constraint_results
from refcompat.reasoning.reference_context import (
    build_reference_context,
    derive_sequence_bindings,
    derive_sequence_identity_absences,
    resolve_anchor_sequence_identity,
)


def reason_bundle(
    request: EvaluationRequest,
    anchor_snapshot: SequenceCollectionSnapshot,
    contracts: tuple[ResourceContract, ...],
    *,
    supplemental_capabilities: tuple[SupplementalCapability, ...] = (),
    supplemental_sequence_bindings: tuple[SequenceBinding, ...] = (),
) -> BundleReasoningResult:
    """Evaluate every scoped typed requirement against the explicit FASTA anchor.

    Peer-resource identity capabilities may establish evidence-backed sequence
    bindings or, when content identity is exhaustive over the complete anchor,
    reasoner-derived sequence absence. Caller-supplied pair validations may enter
    only through the explicit anchor-owned supplemental channel. None of these
    paths lets a peer outvote or replace the selected anchor.
    """

    ordered_contracts = _ordered_contracts(request, contracts)
    context = build_reference_context(request, anchor_snapshot)
    derived_bindings = derive_sequence_bindings(context, ordered_contracts)
    bindings = _merge_sequence_bindings(
        context,
        derived_bindings,
        supplemental_sequence_bindings,
    )
    _validate_supplemental_capabilities(
        request,
        ordered_contracts,
        supplemental_capabilities,
        bindings,
        supplemental_sequence_bindings,
    )
    derived_capabilities = derive_sequence_identity_absences(context, ordered_contracts)

    constraints = []
    for contract in ordered_contracts:
        for requirement in contract.requirements:
            relevant_bindings = _bindings_for_requirement(requirement, bindings)
            candidates = _candidates_for_requirement(
                context,
                requirement,
                relevant_bindings,
                derived_capabilities,
                supplemental_capabilities,
            )
            constraints.append(
                build_constraint(
                    _make_constraint_id(
                        request.anchor_resource_id,
                        requirement,
                        candidates,
                        relevant_bindings,
                    ),
                    requirement,
                    candidates,
                    relevant_bindings,
                )
            )

    constraint_tuple = tuple(constraints)
    evaluations = tuple(evaluate_constraint(constraint) for constraint in constraint_tuple)
    evidence = aggregate_constraint_evidence(constraint_tuple, evaluations)
    interpretation = interpret_constraint_results(
        request,
        constraint_tuple,
        evaluations,
        evidence,
    )
    return BundleReasoningResult(
        request=request,
        contracts=ordered_contracts,
        reference_context=context,
        sequence_bindings=bindings,
        constraints=constraint_tuple,
        evaluations=evaluations,
        evidence=evidence,
        interpretation=interpretation,
        derived_capabilities=derived_capabilities,
        supplemental_capabilities=supplemental_capabilities,
    )


def _bindings_for_requirement(
    requirement: Requirement,
    bindings: tuple[SequenceBinding, ...],
) -> tuple[SequenceBinding, ...]:
    all_resource_bindings = tuple(
        binding for binding in bindings if binding.resource_id == requirement.resource_id
    )
    if isinstance(requirement, SequenceBindingRequirement):
        return tuple(
            binding
            for binding in all_resource_bindings
            if binding.local_sequence_name == requirement.sequence_name
        )

    resource_bindings = tuple(
        binding
        for binding in all_resource_bindings
        if binding.anchor_sequence_name != binding.local_sequence_name
    )
    if isinstance(
        requirement,
        (
            SequencePresenceRequirement,
            SequenceLengthRequirement,
            SequenceIdentityRequirement,
        ),
    ):
        return tuple(
            binding
            for binding in resource_bindings
            if binding.local_sequence_name == requirement.sequence_name
        )
    if isinstance(requirement, SequenceOrderRequirement):
        names = set(requirement.sequence_names)
        return tuple(
            binding for binding in resource_bindings if binding.local_sequence_name in names
        )
    if isinstance(requirement, (CoordinateBoundsRequirement, ReferenceBaseRequirement)):
        return ()
    assert_never(requirement)


def _ordered_contracts(
    request: EvaluationRequest,
    contracts: tuple[ResourceContract, ...],
) -> tuple[ResourceContract, ...]:
    resource_ids = tuple(contract.resource_id for contract in contracts)
    if len(set(resource_ids)) != len(resource_ids):
        raise ValueError("bundle contracts must have unique resource IDs")
    if set(resource_ids) != set(request.scope.resource_ids):
        raise ValueError("bundle reasoning requires exactly one contract per scoped resource")

    by_id = {contract.resource_id: contract for contract in contracts}
    return tuple(by_id[resource_id] for resource_id in request.scope.resource_ids)


def _candidates_for_requirement(
    context: ReferenceContext,
    requirement: Requirement,
    bindings: tuple[SequenceBinding, ...],
    derived_capabilities: tuple[SequenceIdentityAbsenceCapability, ...],
    supplemental_capabilities: tuple[SupplementalCapability, ...],
) -> tuple[Capability, ...]:
    if isinstance(requirement, SequenceBindingRequirement):
        supplemental_candidates = tuple(
            capability
            for capability in supplemental_capabilities
            if capability_is_comparable(requirement, capability)
        )
        if len(supplemental_candidates) > 1:
            raise ValueError(
                "sequence-binding requirement may use only one supplemental validation capability"
            )
        return supplemental_candidates

    if isinstance(requirement, (CoordinateBoundsRequirement, ReferenceBaseRequirement)):
        supplemental_candidates = tuple(
            capability
            for capability in supplemental_capabilities
            if capability_is_comparable(requirement, capability)
        )
        if len(supplemental_candidates) > 1:
            raise ValueError(
                "pair-derived requirement may use only one exhaustive supplemental capability"
            )
        return supplemental_candidates

    target_name = _target_anchor_name(requirement, bindings)
    candidates: list[Capability] = []
    if isinstance(requirement, SequencePresenceRequirement):
        candidates.extend(
            capability
            for capability in derived_capabilities
            if capability_is_comparable(requirement, capability)
        )
    for capability in context.anchor_capabilities:
        if not capability_is_comparable(requirement, capability):
            continue
        if isinstance(requirement, SequencePresenceRequirement):
            if not isinstance(capability, SequencePresenceCapability):
                continue
            if capability.sequence_name != target_name:
                continue
        elif isinstance(requirement, SequenceLengthRequirement):
            if not isinstance(capability, SequenceLengthCapability):
                continue
            if capability.sequence_name != target_name:
                continue
        elif isinstance(requirement, SequenceIdentityRequirement):
            if not isinstance(capability, SequenceIdentityCapability):
                continue
            if capability.sequence_name != target_name:
                continue
        elif isinstance(requirement, SequenceOrderRequirement):
            projected_names = _target_anchor_order(requirement, bindings)
            scoped_names = {sequence.local_name for sequence in context.sequences}
            if any(name not in scoped_names for name in projected_names):
                continue
        else:
            assert_never(requirement)
        candidates.append(capability)
    return tuple(candidates)


def _validate_supplemental_capabilities(
    request: EvaluationRequest,
    contracts: tuple[ResourceContract, ...],
    capabilities: tuple[SupplementalCapability, ...],
    bindings: tuple[SequenceBinding, ...],
    supplemental_bindings: tuple[SequenceBinding, ...],
) -> None:
    if any(
        not isinstance(
            capability,
            (
                CoordinateBoundsValidationCapability,
                ReferenceBaseValidationCapability,
                SequenceBindingValidationCapability,
            ),
        )
        for capability in capabilities
    ):
        raise TypeError(
            "supplemental capabilities must be reference-base validations, "
            "coordinate-bounds validations, or sequence-binding validations"
        )

    capability_ids = tuple(capability.id for capability in capabilities)
    if len(set(capability_ids)) != len(capability_ids):
        raise ValueError("supplemental capability IDs must be unique")
    if any(capability.resource_id != request.anchor_resource_id for capability in capabilities):
        raise ValueError("supplemental capabilities must belong to the selected FASTA anchor")
    if any(
        capability.subject_resource_id not in request.scope.resource_ids
        for capability in capabilities
    ):
        raise ValueError("supplemental capabilities may describe only scoped resources")

    requirements = tuple(
        requirement
        for contract in contracts
        for requirement in contract.requirements
        if isinstance(
            requirement,
            (
                CoordinateBoundsRequirement,
                ReferenceBaseRequirement,
                SequenceBindingRequirement,
            ),
        )
    )
    if any(
        requirement.anchor_resource_id != request.anchor_resource_id for requirement in requirements
    ):
        raise ValueError("pair-derived requirements must name the selected FASTA anchor")

    for capability in capabilities:
        matches = tuple(
            requirement
            for requirement in requirements
            if capability_is_comparable(requirement, capability)
        )
        if not matches:
            raise ValueError("supplemental pair-derived capability must match a scoped requirement")
        if isinstance(capability, SequenceBindingValidationCapability):
            matching_bindings = tuple(
                binding
                for binding in bindings
                if binding.resource_id == capability.subject_resource_id
                and binding.local_sequence_name == capability.sequence_name
                and binding.anchor_resource_id == capability.resource_id
            )
            if capability.state is SequenceBindingValidationState.BOUND:
                if len(matching_bindings) != 1:
                    raise ValueError(
                        "bound sequence-binding capability requires one matching sequence binding"
                    )
                if matching_bindings[0].anchor_sequence_name != capability.anchor_sequence_name:
                    raise ValueError(
                        "sequence-binding capability target must match its sequence binding"
                    )
            elif capability.state is SequenceBindingValidationState.CONTENT_CONFLICT:
                if len(matching_bindings) != 1:
                    raise ValueError(
                        "content-conflict binding capability requires one identity-derived binding"
                    )
                binding = matching_bindings[0]
                if (
                    binding.method is not SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
                    or binding.anchor_sequence_name == capability.anchor_sequence_name
                ):
                    raise ValueError(
                        "content-conflict binding capability requires a different identity target"
                    )

    for binding in supplemental_bindings:
        authorizations = tuple(
            capability
            for capability in capabilities
            if isinstance(capability, SequenceBindingValidationCapability)
            and capability.state is SequenceBindingValidationState.BOUND
            and capability.resource_id == binding.anchor_resource_id
            and capability.subject_resource_id == binding.resource_id
            and capability.sequence_name == binding.local_sequence_name
            and capability.anchor_sequence_name == binding.anchor_sequence_name
        )
        if len(authorizations) != 1:
            raise ValueError(
                "supplemental authoritative binding requires one matching bound validation"
            )


def _merge_sequence_bindings(
    context: ReferenceContext,
    derived: tuple[SequenceBinding, ...],
    supplemental: tuple[SequenceBinding, ...],
) -> tuple[SequenceBinding, ...]:
    supplemental_ids = tuple(binding.id for binding in supplemental)
    if len(set(supplemental_ids)) != len(supplemental_ids):
        raise ValueError("supplemental sequence-binding IDs must be unique")
    supplemental_keys = tuple(
        (binding.resource_id, binding.local_sequence_name) for binding in supplemental
    )
    if len(set(supplemental_keys)) != len(supplemental_keys):
        raise ValueError("supplemental sequence bindings must map each local name at most once")
    if any(
        binding.resource_id not in context.scope.resource_ids
        or binding.resource_id == context.anchor_resource_id
        or binding.anchor_resource_id != context.anchor_resource_id
        for binding in supplemental
    ):
        raise ValueError(
            "supplemental sequence bindings must map scoped peer resources to the selected anchor"
        )

    for binding in supplemental:
        _validate_supplemental_sequence_binding(context, binding)

    derived_by_key = {
        (binding.resource_id, binding.local_sequence_name): binding for binding in derived
    }
    for binding in supplemental:
        key = (binding.resource_id, binding.local_sequence_name)
        existing = derived_by_key.get(key)
        if existing is not None and existing != binding:
            raise ValueError(
                "supplemental sequence binding conflicts with an independently derived binding"
            )

    combined = list(derived)
    derived_keys = set(derived_by_key)
    combined.extend(
        binding
        for binding in supplemental
        if (binding.resource_id, binding.local_sequence_name) not in derived_keys
    )
    return tuple(combined)


def _validate_supplemental_sequence_binding(
    context: ReferenceContext,
    binding: SequenceBinding,
) -> None:
    if binding.method is not SequenceBindingMethod.AUTHORITATIVE_NAME:
        raise ValueError("supplemental sequence bindings must use the authoritative-name method")

    target = next(
        (
            sequence
            for sequence in context.sequences
            if sequence.local_name == binding.anchor_sequence_name
        ),
        None,
    )
    if target is None:
        raise ValueError("supplemental sequence-binding target must be inside anchor scope")

    target_identities = {
        identity for identity in (target.refget_id, target.md5) if identity is not None
    }
    if not set(binding.identity_values).issubset(target_identities):
        raise ValueError("supplemental sequence-binding identities must match its anchor target")

    resolution = resolve_anchor_sequence_identity(context, binding.identity_values)
    if (
        resolution.state is not AnchorIdentityResolutionState.MATCHED
        or resolution.anchor_sequence_name != binding.anchor_sequence_name
    ):
        raise ValueError(
            "supplemental sequence-binding identity trace must uniquely resolve on the full anchor"
        )
    if set(binding.capability_ids) != set(resolution.anchor_capability_ids):
        raise ValueError(
            "supplemental sequence binding must cite exactly its anchor identity capabilities"
        )


def _target_anchor_order(
    requirement: SequenceOrderRequirement,
    bindings: tuple[SequenceBinding, ...],
) -> tuple[str, ...]:
    by_local_name = {binding.local_sequence_name: binding for binding in bindings}
    return tuple(
        by_local_name[name].anchor_sequence_name if name in by_local_name else name
        for name in requirement.sequence_names
    )


def _target_anchor_name(
    requirement: Requirement,
    bindings: tuple[SequenceBinding, ...],
) -> str | None:
    if isinstance(
        requirement,
        (
            SequenceOrderRequirement,
            CoordinateBoundsRequirement,
            ReferenceBaseRequirement,
            SequenceBindingRequirement,
        ),
    ):
        return None
    if isinstance(
        requirement,
        (
            SequencePresenceRequirement,
            SequenceLengthRequirement,
            SequenceIdentityRequirement,
        ),
    ):
        local_name = requirement.sequence_name
    else:
        assert_never(requirement)

    binding = next(
        (item for item in bindings if item.local_sequence_name == local_name),
        None,
    )
    return binding.anchor_sequence_name if binding is not None else local_name


def _make_constraint_id(
    anchor_resource_id: ResourceId,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
    bindings: tuple[SequenceBinding, ...],
) -> ConstraintId:
    payload = json.dumps(
        [
            str(anchor_resource_id),
            str(requirement.id),
            [str(capability.id) for capability in candidates],
            [str(binding.id) for binding in bindings],
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ConstraintId(f"constraint:{hashlib.sha256(payload).hexdigest()}")
