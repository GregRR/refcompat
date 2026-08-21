"""Derive and aggregate qualitative evidence from typed constraint evaluations."""

from __future__ import annotations

import hashlib
import json

from refcompat._compat import assert_never
from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintId,
    ConstraintState,
    capability_is_comparable,
    projected_sequence_name,
    projected_sequence_order,
)
from refcompat.model.contracts import (
    Capability,
    Requirement,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.evidence import (
    Evidence,
    EvidenceAggregate,
    EvidenceId,
    EvidenceKind,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
)
from refcompat.model.reference_context import SequenceBinding, SequenceBindingId
from refcompat.model.resources import ResourceId


def aggregate_constraint_evidence(
    constraints: tuple[CompatibilityConstraint, ...],
    evaluations: tuple[ConstraintEvaluation, ...],
) -> EvidenceAggregate:
    """Aggregate traceable evidence without computing a score or bundle verdict."""

    constraint_ids = tuple(constraint.id for constraint in constraints)
    if len(set(constraint_ids)) != len(constraint_ids):
        raise ValueError("constraints must have unique IDs for evidence aggregation")

    evaluation_ids = tuple(evaluation.constraint_id for evaluation in evaluations)
    if len(set(evaluation_ids)) != len(evaluation_ids):
        raise ValueError("constraint evaluations must have unique constraint IDs")
    if set(constraint_ids) != set(evaluation_ids):
        raise ValueError("evidence aggregation requires exactly one evaluation per constraint")

    evaluations_by_id = {evaluation.constraint_id: evaluation for evaluation in evaluations}
    evidence: list[Evidence] = []
    unresolved: list[ConstraintId] = []
    not_applicable: list[ConstraintId] = []

    for constraint in constraints:
        evaluation = evaluations_by_id[constraint.id]
        if evaluation.requirement_id != constraint.requirement.id:
            raise ValueError("constraint evaluation requirement ID does not match its constraint")

        if evaluation.state is ConstraintState.UNRESOLVED:
            unresolved.append(constraint.id)
        elif evaluation.state is ConstraintState.NOT_APPLICABLE:
            not_applicable.append(constraint.id)

        items = derive_constraint_evidence(constraint, evaluation)
        _validate_evidence_matches_evaluation(evaluation, items)
        evidence.extend(items)

    return EvidenceAggregate(
        evidence=tuple(evidence),
        unresolved_constraint_ids=tuple(unresolved),
        not_applicable_constraint_ids=tuple(not_applicable),
    )


def derive_constraint_evidence(
    constraint: CompatibilityConstraint,
    evaluation: ConstraintEvaluation,
) -> tuple[Evidence, ...]:
    """Derive one qualitative evidence item per evaluator-relevant capability."""

    if evaluation.constraint_id != constraint.id:
        raise ValueError("constraint evaluation does not belong to the supplied constraint")
    if evaluation.requirement_id != constraint.requirement.id:
        raise ValueError("constraint evaluation requirement ID does not match its constraint")

    candidates_by_id = {
        capability.id: capability for capability in constraint.candidate_capabilities
    }
    missing_ids = tuple(
        capability_id
        for capability_id in evaluation.relevant_capability_ids
        if capability_id not in candidates_by_id
    )
    if missing_ids:
        raise ValueError("constraint evaluation references a capability absent from its constraint")

    return tuple(
        _evidence_from_capability(constraint, candidates_by_id[capability_id])
        for capability_id in evaluation.relevant_capability_ids
    )


def _evidence_from_capability(
    constraint: CompatibilityConstraint,
    capability: Capability,
) -> Evidence:
    requirement = constraint.requirement
    if not capability_is_comparable(requirement, capability):
        raise ValueError("evidence capability is not comparable to the requirement")

    kind, strength, polarity, method, binding_ids = _classify_relationship(
        constraint,
        requirement,
        capability,
    )
    return Evidence(
        id=_make_evidence_id(
            constraint_id=str(constraint.id),
            requirement_id=str(requirement.id),
            capability_id=str(capability.id),
            kind=kind,
            method=method,
            strength=strength,
            polarity=polarity,
            binding_ids=tuple(str(binding_id) for binding_id in binding_ids),
        ),
        kind=kind,
        method=method,
        strength=strength,
        polarity=polarity,
        constraint_id=constraint.id,
        requirement_id=requirement.id,
        capability_id=capability.id,
        source_observation_ids=capability.source_observation_ids,
        sequence_binding_ids=binding_ids,
    )


def _classify_relationship(
    constraint: CompatibilityConstraint,
    requirement: Requirement,
    capability: Capability,
) -> tuple[
    EvidenceKind,
    EvidenceStrength,
    EvidencePolarity,
    EvidenceMethod,
    tuple[SequenceBindingId, ...],
]:
    if isinstance(requirement, SequencePresenceRequirement):
        if not isinstance(capability, SequencePresenceCapability):
            raise ValueError("presence evidence requires a presence capability")
        binding = _named_binding(
            constraint,
            requirement.sequence_name,
            capability.sequence_name,
            capability.resource_id,
        )
        return (
            EvidenceKind.SEQUENCE_PRESENCE,
            EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            EvidencePolarity.SUPPORTS if capability.present else EvidencePolarity.CONTRADICTS,
            _method(binding),
            _binding_ids(binding),
        )

    if isinstance(requirement, SequenceLengthRequirement):
        if not isinstance(capability, SequenceLengthCapability):
            raise ValueError("length evidence requires a length capability")
        binding = _named_binding(
            constraint,
            requirement.sequence_name,
            capability.sequence_name,
            capability.resource_id,
        )
        return (
            EvidenceKind.SEQUENCE_LENGTH,
            EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            EvidencePolarity.SUPPORTS
            if capability.length == requirement.length
            else EvidencePolarity.CONTRADICTS,
            _method(binding),
            _binding_ids(binding),
        )

    if isinstance(requirement, SequenceIdentityRequirement):
        if not isinstance(capability, SequenceIdentityCapability):
            raise ValueError("identity evidence requires an identity capability")
        binding = _named_binding(
            constraint,
            requirement.sequence_name,
            capability.sequence_name,
            capability.resource_id,
        )
        return (
            EvidenceKind.SEQUENCE_IDENTITY,
            EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT,
            EvidencePolarity.SUPPORTS
            if capability.identity == requirement.identity
            else EvidencePolarity.CONTRADICTS,
            _method(binding),
            _binding_ids(binding),
        )

    if isinstance(requirement, SequenceOrderRequirement):
        if not isinstance(capability, SequenceOrderCapability):
            raise ValueError("order evidence requires an order capability")
        projected = projected_sequence_order(constraint, requirement, capability.resource_id)
        if projected is None:
            raise ValueError("order evidence capability is not relevant to the requirement")
        expected_names, bindings = projected
        binding_ids = tuple(binding.id for binding in bindings)
        return (
            EvidenceKind.SEQUENCE_ORDER,
            EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            EvidencePolarity.SUPPORTS
            if capability.sequence_names == expected_names
            else EvidencePolarity.CONTRADICTS,
            EvidenceMethod.VERIFIED_SEQUENCE_BINDING
            if binding_ids
            else EvidenceMethod.EXACT_TYPED_CONSTRAINT,
            binding_ids,
        )

    assert_never(requirement)


def _named_binding(
    constraint: CompatibilityConstraint,
    local_name: str,
    capability_name: str,
    capability_resource_id: ResourceId,
) -> SequenceBinding | None:
    projected = projected_sequence_name(
        constraint,
        local_name,
        capability_resource_id,
    )
    if projected is None or capability_name != projected[0]:
        raise ValueError("evidence capability is not relevant to the requirement")
    return projected[1]


def _method(binding: SequenceBinding | None) -> EvidenceMethod:
    if binding is not None and binding.anchor_sequence_name != binding.local_sequence_name:
        return EvidenceMethod.VERIFIED_SEQUENCE_BINDING
    return EvidenceMethod.EXACT_TYPED_CONSTRAINT


def _binding_ids(binding: SequenceBinding | None) -> tuple[SequenceBindingId, ...]:
    if binding is not None and binding.anchor_sequence_name != binding.local_sequence_name:
        return (binding.id,)
    return ()


def _validate_evidence_matches_evaluation(
    evaluation: ConstraintEvaluation,
    evidence: tuple[Evidence, ...],
) -> None:
    if evaluation.state is ConstraintState.SATISFIED:
        if not evidence or any(item.polarity is not EvidencePolarity.SUPPORTS for item in evidence):
            raise ValueError("satisfied evaluation must be backed only by supporting evidence")
    elif evaluation.state is ConstraintState.UNSATISFIED and (
        not evidence or any(item.polarity is not EvidencePolarity.CONTRADICTS for item in evidence)
    ):
        raise ValueError("unsatisfied evaluation must be backed only by contradicting evidence")


def _make_evidence_id(
    *,
    constraint_id: str,
    requirement_id: str,
    capability_id: str,
    kind: EvidenceKind,
    method: EvidenceMethod,
    strength: EvidenceStrength,
    polarity: EvidencePolarity,
    binding_ids: tuple[str, ...] = (),
) -> EvidenceId:
    """Return an opaque deterministic ID for one derived evidence relationship."""

    payload = json.dumps(
        [
            constraint_id,
            requirement_id,
            capability_id,
            kind.value,
            method.value,
            strength.value,
            polarity.value,
            *sorted(binding_ids),
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return EvidenceId(f"evidence:{digest}")
