"""Tests for generic exhaustive coordinate-bounds constraint/evidence reasoning."""

from refcompat.model.constraints import ConstraintId, ConstraintState, SatisfactionMode
from refcompat.model.contracts import (
    CapabilityId,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    ReferenceBaseValidationCapability,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
)
from refcompat.model.evidence import (
    EvidenceKind,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
)
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import derive_constraint_evidence

_ANNOTATION = ResourceId("annotation")
_FASTA = ResourceId("fasta")


def _requirement(count: int = 10) -> CoordinateBoundsRequirement:
    return CoordinateBoundsRequirement(
        RequirementId("coordinate-bounds"),
        _ANNOTATION,
        _FASTA,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        count,
    )


def _capability(
    *,
    representable: int,
    conflicts: int,
    unresolved: int,
) -> CoordinateBoundsValidationCapability:
    return CoordinateBoundsValidationCapability(
        CapabilityId(f"cap-{representable}-{conflicts}-{unresolved}"),
        _FASTA,
        _ANNOTATION,
        checked_count=representable + conflicts + unresolved,
        representable_count=representable,
        conflict_count=conflicts,
        unresolved_count=unresolved,
    )


def test_all_representable_coordinates_are_satisfied_exhaustively() -> None:
    constraint = build_constraint(
        ConstraintId("c"),
        _requirement(),
        (_capability(representable=10, conflicts=0, unresolved=0),),
    )
    evaluation = evaluate_constraint(constraint)

    assert evaluation.state is ConstraintState.SATISFIED
    assert evaluation.satisfaction_mode is SatisfactionMode.EXHAUSTIVE_DIRECT
    evidence = derive_constraint_evidence(constraint, evaluation)
    assert len(evidence) == 1
    assert evidence[0].kind is EvidenceKind.COORDINATE_BOUNDS
    assert evidence[0].polarity is EvidencePolarity.SUPPORTS
    assert evidence[0].strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert evidence[0].method is EvidenceMethod.EXHAUSTIVE_COORDINATE_BOUNDS_VALIDATION


def test_one_coordinate_conflict_remains_unsatisfied_beside_many_valid_intervals() -> None:
    capability = _capability(representable=999_999, conflicts=1, unresolved=0)
    constraint = build_constraint(ConstraintId("c"), _requirement(1_000_000), (capability,))
    evaluation = evaluate_constraint(constraint)

    assert evaluation.state is ConstraintState.UNSATISFIED
    evidence = derive_constraint_evidence(constraint, evaluation)
    assert len(evidence) == 1
    assert evidence[0].polarity is EvidencePolarity.CONTRADICTS
    assert evidence[0].strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL


def test_unresolved_coordinates_do_not_fabricate_evidence() -> None:
    capability = _capability(representable=9, conflicts=0, unresolved=1)
    constraint = build_constraint(ConstraintId("c"), _requirement(), (capability,))
    evaluation = evaluate_constraint(constraint)

    assert evaluation.state is ConstraintState.UNRESOLVED
    assert evaluation.relevant_capability_ids == ()
    assert derive_constraint_evidence(constraint, evaluation) == ()


def test_coordinate_conflict_takes_precedence_over_unresolved_intervals() -> None:
    capability = _capability(representable=8, conflicts=1, unresolved=1)
    constraint = build_constraint(ConstraintId("c"), _requirement(), (capability,))

    assert evaluate_constraint(constraint).state is ConstraintState.UNSATISFIED


def test_empty_coordinate_check_is_not_applicable() -> None:
    capability = _capability(representable=0, conflicts=0, unresolved=0)
    constraint = build_constraint(ConstraintId("c"), _requirement(0), (capability,))

    assert evaluate_constraint(constraint).state is ConstraintState.NOT_APPLICABLE


def test_hard_coordinate_conflict_survives_competing_support() -> None:
    matching = _capability(representable=10, conflicts=0, unresolved=0)
    conflicting = CoordinateBoundsValidationCapability(
        CapabilityId("conflicting"),
        _FASTA,
        _ANNOTATION,
        checked_count=10,
        representable_count=9,
        conflict_count=1,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("c"), _requirement(), (matching, conflicting))
    evaluation = evaluate_constraint(constraint)

    assert evaluation.state is ConstraintState.UNSATISFIED
    assert evaluation.relevant_capability_ids == (conflicting.id,)


def test_wrong_anchor_coordinate_capability_is_not_comparable() -> None:
    wrong_anchor = CoordinateBoundsValidationCapability(
        CapabilityId("wrong-anchor"),
        ResourceId("other-fasta"),
        _ANNOTATION,
        checked_count=10,
        representable_count=10,
        conflict_count=0,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("c"), _requirement(), (wrong_anchor,))

    assert constraint.candidate_capabilities == ()
    assert evaluate_constraint(constraint).state is ConstraintState.UNRESOLVED


def test_wrong_subject_coordinate_capability_is_not_comparable() -> None:
    wrong_subject = CoordinateBoundsValidationCapability(
        CapabilityId("wrong-subject"),
        _FASTA,
        ResourceId("other-annotation"),
        checked_count=10,
        representable_count=10,
        conflict_count=0,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("c"), _requirement(), (wrong_subject,))

    assert constraint.candidate_capabilities == ()
    assert evaluate_constraint(constraint).state is ConstraintState.UNRESOLVED


def test_wrong_coordinate_count_capability_is_not_comparable() -> None:
    wrong_count = _capability(representable=9, conflicts=0, unresolved=0)
    constraint = build_constraint(ConstraintId("c"), _requirement(10), (wrong_count,))

    assert constraint.candidate_capabilities == ()
    assert evaluate_constraint(constraint).state is ConstraintState.UNRESOLVED


def test_reference_base_capability_cannot_satisfy_coordinate_bounds() -> None:
    reference_base = ReferenceBaseValidationCapability(
        CapabilityId("reference-bases"),
        _FASTA,
        _ANNOTATION,
        checked_count=10,
        match_count=10,
        mismatch_count=0,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("c"), _requirement(), (reference_base,))

    assert constraint.candidate_capabilities == ()
    assert evaluate_constraint(constraint).state is ConstraintState.UNRESOLVED
