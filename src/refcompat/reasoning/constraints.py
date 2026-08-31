"""Typed requirement/capability evaluation with optional verified bindings.

Missing candidate evidence remains unresolved unless an explicit negative
presence capability proves absence. Sequence-name projection uses only explicit
``SequenceBinding`` objects; no string-based alias inference occurs here.
"""

from __future__ import annotations

from typing import TypeAlias, TypeVar

from refcompat._compat import assert_never
from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintId,
    ConstraintState,
    SatisfactionMode,
    capability_is_comparable,
    constraint_rule_for_requirement,
    projected_sequence_name,
    projected_sequence_order,
)
from refcompat.model.contracts import (
    Capability,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    SequenceBindingRequirement,
    SequenceBindingValidationCapability,
    SequenceBindingValidationState,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.reference_context import SequenceBinding

_NamedSequenceCapability: TypeAlias = (
    SequencePresenceCapability | SequenceLengthCapability | SequenceIdentityCapability
)

_NamedSequenceCapabilityT = TypeVar("_NamedSequenceCapabilityT", bound=_NamedSequenceCapability)


def build_constraint(
    constraint_id: ConstraintId,
    requirement: Requirement,
    candidate_capabilities: tuple[Capability, ...],
    sequence_bindings: tuple[SequenceBinding, ...] = (),
) -> CompatibilityConstraint:
    """Build one typed constraint from caller-selected candidates and bindings."""

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
        sequence_bindings=sequence_bindings,
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
    if isinstance(requirement, SequenceBindingRequirement):
        return _evaluate_sequence_binding(constraint, requirement)
    if isinstance(requirement, CoordinateBoundsRequirement):
        return _evaluate_coordinate_bounds(constraint, requirement)
    if isinstance(requirement, ReferenceBaseRequirement):
        return _evaluate_reference_bases(constraint, requirement)
    assert_never(requirement)


def _evaluate_presence(
    constraint: CompatibilityConstraint,
    requirement: SequencePresenceRequirement,
) -> ConstraintEvaluation:
    absence_candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, SequenceIdentityAbsenceCapability)
        and capability_is_comparable(requirement, capability)
    )
    if absence_candidates:
        return _result(
            constraint,
            ConstraintState.UNSATISFIED,
            candidates=absence_candidates,
        )

    candidates, used_alias = _named_candidates(
        constraint,
        requirement.sequence_name,
        SequencePresenceCapability,
    )
    if not candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)

    present_values = {capability.present for capability in candidates}
    if len(present_values) != 1:
        return _result(constraint, ConstraintState.UNRESOLVED, candidates=candidates)

    state = ConstraintState.SATISFIED if True in present_values else ConstraintState.UNSATISFIED
    mode = None
    if state is ConstraintState.SATISFIED:
        mode = SatisfactionMode.VERIFIED_ALIAS if used_alias else SatisfactionMode.EXACT
    return _result(constraint, state, mode=mode, candidates=candidates)


def _evaluate_length(
    constraint: CompatibilityConstraint,
    requirement: SequenceLengthRequirement,
) -> ConstraintEvaluation:
    candidates, used_alias = _named_candidates(
        constraint,
        requirement.sequence_name,
        SequenceLengthCapability,
    )
    return _evaluate_exact_values(
        constraint,
        candidates,
        expected=requirement.length,
        values=tuple(capability.length for capability in candidates),
        satisfied_mode=(SatisfactionMode.VERIFIED_ALIAS if used_alias else SatisfactionMode.EXACT),
    )


def _evaluate_identity(
    constraint: CompatibilityConstraint,
    requirement: SequenceIdentityRequirement,
) -> ConstraintEvaluation:
    candidates, _used_alias = _named_candidates(
        constraint,
        requirement.sequence_name,
        SequenceIdentityCapability,
    )
    candidates = tuple(
        capability for capability in candidates if capability_is_comparable(requirement, capability)
    )
    return _evaluate_exact_values(
        constraint,
        candidates,
        expected=requirement.identity,
        values=tuple(capability.identity for capability in candidates),
        satisfied_mode=SatisfactionMode.VERIFIED_SEQUENCE_IDENTITY,
    )


def _evaluate_sequence_binding(
    constraint: CompatibilityConstraint,
    requirement: SequenceBindingRequirement,
) -> ConstraintEvaluation:
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, SequenceBindingValidationCapability)
        and capability_is_comparable(requirement, capability)
    )
    if not candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)

    states = {capability.state for capability in candidates}
    if len(states) != 1:
        return _result(constraint, ConstraintState.UNRESOLVED, candidates=candidates)

    state = next(iter(states))
    if state in (
        SequenceBindingValidationState.CONTENT_CONFLICT,
        SequenceBindingValidationState.PROVEN_ABSENT,
    ):
        return _result(constraint, ConstraintState.UNSATISFIED, candidates=candidates)

    bindings = tuple(
        binding
        for binding in constraint.sequence_bindings
        if binding.local_sequence_name == requirement.sequence_name
        and binding.anchor_resource_id == requirement.anchor_resource_id
    )
    if len(bindings) != 1:
        return _result(constraint, ConstraintState.UNRESOLVED)
    binding = bindings[0]
    if any(
        capability.anchor_sequence_name != binding.anchor_sequence_name for capability in candidates
    ):
        return _result(constraint, ConstraintState.UNRESOLVED, candidates=candidates)
    return _result(
        constraint,
        ConstraintState.SATISFIED,
        mode=SatisfactionMode.VERIFIED_SEQUENCE_BINDING,
        candidates=candidates,
    )


