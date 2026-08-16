"""Unit tests for constraint/evaluation model invariants."""

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
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.identity import Md5Digest, RefgetSequenceId
from refcompat.model.resources import ResourceId

_RESOURCE = ResourceId("reference")


def _requirement() -> SequencePresenceRequirement:
    return SequencePresenceRequirement(
        id=RequirementId("req"),
        resource_id=_RESOURCE,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
    )


def _capability(capability_id: str = "cap") -> SequencePresenceCapability:
    return SequencePresenceCapability(
        id=CapabilityId(capability_id),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        present=True,
    )


def test_constraint_keeps_question_separate_from_evaluation() -> None:
    constraint = CompatibilityConstraint(
        id=ConstraintId("constraint"),
        requirement=_requirement(),
        candidate_capabilities=(_capability(),),
        rule=ConstraintRule.SEQUENCE_PRESENCE,
    )
    evaluation = ConstraintEvaluation(
        constraint_id=constraint.id,
        requirement_id=constraint.requirement.id,
        state=ConstraintState.SATISFIED,
        satisfaction_mode=SatisfactionMode.EXACT,
        relevant_capability_ids=(CapabilityId("cap"),),
    )

    assert evaluation.constraint_id == constraint.id
    assert evaluation.state is ConstraintState.SATISFIED


def test_constraint_rejects_duplicate_candidate_capability_ids() -> None:
    with pytest.raises(ValueError, match="candidate capability IDs must be unique"):
        CompatibilityConstraint(
            id=ConstraintId("constraint"),
            requirement=_requirement(),
            candidate_capabilities=(_capability("same"), _capability("same")),
            rule=ConstraintRule.SEQUENCE_PRESENCE,
        )


def test_satisfied_evaluation_requires_mode_and_relevant_capability() -> None:
    with pytest.raises(ValueError, match="requires a satisfaction mode"):
        ConstraintEvaluation(
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("req"),
            state=ConstraintState.SATISFIED,
            relevant_capability_ids=(CapabilityId("cap"),),
        )

    with pytest.raises(ValueError, match="requires a relevant capability"):
        ConstraintEvaluation(
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("req"),
            state=ConstraintState.SATISFIED,
            satisfaction_mode=SatisfactionMode.EXACT,
        )


def test_non_satisfied_evaluation_cannot_claim_satisfaction_mode() -> None:
    with pytest.raises(ValueError, match="only satisfied"):
        ConstraintEvaluation(
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("req"),
            state=ConstraintState.UNSATISFIED,
            satisfaction_mode=SatisfactionMode.EXACT,
        )


def test_constraint_rejects_rule_or_capability_type_mismatch() -> None:
    presence = _requirement()
    with pytest.raises(ValueError, match="rule must match"):
        CompatibilityConstraint(
            id=ConstraintId("wrong-rule"),
            requirement=presence,
            candidate_capabilities=(_capability(),),
            rule=ConstraintRule.SEQUENCE_LENGTH,
        )

    length = SequenceLengthCapability(
        id=CapabilityId("length"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        length=4,
    )
    with pytest.raises(ValueError, match="capabilities must match"):
        CompatibilityConstraint(
            id=ConstraintId("wrong-capability"),
            requirement=presence,
            candidate_capabilities=(length,),
            rule=ConstraintRule.SEQUENCE_PRESENCE,
        )


def test_constraint_rejects_identity_scheme_mismatch() -> None:
    requirement = SequenceIdentityRequirement(
        id=RequirementId("req-identity"),
        resource_id=_RESOURCE,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        identity=RefgetSequenceId("SQ.01234567890123456789012345678901"),
    )
    md5 = SequenceIdentityCapability(
        id=CapabilityId("md5"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        identity=Md5Digest("f1f8f4bf413b16ad135722aa4591043e"),
    )

    with pytest.raises(ValueError, match="capabilities must match"):
        CompatibilityConstraint(
            id=ConstraintId("scheme-mismatch"),
            requirement=requirement,
            candidate_capabilities=(md5,),
            rule=ConstraintRule.SEQUENCE_IDENTITY,
        )


def test_unsatisfied_evaluation_requires_relevant_capability() -> None:
    with pytest.raises(ValueError, match=r"unsatisfied.*relevant capability"):
        ConstraintEvaluation(
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("req"),
            state=ConstraintState.UNSATISFIED,
        )


def test_not_applicable_evaluation_cannot_cite_candidate_capabilities() -> None:
    with pytest.raises(ValueError, match=r"not-applicable.*cannot cite"):
        ConstraintEvaluation(
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("req"),
            state=ConstraintState.NOT_APPLICABLE,
            relevant_capability_ids=(CapabilityId("cap"),),
        )
