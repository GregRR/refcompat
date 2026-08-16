"""Unit tests for qualitative evidence derivation and aggregation."""

from __future__ import annotations

import pytest

from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintId,
    ConstraintRule,
    ConstraintState,
    SatisfactionMode,
)
from refcompat.model.contracts import (
    CapabilityId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.evidence import EvidenceKind, EvidencePolarity, EvidenceStrength
from refcompat.model.identity import Md5Digest
from refcompat.model.observations import ObservationId
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence, derive_constraint_evidence

_REQUIRED = ResourceId("consumer")
_ANCHOR = ResourceId("reference")
_MD5_A = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_B = Md5Digest("ca773511c152b8191d2757f5a45ff252")


def _length_requirement() -> SequenceLengthRequirement:
    return SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )


def test_matching_length_derives_deterministic_tier_b_support() -> None:
    capability = SequenceLengthCapability(
        id=CapabilityId("length"),
        resource_id=_ANCHOR,
        sequence_name="chr1",
        length=4,
        source_observation_ids=(ObservationId("obs-length"),),
    )
    constraint = build_constraint(ConstraintId("length"), _length_requirement(), (capability,))
    evaluation = evaluate_constraint(constraint)

    first = derive_constraint_evidence(constraint, evaluation)
    second = derive_constraint_evidence(constraint, evaluation)

    assert first == second
    assert first[0].kind is EvidenceKind.SEQUENCE_LENGTH
    assert first[0].strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert first[0].polarity is EvidencePolarity.SUPPORTS
    assert first[0].source_observation_ids == (ObservationId("obs-length"),)


