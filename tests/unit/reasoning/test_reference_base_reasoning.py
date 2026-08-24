"""Tests for generic exhaustive reference-base constraint/evidence reasoning."""

from refcompat.model.constraints import ConstraintId, ConstraintState, SatisfactionMode
from refcompat.model.contracts import (
    CapabilityId,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
)
from refcompat.model.evidence import EvidenceMethod, EvidencePolarity, EvidenceStrength
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import derive_constraint_evidence

_VCF = ResourceId("variants")
_FASTA = ResourceId("fasta")


def _requirement(count: int = 10) -> ReferenceBaseRequirement:
    return ReferenceBaseRequirement(
        RequirementId("ref-bases"),
        _VCF,
        _FASTA,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        count,
    )


def _capability(
    *,
    matches: int,
    mismatches: int,
    unresolved: int,
) -> ReferenceBaseValidationCapability:
    return ReferenceBaseValidationCapability(
        CapabilityId(f"cap-{matches}-{mismatches}-{unresolved}"),
        _FASTA,
        _VCF,
        checked_count=matches + mismatches + unresolved,
        match_count=matches,
        mismatch_count=mismatches,
        unresolved_count=unresolved,
    )


def test_all_matched_reference_bases_are_satisfied_exhaustively() -> None:
    constraint = build_constraint(
        ConstraintId("c"),
        _requirement(),
        (_capability(matches=10, mismatches=0, unresolved=0),),
    )
    evaluation = evaluate_constraint(constraint)
    assert evaluation.state is ConstraintState.SATISFIED
    assert evaluation.satisfaction_mode is SatisfactionMode.EXHAUSTIVE_DIRECT


def test_one_mismatch_remains_unsatisfied_beside_many_matches() -> None:
    capability = _capability(matches=999, mismatches=1, unresolved=0)
    constraint = build_constraint(ConstraintId("c"), _requirement(1000), (capability,))
    evaluation = evaluate_constraint(constraint)
    assert evaluation.state is ConstraintState.UNSATISFIED
    evidence = derive_constraint_evidence(constraint, evaluation)
    assert len(evidence) == 1
    assert evidence[0].polarity is EvidencePolarity.CONTRADICTS
    assert evidence[0].strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert evidence[0].method is EvidenceMethod.EXHAUSTIVE_REFERENCE_BASE_VALIDATION


def test_unresolved_reference_base_records_do_not_fabricate_evidence() -> None:
    capability = _capability(matches=9, mismatches=0, unresolved=1)
    constraint = build_constraint(ConstraintId("c"), _requirement(), (capability,))
    evaluation = evaluate_constraint(constraint)
    assert evaluation.state is ConstraintState.UNRESOLVED
    assert evaluation.relevant_capability_ids == ()
    assert derive_constraint_evidence(constraint, evaluation) == ()


def test_mismatch_takes_precedence_over_unresolved_records() -> None:
    capability = _capability(matches=8, mismatches=1, unresolved=1)
    constraint = build_constraint(ConstraintId("c"), _requirement(), (capability,))
    assert evaluate_constraint(constraint).state is ConstraintState.UNSATISFIED


def test_empty_reference_base_check_is_not_applicable() -> None:
    capability = _capability(matches=0, mismatches=0, unresolved=0)
    constraint = build_constraint(ConstraintId("c"), _requirement(0), (capability,))
    assert evaluate_constraint(constraint).state is ConstraintState.NOT_APPLICABLE


def test_hard_reference_base_conflict_survives_competing_support() -> None:
    matching = _capability(matches=10, mismatches=0, unresolved=0)
    conflicting = ReferenceBaseValidationCapability(
        CapabilityId("conflicting"),
        _FASTA,
        _VCF,
        checked_count=10,
        match_count=9,
        mismatch_count=1,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("c"), _requirement(), (matching, conflicting))
    evaluation = evaluate_constraint(constraint)
    assert evaluation.state is ConstraintState.UNSATISFIED
    assert evaluation.relevant_capability_ids == (conflicting.id,)


def test_wrong_anchor_reference_base_capability_is_not_comparable() -> None:
    wrong_anchor = ReferenceBaseValidationCapability(
        CapabilityId("wrong-anchor"),
        ResourceId("other-fasta"),
        _VCF,
        checked_count=10,
        match_count=10,
        mismatch_count=0,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("c"), _requirement(), (wrong_anchor,))

    assert constraint.candidate_capabilities == ()
    assert evaluate_constraint(constraint).state is ConstraintState.UNRESOLVED
