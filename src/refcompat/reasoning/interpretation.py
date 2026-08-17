"""Interpret evaluated constraints as structured findings and scope conditions."""

from __future__ import annotations

import hashlib
import json
from typing import assert_never

from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintId,
    ConstraintState,
)
from refcompat.model.contracts import (
    CapabilityId,
    Requirement,
    RequirementId,
    SequenceIdentityRequirement,
    SequenceLengthRequirement,
    SequenceOrderRequirement,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.evidence import EvidenceAggregate, EvidenceId, EvidencePolarity
from refcompat.model.interpretation import (
    CompatibilityCondition,
    CompatibilityFinding,
    ConditionId,
    ConditionKind,
    FindingId,
    FindingKind,
    InterpretationResult,
)
from refcompat.model.resources import ResourceId


def interpret_constraint_results(
    request: EvaluationRequest,
    constraints: tuple[CompatibilityConstraint, ...],
    evaluations: tuple[ConstraintEvaluation, ...],
    evidence: EvidenceAggregate,
) -> InterpretationResult:
    """Create findings and explicit-scope conditions without computing a verdict."""

    _validate_request_scope(request, constraints)
    evaluations_by_id = _validate_interpretation_inputs(constraints, evaluations, evidence)
    findings: list[CompatibilityFinding] = []

    for constraint in constraints:
        evaluation = evaluations_by_id[constraint.id]
        items = evidence.for_constraint(constraint.id)
        if evaluation.state is ConstraintState.NOT_APPLICABLE:
            if items:
                raise ValueError("not-applicable interpretation cannot carry evidence")
            continue

        evidence_capability_ids = tuple(item.capability_id for item in items)
        if evidence_capability_ids != evaluation.relevant_capability_ids:
            raise ValueError("finding evidence does not match evaluator-relevant capabilities")

        if evaluation.state is ConstraintState.SATISFIED:
            if not items or any(item.polarity is not EvidencePolarity.SUPPORTS for item in items):
                raise ValueError("satisfied interpretation requires only supporting evidence")
            continue

        if evaluation.state is ConstraintState.UNSATISFIED:
            kind = _conflict_kind(constraint.requirement)
            if not items or any(
                item.polarity is not EvidencePolarity.CONTRADICTS for item in items
            ):
                raise ValueError("unsatisfied finding requires only contradicting evidence")
        elif evaluation.state is ConstraintState.UNRESOLVED:
            kind = FindingKind.UNRESOLVED_REQUIREMENT
        else:
            assert_never(evaluation.state)

        resource_ids = _finding_resource_ids(constraint, evaluation.relevant_capability_ids)
        evidence_ids = tuple(item.id for item in items)
        findings.append(
            CompatibilityFinding(
                id=_make_finding_id(
                    kind=kind,
                    constraint_ids=(constraint.id,),
                    requirement_ids=(constraint.requirement.id,),
                    evidence_ids=evidence_ids,
                    resource_ids=resource_ids,
                ),
                kind=kind,
                constraint_ids=(constraint.id,),
                requirement_ids=(constraint.requirement.id,),
                evidence_ids=evidence_ids,
                resource_ids=resource_ids,
            )
        )

    constraint_ids = tuple(constraint.id for constraint in constraints)
    conditions = _scope_conditions(request, constraint_ids)
    return InterpretationResult(findings=tuple(findings), conditions=conditions)


def _validate_request_scope(
    request: EvaluationRequest,
    constraints: tuple[CompatibilityConstraint, ...],
) -> None:
    scoped_resource_ids = set(request.scope.resource_ids)
    for constraint in constraints:
        if constraint.requirement.resource_id not in scoped_resource_ids:
            raise ValueError("constraint requirement resource is outside evaluation scope")
        if any(
            capability.resource_id not in scoped_resource_ids
            for capability in constraint.candidate_capabilities
        ):
            raise ValueError("constraint capability resource is outside evaluation scope")


def _validate_interpretation_inputs(
    constraints: tuple[CompatibilityConstraint, ...],
    evaluations: tuple[ConstraintEvaluation, ...],
    evidence: EvidenceAggregate,
) -> dict[ConstraintId, ConstraintEvaluation]:
    constraint_ids = tuple(constraint.id for constraint in constraints)
    if len(set(constraint_ids)) != len(constraint_ids):
        raise ValueError("interpretation constraints must have unique IDs")

    evaluation_ids = tuple(evaluation.constraint_id for evaluation in evaluations)
    if len(set(evaluation_ids)) != len(evaluation_ids):
        raise ValueError("interpretation evaluations must have unique constraint IDs")
    if set(constraint_ids) != set(evaluation_ids):
        raise ValueError("interpretation requires exactly one evaluation per constraint")

    constraints_by_id = {constraint.id: constraint for constraint in constraints}
    evaluations_by_id = {evaluation.constraint_id: evaluation for evaluation in evaluations}

    expected_unresolved = {
        evaluation.constraint_id
        for evaluation in evaluations
        if evaluation.state is ConstraintState.UNRESOLVED
    }
    expected_not_applicable = {
        evaluation.constraint_id
        for evaluation in evaluations
        if evaluation.state is ConstraintState.NOT_APPLICABLE
    }
    if set(evidence.unresolved_constraint_ids) != expected_unresolved:
        raise ValueError("evidence aggregate unresolved constraints do not match evaluations")
    if set(evidence.not_applicable_constraint_ids) != expected_not_applicable:
        raise ValueError("evidence aggregate not-applicable constraints do not match evaluations")

    for item in evidence.evidence:
        constraint = constraints_by_id.get(item.constraint_id)
        if constraint is None:
            raise ValueError("evidence references a constraint outside interpretation input")
        if item.requirement_id != constraint.requirement.id:
            raise ValueError("evidence requirement ID does not match its constraint")
        capability_ids = {capability.id for capability in constraint.candidate_capabilities}
        if item.capability_id not in capability_ids:
            raise ValueError("evidence capability ID is absent from its constraint")

    for constraint in constraints:
        evaluation = evaluations_by_id[constraint.id]
        if evaluation.requirement_id != constraint.requirement.id:
            raise ValueError("interpretation evaluation requirement ID does not match constraint")

    return evaluations_by_id


def _conflict_kind(requirement: Requirement) -> FindingKind:
    if isinstance(requirement, SequencePresenceRequirement):
        return FindingKind.MISSING_REQUIRED_SEQUENCE
    if isinstance(requirement, SequenceLengthRequirement):
        return FindingKind.SEQUENCE_LENGTH_CONFLICT
    if isinstance(requirement, SequenceIdentityRequirement):
        return FindingKind.SEQUENCE_IDENTITY_CONFLICT
    if isinstance(requirement, SequenceOrderRequirement):
        return FindingKind.SEQUENCE_ORDER_CONFLICT
    assert_never(requirement)


def _finding_resource_ids(
    constraint: CompatibilityConstraint,
    relevant_capability_ids: tuple[CapabilityId, ...],
) -> tuple[ResourceId, ...]:
    resource_ids: list[ResourceId] = [constraint.requirement.resource_id]
    relevant = set(relevant_capability_ids)
    for capability in constraint.candidate_capabilities:
        if capability.id in relevant and capability.resource_id not in resource_ids:
            resource_ids.append(capability.resource_id)
    return tuple(resource_ids)


def _scope_conditions(
    request: EvaluationRequest,
    constraint_ids: tuple[ConstraintId, ...],
) -> tuple[CompatibilityCondition, ...]:
    conditions: list[CompatibilityCondition] = []
    supplied_ids = tuple(resource.id for resource in request.resources)
    scoped_ids = set(request.scope.resource_ids)
    excluded_ids = tuple(
        resource_id for resource_id in supplied_ids if resource_id not in scoped_ids
    )

    if excluded_ids:
        conditions.append(
            CompatibilityCondition(
                id=_make_condition_id(
                    kind=ConditionKind.EXPLICIT_RESOURCE_SCOPE,
                    anchor_resource_id=request.anchor_resource_id,
                    scope_resource_ids=request.scope.resource_ids,
                    anchor_sequence_names=request.scope.anchor_sequence_names,
                    constraint_ids=constraint_ids,
                    excluded_resource_ids=excluded_ids,
                ),
                kind=ConditionKind.EXPLICIT_RESOURCE_SCOPE,
                scope=request.scope,
                anchor_resource_id=request.anchor_resource_id,
                constraint_ids=constraint_ids,
                excluded_resource_ids=excluded_ids,
            )
        )

    if request.scope.anchor_sequence_names is not None:
        conditions.append(
            CompatibilityCondition(
                id=_make_condition_id(
                    kind=ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE,
                    anchor_resource_id=request.anchor_resource_id,
                    scope_resource_ids=request.scope.resource_ids,
                    anchor_sequence_names=request.scope.anchor_sequence_names,
                    constraint_ids=constraint_ids,
                    excluded_resource_ids=(),
                ),
                kind=ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE,
                scope=request.scope,
                anchor_resource_id=request.anchor_resource_id,
                constraint_ids=constraint_ids,
            )
        )

    return tuple(conditions)


def _make_finding_id(
    *,
    kind: FindingKind,
    constraint_ids: tuple[ConstraintId, ...],
    requirement_ids: tuple[RequirementId, ...],
    evidence_ids: tuple[EvidenceId, ...],
    resource_ids: tuple[ResourceId, ...],
) -> FindingId:
    payload = [
        kind.value,
        sorted(str(value) for value in constraint_ids),
        sorted(str(value) for value in requirement_ids),
        sorted(str(value) for value in evidence_ids),
        sorted(str(value) for value in resource_ids),
    ]
    return FindingId(f"finding:{_digest_payload(payload)}")


def _make_condition_id(
    *,
    kind: ConditionKind,
    anchor_resource_id: ResourceId,
    scope_resource_ids: tuple[ResourceId, ...],
    anchor_sequence_names: tuple[str, ...] | None,
    constraint_ids: tuple[ConstraintId, ...],
    excluded_resource_ids: tuple[ResourceId, ...],
) -> ConditionId:
    payload = [
        kind.value,
        str(anchor_resource_id),
        sorted(str(value) for value in scope_resource_ids),
        sorted(anchor_sequence_names) if anchor_sequence_names is not None else None,
        sorted(str(value) for value in constraint_ids),
        sorted(str(value) for value in excluded_resource_ids),
    ]
    return ConditionId(f"condition:{_digest_payload(payload)}")


def _digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
