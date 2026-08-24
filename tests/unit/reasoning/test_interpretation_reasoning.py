"""Unit tests for structured finding and explicit-scope interpretation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintId,
    ConstraintState,
)
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.evidence import EvidenceAggregate, EvidenceMethod, EvidencePolarity
from refcompat.model.identity import Md5Digest
from refcompat.model.interpretation import ConditionKind, FindingKind
from refcompat.model.reference_context import SequenceBindingId
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence
from refcompat.reasoning.interpretation import interpret_constraint_results

_CONSUMER = ResourceId("consumer")
_REFERENCE = ResourceId("reference")
_OTHER = ResourceId("other")
_MD5_A = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_B = Md5Digest("ca773511c152b8191d2757f5a45ff252")


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(
        id=resource_id,
        kind=kind,
        artifact=ArtifactIdentity(path=Path(f"/{resource_id}")),
    )


def _request(
    *,
    scoped_resources: tuple[ResourceId, ...] = (_REFERENCE, _CONSUMER, _OTHER),
    anchor_sequence_names: tuple[str, ...] | None = None,
) -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_CONSUMER, ResourceKind.VCF),
            _resource(_OTHER, ResourceKind.GTF),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope(
            resource_ids=scoped_resources,
            anchor_sequence_names=anchor_sequence_names,
        ),
    )


def _presence_requirement(
    *, level: RequirementLevel = RequirementLevel.MANDATORY
) -> SequencePresenceRequirement:
    return SequencePresenceRequirement(
        id=RequirementId("req-presence"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=level,
        sequence_name="chrX",
    )


def _pipeline(
    constraint: CompatibilityConstraint,
) -> tuple[ConstraintEvaluation, EvidenceAggregate]:
    evaluation = evaluate_constraint(constraint)
    aggregate = aggregate_constraint_evidence((constraint,), (evaluation,))
    return evaluation, aggregate


def test_missing_required_sequence_becomes_traceable_finding() -> None:
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_REFERENCE, sequence_name="chrX", present=False
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (absent,))
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert result.findings[0].kind is FindingKind.MISSING_REQUIRED_SEQUENCE
    assert result.findings[0].constraint_ids == (constraint.id,)
    assert result.findings[0].evidence_ids == (aggregate.evidence[0].id,)
    assert result.findings[0].resource_ids == (_CONSUMER, _REFERENCE)


@pytest.mark.parametrize(
    ("requirement", "capability", "expected_kind"),
    [
        (
            SequenceLengthRequirement(
                id=RequirementId("req-length"),
                resource_id=_CONSUMER,
                origin=RequirementOrigin.CORE_FORMAT,
                level=RequirementLevel.MANDATORY,
                sequence_name="chr1",
                length=4,
            ),
            SequenceLengthCapability(
                id=CapabilityId("length"), resource_id=_REFERENCE, sequence_name="chr1", length=5
            ),
            FindingKind.SEQUENCE_LENGTH_CONFLICT,
        ),
        (
            SequenceIdentityRequirement(
                id=RequirementId("req-identity"),
                resource_id=_CONSUMER,
                origin=RequirementOrigin.CORE_FORMAT,
                level=RequirementLevel.MANDATORY,
                sequence_name="chr1",
                identity=_MD5_A,
            ),
            SequenceIdentityCapability(
                id=CapabilityId("identity"),
                resource_id=_REFERENCE,
                sequence_name="chr1",
                identity=_MD5_B,
            ),
            FindingKind.SEQUENCE_IDENTITY_CONFLICT,
        ),
        (
            SequenceOrderRequirement(
                id=RequirementId("req-order"),
                resource_id=_CONSUMER,
                origin=RequirementOrigin.CORE_FORMAT,
                level=RequirementLevel.MANDATORY,
                sequence_names=("chr1", "chr2"),
            ),
            SequenceOrderCapability(
                id=CapabilityId("order"),
                resource_id=_REFERENCE,
                sequence_names=("chr2", "chr1"),
            ),
            FindingKind.SEQUENCE_ORDER_CONFLICT,
        ),
    ],
)
def test_unsatisfied_typed_constraints_map_to_specific_finding_kinds(
    requirement: Requirement, capability: Capability, expected_kind: FindingKind
) -> None:
    constraint = build_constraint(ConstraintId("constraint"), requirement, (capability,))
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert result.findings[0].kind is expected_kind


def test_reference_base_contradiction_maps_to_specific_finding_kind() -> None:
    requirement = ReferenceBaseRequirement(
        id=RequirementId("req-reference-bases"),
        resource_id=_CONSUMER,
        anchor_resource_id=_REFERENCE,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        record_count=10,
    )
    capability = ReferenceBaseValidationCapability(
        id=CapabilityId("reference-base-validation"),
        resource_id=_REFERENCE,
        subject_resource_id=_CONSUMER,
        checked_count=10,
        match_count=9,
        mismatch_count=1,
        unresolved_count=0,
    )
    constraint = build_constraint(ConstraintId("reference-bases"), requirement, (capability,))
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert result.findings[0].kind is FindingKind.REFERENCE_BASE_CONFLICT
    assert result.findings[0].resource_ids == (_CONSUMER, _REFERENCE)


def test_unresolved_missing_evidence_becomes_unresolved_finding_without_evidence() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    constraint = build_constraint(ConstraintId("length"), requirement, ())
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert evaluation.state is ConstraintState.UNRESOLVED
    assert result.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT
    assert result.findings[0].evidence_ids == ()
    assert result.findings[0].resource_ids == (_CONSUMER,)


def test_unresolved_conflicting_candidates_preserve_both_evidence_items() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    matching = SequenceLengthCapability(
        id=CapabilityId("matching"), resource_id=_REFERENCE, sequence_name="chr1", length=4
    )
    wrong = SequenceLengthCapability(
        id=CapabilityId("wrong"), resource_id=_REFERENCE, sequence_name="chr1", length=5
    )
    constraint = build_constraint(ConstraintId("length"), requirement, (matching, wrong))
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert result.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT
    assert result.findings[0].evidence_ids == tuple(item.id for item in aggregate.evidence)
    assert {item.polarity for item in aggregate.evidence} == {
        EvidencePolarity.SUPPORTS,
        EvidencePolarity.CONTRADICTS,
    }


def test_satisfied_constraint_does_not_create_generic_success_finding() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert evaluation.state is ConstraintState.SATISFIED
    assert result.findings == ()


def test_advisory_conflict_is_still_a_finding_not_a_verdict_policy_decision() -> None:
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_REFERENCE, sequence_name="chrX", present=False
    )
    constraint = build_constraint(
        ConstraintId("presence"),
        _presence_requirement(level=RequirementLevel.ADVISORY),
        (absent,),
    )
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert result.findings[0].kind is FindingKind.MISSING_REQUIRED_SEQUENCE


def test_explicit_resource_scope_creates_condition_with_excluded_resources() -> None:
    request = _request(scoped_resources=(_REFERENCE, _CONSUMER))

    result = interpret_constraint_results(request, (), (), EvidenceAggregate())

    assert len(result.conditions) == 1
    assert result.conditions[0].kind is ConditionKind.EXPLICIT_RESOURCE_SCOPE
    assert result.conditions[0].excluded_resource_ids == (_OTHER,)


def test_explicit_anchor_sequence_scope_creates_condition_without_inferring_exclusions() -> None:
    request = _request(anchor_sequence_names=("chr1", "chr2"))

    result = interpret_constraint_results(request, (), (), EvidenceAggregate())

    assert len(result.conditions) == 1
    assert result.conditions[0].kind is ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE
    assert result.conditions[0].anchor_resource_id == _REFERENCE
    assert result.conditions[0].scope.anchor_sequence_names == ("chr1", "chr2")
    assert result.conditions[0].excluded_resource_ids == ()


def test_both_explicit_scope_boundaries_are_preserved_deterministically() -> None:
    request = _request(scoped_resources=(_REFERENCE, _CONSUMER), anchor_sequence_names=("chr1",))

    first = interpret_constraint_results(request, (), (), EvidenceAggregate())
    second = interpret_constraint_results(request, (), (), EvidenceAggregate())

    assert first == second
    assert tuple(condition.kind for condition in first.conditions) == (
        ConditionKind.EXPLICIT_RESOURCE_SCOPE,
        ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE,
    )


def test_full_request_scope_creates_no_condition() -> None:
    result = interpret_constraint_results(_request(), (), (), EvidenceAggregate())

    assert result.conditions == ()


def test_interpretation_rejects_evidence_state_mismatch() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    constraint = build_constraint(ConstraintId("length"), requirement, ())
    evaluation = evaluate_constraint(constraint)
    wrong_aggregate = EvidenceAggregate()

    with pytest.raises(ValueError, match="unresolved constraints do not match"):
        interpret_constraint_results(_request(), (constraint,), (evaluation,), wrong_aggregate)


def test_interpretation_rejects_evidence_for_unknown_constraint() -> None:
    fake = EvidenceAggregate(
        evidence=(),
        unresolved_constraint_ids=(ConstraintId("unknown"),),
    )
    evaluation = ConstraintEvaluation(
        constraint_id=ConstraintId("unknown"),
        requirement_id=RequirementId("unknown"),
        state=ConstraintState.UNRESOLVED,
    )

    with pytest.raises(ValueError, match="exactly one evaluation"):
        interpret_constraint_results(_request(), (), (evaluation,), fake)


def test_interpretation_rejects_constraint_resources_outside_request_scope() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    capability = SequenceLengthCapability(
        id=CapabilityId("length"), resource_id=_OTHER, sequence_name="chr1", length=4
    )
    constraint = build_constraint(ConstraintId("length"), requirement, (capability,))
    evaluation, aggregate = _pipeline(constraint)
    request = _request(scoped_resources=(_REFERENCE, _CONSUMER))

    with pytest.raises(ValueError, match="capability resource is outside evaluation scope"):
        interpret_constraint_results(request, (constraint,), (evaluation,), aggregate)


def test_interpretation_rejects_requirement_resource_outside_request_scope() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_OTHER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    capability = SequenceLengthCapability(
        id=CapabilityId("length"), resource_id=_REFERENCE, sequence_name="chr1", length=4
    )
    constraint = build_constraint(ConstraintId("length"), requirement, (capability,))
    evaluation, aggregate = _pipeline(constraint)
    request = _request(scoped_resources=(_REFERENCE, _CONSUMER))

    with pytest.raises(ValueError, match="requirement resource is outside evaluation scope"):
        interpret_constraint_results(request, (constraint,), (evaluation,), aggregate)


def test_interpretation_rejects_satisfied_evaluation_without_supporting_evidence() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation = evaluate_constraint(constraint)

    with pytest.raises(ValueError, match="evidence does not match evaluator-relevant capabilities"):
        interpret_constraint_results(_request(), (constraint,), (evaluation,), EvidenceAggregate())


def test_not_applicable_constraint_creates_no_finding() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.NOT_APPLICABLE,
    )
    aggregate = EvidenceAggregate(not_applicable_constraint_ids=(constraint.id,))

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert result.findings == ()


def test_conflicting_presence_candidates_remain_unresolved_not_missing() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_REFERENCE, sequence_name="chrX", present=False
    )
    constraint = build_constraint(
        ConstraintId("presence"), _presence_requirement(), (present, absent)
    )
    evaluation, aggregate = _pipeline(constraint)

    result = interpret_constraint_results(_request(), (constraint,), (evaluation,), aggregate)

    assert evaluation.state is ConstraintState.UNRESOLVED
    assert result.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT
    assert {item.polarity for item in aggregate.evidence} == {
        EvidencePolarity.SUPPORTS,
        EvidencePolarity.CONTRADICTS,
    }


def test_interpretation_rejects_duplicate_constraint_ids() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)

    with pytest.raises(ValueError, match="constraints must have unique IDs"):
        interpret_constraint_results(_request(), (constraint, constraint), (evaluation,), aggregate)


def test_interpretation_rejects_duplicate_evaluation_constraint_ids() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)

    with pytest.raises(ValueError, match="evaluations must have unique constraint IDs"):
        interpret_constraint_results(_request(), (constraint,), (evaluation, evaluation), aggregate)


def test_interpretation_rejects_not_applicable_aggregate_state_mismatch() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.NOT_APPLICABLE,
    )

    with pytest.raises(ValueError, match="not-applicable constraints do not match"):
        interpret_constraint_results(_request(), (constraint,), (evaluation,), EvidenceAggregate())


def test_interpretation_rejects_evidence_from_unknown_constraint() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evidence = replace(aggregate.evidence[0], constraint_id=ConstraintId("unknown"))

    with pytest.raises(ValueError, match="constraint outside interpretation input"):
        interpret_constraint_results(
            _request(), (constraint,), (evaluation,), EvidenceAggregate(evidence=(wrong_evidence,))
        )


def test_interpretation_rejects_evidence_requirement_mismatch() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evidence = replace(aggregate.evidence[0], requirement_id=RequirementId("wrong"))

    with pytest.raises(ValueError, match="requirement ID does not match its constraint"):
        interpret_constraint_results(
            _request(), (constraint,), (evaluation,), EvidenceAggregate(evidence=(wrong_evidence,))
        )


def test_interpretation_rejects_evidence_capability_absent_from_constraint() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evidence = replace(aggregate.evidence[0], capability_id=CapabilityId("unknown"))

    with pytest.raises(ValueError, match="capability ID is absent from its constraint"):
        interpret_constraint_results(
            _request(), (constraint,), (evaluation,), EvidenceAggregate(evidence=(wrong_evidence,))
        )


def test_interpretation_rejects_evaluation_requirement_mismatch() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evaluation = replace(evaluation, requirement_id=RequirementId("wrong"))

    with pytest.raises(ValueError, match="evaluation requirement ID does not match constraint"):
        interpret_constraint_results(_request(), (constraint,), (wrong_evaluation,), aggregate)


def test_interpretation_rejects_satisfied_with_contradicting_evidence() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evidence = replace(aggregate.evidence[0], polarity=EvidencePolarity.CONTRADICTS)

    with pytest.raises(ValueError, match="satisfied interpretation requires only supporting"):
        interpret_constraint_results(
            _request(), (constraint,), (evaluation,), EvidenceAggregate(evidence=(wrong_evidence,))
        )


def test_interpretation_rejects_unsatisfied_with_supporting_evidence() -> None:
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_REFERENCE, sequence_name="chrX", present=False
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (absent,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evidence = replace(aggregate.evidence[0], polarity=EvidencePolarity.SUPPORTS)

    with pytest.raises(ValueError, match="unsatisfied finding requires only contradicting"):
        interpret_constraint_results(
            _request(), (constraint,), (evaluation,), EvidenceAggregate(evidence=(wrong_evidence,))
        )


def test_interpretation_rejects_not_applicable_with_evidence() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    _, aggregate = _pipeline(constraint)
    evaluation = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.NOT_APPLICABLE,
    )
    wrong_aggregate = EvidenceAggregate(
        evidence=aggregate.evidence,
        not_applicable_constraint_ids=(constraint.id,),
    )

    with pytest.raises(ValueError, match="not-applicable interpretation cannot carry evidence"):
        interpret_constraint_results(_request(), (constraint,), (evaluation,), wrong_aggregate)


def test_interpretation_rejects_evidence_binding_absent_from_constraint() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_REFERENCE, sequence_name="chrX", present=True
    )
    constraint = build_constraint(ConstraintId("presence"), _presence_requirement(), (present,))
    evaluation, aggregate = _pipeline(constraint)
    wrong_evidence = replace(
        aggregate.evidence[0],
        method=EvidenceMethod.VERIFIED_SEQUENCE_BINDING,
        sequence_binding_ids=(SequenceBindingId("unknown"),),
    )

    with pytest.raises(ValueError, match="sequence-binding ID is absent from its constraint"):
        interpret_constraint_results(
            _request(), (constraint,), (evaluation,), EvidenceAggregate(evidence=(wrong_evidence,))
        )
