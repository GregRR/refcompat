"""First exact typed requirement/capability evaluator.

This slice deliberately implements only relationships that the current typed
models can establish without alias inference, completeness assumptions, or
numeric scoring. Missing candidate evidence remains unresolved unless an
explicit negative presence capability proves absence.
"""

from __future__ import annotations

from typing import assert_never

from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintId,
    ConstraintState,
    SatisfactionMode,
    capability_is_comparable,
    constraint_rule_for_requirement,
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


def build_constraint(
    constraint_id: ConstraintId,
    requirement: Requirement,
    candidate_capabilities: tuple[Capability, ...],
) -> CompatibilityConstraint:
    """Build one typed constraint from a caller-selected candidate capability pool."""

    rule = constraint_rule_for_requirement(requirement)
    candidates = tuple(
        capability
        for capability in candidate_capabilities
        if capability_is_comparable(requirement, capability)
    )
    return CompatibilityConstraint(
        id=constraint_id,
        requirement=requirement,
        candidate_capabilities=candidates,
        rule=rule,
    )


def evaluate_constraint(constraint: CompatibilityConstraint) -> ConstraintEvaluation:
    """Evaluate one constraint without inventing evidence absent from its candidates."""

    requirement = constraint.requirement
    if isinstance(requirement, SequencePresenceRequirement):
        return _evaluate_presence(constraint, requirement)
    if isinstance(requirement, SequenceLengthRequirement):
        return _evaluate_length(constraint, requirement)
    if isinstance(requirement, SequenceIdentityRequirement):
        return _evaluate_identity(constraint, requirement)
    if isinstance(requirement, SequenceOrderRequirement):
        return _evaluate_order(constraint, requirement)
    assert_never(requirement)


def _evaluate_presence(
    constraint: CompatibilityConstraint,
    requirement: SequencePresenceRequirement,
) -> ConstraintEvaluation:
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, SequencePresenceCapability)
        and capability.sequence_name == requirement.sequence_name
    )
    if not candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)

    present_values = {capability.present for capability in candidates}
    if len(present_values) != 1:
        return _result(constraint, ConstraintState.UNRESOLVED, candidates=candidates)
    state = ConstraintState.SATISFIED if True in present_values else ConstraintState.UNSATISFIED
    return _result(
        constraint,
        state,
        mode=SatisfactionMode.EXACT if state is ConstraintState.SATISFIED else None,
        candidates=candidates,
    )


def _evaluate_length(
    constraint: CompatibilityConstraint,
    requirement: SequenceLengthRequirement,
) -> ConstraintEvaluation:
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, SequenceLengthCapability)
        and capability.sequence_name == requirement.sequence_name
    )
    return _evaluate_exact_values(
        constraint,
        candidates,
        expected=requirement.length,
        values=tuple(capability.length for capability in candidates),
        satisfied_mode=SatisfactionMode.EXACT,
    )


def _evaluate_identity(
    constraint: CompatibilityConstraint,
    requirement: SequenceIdentityRequirement,
) -> ConstraintEvaluation:
    # CompatibilityConstraint already guarantees scheme comparability. Reuse
    # the centralized comparability rule as defense in depth so this evaluator
    # cannot diverge from the model if another identity scheme is added.
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, SequenceIdentityCapability)
        and capability.sequence_name == requirement.sequence_name
        and capability_is_comparable(requirement, capability)
    )
    return _evaluate_exact_values(
        constraint,
        candidates,
        expected=requirement.identity,
        values=tuple(capability.identity for capability in candidates),
        satisfied_mode=SatisfactionMode.VERIFIED_SEQUENCE_IDENTITY,
    )


def _evaluate_order(
    constraint: CompatibilityConstraint,
    requirement: SequenceOrderRequirement,
) -> ConstraintEvaluation:
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, SequenceOrderCapability)
    )
    return _evaluate_exact_values(
        constraint,
        candidates,
        expected=requirement.sequence_names,
        values=tuple(capability.sequence_names for capability in candidates),
        satisfied_mode=SatisfactionMode.EXACT,
    )


def _evaluate_exact_values(
    constraint: CompatibilityConstraint,
    candidates: tuple[Capability, ...],
    *,
    expected: object,
    values: tuple[object, ...],
    satisfied_mode: SatisfactionMode,
) -> ConstraintEvaluation:
    if not candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)

    distinct_values = set(values)
    if len(distinct_values) != 1:
        return _result(constraint, ConstraintState.UNRESOLVED, candidates=candidates)
    if values[0] == expected:
        return _result(
            constraint,
            ConstraintState.SATISFIED,
            mode=satisfied_mode,
            candidates=candidates,
        )
    return _result(constraint, ConstraintState.UNSATISFIED, candidates=candidates)


def _result(
    constraint: CompatibilityConstraint,
    state: ConstraintState,
    *,
    mode: SatisfactionMode | None = None,
    candidates: tuple[Capability, ...] = (),
) -> ConstraintEvaluation:
    return ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=state,
        satisfaction_mode=mode,
        relevant_capability_ids=tuple(capability.id for capability in candidates),
    )