def test_identity_match_is_tier_a_support() -> None:
    requirement = SequenceIdentityRequirement(
        id=RequirementId("req-identity-support"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        identity=_MD5_A,
    )
    capability = SequenceIdentityCapability(
        id=CapabilityId("identity-support"),
        resource_id=_ANCHOR,
        sequence_name="chr1",
        identity=_MD5_A,
        source_observation_ids=(ObservationId("obs-md5-support"),),
    )
    constraint = build_constraint(ConstraintId("identity-support"), requirement, (capability,))
    evaluation = evaluate_constraint(constraint)

    evidence = derive_constraint_evidence(constraint, evaluation)

    assert evaluation.state is ConstraintState.SATISFIED
    assert evidence[0].kind is EvidenceKind.SEQUENCE_IDENTITY
    assert evidence[0].strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert evidence[0].polarity is EvidencePolarity.SUPPORTS
    assert evidence[0].source_observation_ids == (ObservationId("obs-md5-support"),)


def test_identity_mismatch_is_tier_a_contradiction() -> None:
    requirement = SequenceIdentityRequirement(
        id=RequirementId("req-identity"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        identity=_MD5_A,
    )
    capability = SequenceIdentityCapability(
        id=CapabilityId("identity"),
        resource_id=_ANCHOR,
        sequence_name="chr1",
        identity=_MD5_B,
        source_observation_ids=(ObservationId("obs-md5"),),
    )
    constraint = build_constraint(ConstraintId("identity"), requirement, (capability,))
    evaluation = evaluate_constraint(constraint)

    aggregate = aggregate_constraint_evidence((constraint,), (evaluation,))

    assert evaluation.state is ConstraintState.UNSATISFIED
    assert aggregate.evidence[0].strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert aggregate.evidence[0].polarity is EvidencePolarity.CONTRADICTS
    assert aggregate.conclusive_contradictions == aggregate.evidence


def test_unresolved_missing_evidence_produces_no_evidence_item() -> None:
    constraint = build_constraint(ConstraintId("missing"), _length_requirement(), ())
    evaluation = evaluate_constraint(constraint)

    aggregate = aggregate_constraint_evidence((constraint,), (evaluation,))

    assert aggregate.evidence == ()
    assert aggregate.unresolved_constraint_ids == (ConstraintId("missing"),)
    assert aggregate.has_conclusive_contradiction is False


def test_conflicting_candidates_remain_unresolved_while_both_relationships_survive() -> None:
    matching = SequenceLengthCapability(
        id=CapabilityId("matching"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )
    wrong = SequenceLengthCapability(
        id=CapabilityId("wrong"), resource_id=_ANCHOR, sequence_name="chr1", length=5
    )
    constraint = build_constraint(
        ConstraintId("conflict"), _length_requirement(), (matching, wrong)
    )
    evaluation = evaluate_constraint(constraint)

    aggregate = aggregate_constraint_evidence((constraint,), (evaluation,))

    assert evaluation.state is ConstraintState.UNRESOLVED
    assert tuple(item.polarity for item in aggregate.evidence) == (
        EvidencePolarity.SUPPORTS,
        EvidencePolarity.CONTRADICTS,
    )
    assert aggregate.unresolved_constraint_ids == (ConstraintId("conflict"),)


def test_explicit_negative_presence_becomes_tier_b_contradiction() -> None:
    requirement = SequencePresenceRequirement(
        id=RequirementId("req-presence"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chrX",
    )
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_ANCHOR, sequence_name="chrX", present=False
    )
    constraint = build_constraint(ConstraintId("presence"), requirement, (absent,))
    evaluation = evaluate_constraint(constraint)

    evidence = derive_constraint_evidence(constraint, evaluation)

    assert evaluation.state is ConstraintState.UNSATISFIED
    assert evidence[0].kind is EvidenceKind.SEQUENCE_PRESENCE
    assert evidence[0].strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert evidence[0].polarity is EvidencePolarity.CONTRADICTS


def test_many_weak_supports_do_not_hide_tier_a_contradiction() -> None:
    supporting_constraints = []
    supporting_evaluations = []
    for index in range(5):
        requirement = SequenceLengthRequirement(
            id=RequirementId(f"req-length-{index}"),
            resource_id=_REQUIRED,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=f"chr{index}",
            length=4,
        )
        capability = SequenceLengthCapability(
            id=CapabilityId(f"length-{index}"),
            resource_id=_ANCHOR,
            sequence_name=f"chr{index}",
            length=4,
        )
        constraint = build_constraint(ConstraintId(f"length-{index}"), requirement, (capability,))
        supporting_constraints.append(constraint)
        supporting_evaluations.append(evaluate_constraint(constraint))

    identity_requirement = SequenceIdentityRequirement(
        id=RequirementId("req-identity"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chrX",
        identity=_MD5_A,
    )
    identity_capability = SequenceIdentityCapability(
        id=CapabilityId("wrong-identity"),
        resource_id=_ANCHOR,
        sequence_name="chrX",
        identity=_MD5_B,
    )
    identity_constraint = build_constraint(
        ConstraintId("identity"), identity_requirement, (identity_capability,)
    )
    identity_evaluation = evaluate_constraint(identity_constraint)

    aggregate = aggregate_constraint_evidence(
        (*supporting_constraints, identity_constraint),
        (*supporting_evaluations, identity_evaluation),
    )

    assert len(aggregate.supporting_evidence) == 5
    assert len(aggregate.conclusive_contradictions) == 1
    assert aggregate.has_conclusive_contradiction is True


def test_aggregation_matches_evaluations_by_constraint_id_not_input_position() -> None:
    first_capability = SequenceLengthCapability(
        id=CapabilityId("first"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )
    first = build_constraint(ConstraintId("first"), _length_requirement(), (first_capability,))

    second_requirement = SequenceLengthRequirement(
        id=RequirementId("req-second"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr2",
        length=5,
    )
    second_capability = SequenceLengthCapability(
        id=CapabilityId("second"), resource_id=_ANCHOR, sequence_name="chr2", length=5
    )
    second = build_constraint(ConstraintId("second"), second_requirement, (second_capability,))

    aggregate = aggregate_constraint_evidence(
        (first, second),
        (evaluate_constraint(second), evaluate_constraint(first)),
    )

    assert tuple(item.constraint_id for item in aggregate.evidence) == (
        ConstraintId("first"),
        ConstraintId("second"),
    )


def test_aggregation_rejects_mismatched_or_incoherent_evaluations() -> None:
    capability = SequenceLengthCapability(
        id=CapabilityId("length"), resource_id=_ANCHOR, sequence_name="chr1", length=5
    )
    constraint = build_constraint(ConstraintId("length"), _length_requirement(), (capability,))

    missing = ConstraintEvaluation(
        constraint_id=ConstraintId("other"),
        requirement_id=RequirementId("other"),
        state=ConstraintState.UNRESOLVED,
    )
    with pytest.raises(ValueError, match="exactly one evaluation"):
        aggregate_constraint_evidence((constraint,), (missing,))

    falsely_satisfied = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.SATISFIED,
        satisfaction_mode=SatisfactionMode.EXACT,
        relevant_capability_ids=(capability.id,),
    )
    with pytest.raises(ValueError, match="supporting evidence"):
        aggregate_constraint_evidence((constraint,), (falsely_satisfied,))


def test_derive_evidence_rejects_evaluation_for_different_constraint() -> None:
    capability = SequenceLengthCapability(
        id=CapabilityId("length"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )
    constraint = build_constraint(ConstraintId("length"), _length_requirement(), (capability,))
    evaluation = ConstraintEvaluation(
        constraint_id=ConstraintId("other"),
        requirement_id=constraint.requirement.id,
        state=ConstraintState.UNRESOLVED,
    )

    with pytest.raises(ValueError, match="does not belong to the supplied constraint"):
        derive_constraint_evidence(constraint, evaluation)


def test_derive_evidence_rejects_capability_absent_from_constraint() -> None:
    capability = SequenceLengthCapability(
        id=CapabilityId("length"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )
    constraint = build_constraint(ConstraintId("length"), _length_requirement(), (capability,))
    evaluation = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.UNRESOLVED,
        relevant_capability_ids=(CapabilityId("missing"),),
    )

    with pytest.raises(ValueError, match="capability absent from its constraint"):
        derive_constraint_evidence(constraint, evaluation)


def test_not_applicable_state_is_retained_without_creating_a_verdict() -> None:
    constraint = CompatibilityConstraint(
        id=ConstraintId("na"),
        requirement=_length_requirement(),
        candidate_capabilities=(),
        rule=ConstraintRule.SEQUENCE_LENGTH,
    )
    evaluation = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.NOT_APPLICABLE,
    )

    aggregate = aggregate_constraint_evidence((constraint,), (evaluation,))

    assert aggregate.evidence == ()
    assert aggregate.not_applicable_constraint_ids == (ConstraintId("na"),)