def _evaluate_coordinate_bounds(
    constraint: CompatibilityConstraint,
    requirement: CoordinateBoundsRequirement,
) -> ConstraintEvaluation:
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, CoordinateBoundsValidationCapability)
        and capability_is_comparable(requirement, capability)
    )
    if not candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)

    by_state = {
        state: tuple(
            capability for capability in candidates if _coordinate_bounds_state(capability) is state
        )
        for state in ConstraintState
    }
    if by_state[ConstraintState.UNSATISFIED]:
        return _result(
            constraint,
            ConstraintState.UNSATISFIED,
            candidates=by_state[ConstraintState.UNSATISFIED],
        )
    if by_state[ConstraintState.UNRESOLVED]:
        return _result(constraint, ConstraintState.UNRESOLVED)
    if by_state[ConstraintState.SATISFIED]:
        return _result(
            constraint,
            ConstraintState.SATISFIED,
            mode=SatisfactionMode.EXHAUSTIVE_DIRECT,
            candidates=by_state[ConstraintState.SATISFIED],
        )
    return _result(constraint, ConstraintState.NOT_APPLICABLE)


def _coordinate_bounds_state(
    capability: CoordinateBoundsValidationCapability,
) -> ConstraintState:
    if capability.checked_count == 0:
        return ConstraintState.NOT_APPLICABLE
    if capability.conflict_count:
        return ConstraintState.UNSATISFIED
    if capability.unresolved_count:
        return ConstraintState.UNRESOLVED
    return ConstraintState.SATISFIED


def _evaluate_reference_bases(
    constraint: CompatibilityConstraint,
    requirement: ReferenceBaseRequirement,
) -> ConstraintEvaluation:
    candidates = tuple(
        capability
        for capability in constraint.candidate_capabilities
        if isinstance(capability, ReferenceBaseValidationCapability)
        and capability_is_comparable(requirement, capability)
    )
    if not candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)

    by_state = {
        state: tuple(
            capability for capability in candidates if _reference_base_state(capability) is state
        )
        for state in ConstraintState
    }
    if by_state[ConstraintState.UNSATISFIED]:
        return _result(
            constraint,
            ConstraintState.UNSATISFIED,
            candidates=by_state[ConstraintState.UNSATISFIED],
        )
    if by_state[ConstraintState.UNRESOLVED]:
        return _result(constraint, ConstraintState.UNRESOLVED)
    if by_state[ConstraintState.SATISFIED]:
        return _result(
            constraint,
            ConstraintState.SATISFIED,
            mode=SatisfactionMode.EXHAUSTIVE_DIRECT,
            candidates=by_state[ConstraintState.SATISFIED],
        )
    return _result(constraint, ConstraintState.NOT_APPLICABLE)


def _reference_base_state(
    capability: ReferenceBaseValidationCapability,
) -> ConstraintState:
    if capability.checked_count == 0:
        return ConstraintState.NOT_APPLICABLE
    if capability.mismatch_count:
        return ConstraintState.UNSATISFIED
    if capability.unresolved_count:
        return ConstraintState.UNRESOLVED
    return ConstraintState.SATISFIED


def _evaluate_order(
    constraint: CompatibilityConstraint,
    requirement: SequenceOrderRequirement,
) -> ConstraintEvaluation:
    candidates: list[SequenceOrderCapability] = []
    matches: list[bool] = []
    used_alias = False

    for capability in constraint.candidate_capabilities:
        if not isinstance(capability, SequenceOrderCapability):
            continue
        projected = projected_sequence_order(constraint, requirement, capability.resource_id)
        if projected is None:
            continue
        expected_names, bindings = projected
        candidates.append(capability)
        matches.append(capability.sequence_names == expected_names)
        used_alias = used_alias or bool(bindings)

    typed_candidates = tuple(candidates)
    if not typed_candidates:
        return _result(constraint, ConstraintState.UNRESOLVED)
    if len(set(matches)) != 1:
        return _result(constraint, ConstraintState.UNRESOLVED, candidates=typed_candidates)
    if matches[0]:
        return _result(
            constraint,
            ConstraintState.SATISFIED,
            mode=SatisfactionMode.VERIFIED_ALIAS if used_alias else SatisfactionMode.EXACT,
            candidates=typed_candidates,
        )
    return _result(constraint, ConstraintState.UNSATISFIED, candidates=typed_candidates)


def _named_candidates(
    constraint: CompatibilityConstraint,
    local_sequence_name: str,
    capability_type: type[_NamedSequenceCapabilityT],
) -> tuple[tuple[_NamedSequenceCapabilityT, ...], bool]:
    candidates: list[_NamedSequenceCapabilityT] = []
    used_alias = False
    for capability in constraint.candidate_capabilities:
        if not isinstance(capability, capability_type):
            continue
        projected = projected_sequence_name(
            constraint,
            local_sequence_name,
            capability.resource_id,
        )
        if projected is None:
            continue
        projected_name, binding = projected
        if capability.sequence_name != projected_name:
            continue
        candidates.append(capability)
        if binding is not None and binding.anchor_sequence_name != binding.local_sequence_name:
            used_alias = True
    return tuple(candidates), used_alias


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
