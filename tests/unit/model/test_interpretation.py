"""Unit tests for structured findings and explicit-scope conditions."""

from __future__ import annotations

import pytest

from refcompat.model.constraints import ConstraintId
from refcompat.model.contracts import RequirementId
from refcompat.model.evaluation import EvaluationScope
from refcompat.model.evidence import EvidenceId
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


def test_conflict_finding_requires_traceable_evidence() -> None:
    with pytest.raises(ValueError, match="conflict finding requires"):
        CompatibilityFinding(
            id=FindingId("finding"),
            kind=FindingKind.SEQUENCE_IDENTITY_CONFLICT,
            constraint_ids=(ConstraintId("constraint"),),
            requirement_ids=(RequirementId("requirement"),),
            evidence_ids=(),
            resource_ids=(ResourceId("consumer"), ResourceId("reference")),
        )


def test_unresolved_finding_may_have_no_evidence() -> None:
    finding = CompatibilityFinding(
        id=FindingId("finding"),
        kind=FindingKind.UNRESOLVED_REQUIREMENT,
        constraint_ids=(ConstraintId("constraint"),),
        requirement_ids=(RequirementId("requirement"),),
        evidence_ids=(),
        resource_ids=(ResourceId("consumer"),),
    )

    assert finding.evidence_ids == ()


def test_finding_rejects_duplicate_trace_ids() -> None:
    with pytest.raises(ValueError, match="finding evidence IDs must be unique"):
        CompatibilityFinding(
            id=FindingId("finding"),
            kind=FindingKind.MISSING_REQUIRED_SEQUENCE,
            constraint_ids=(ConstraintId("constraint"),),
            requirement_ids=(RequirementId("requirement"),),
            evidence_ids=(EvidenceId("evidence"), EvidenceId("evidence")),
            resource_ids=(ResourceId("consumer"),),
        )


def test_resource_scope_condition_requires_real_exclusion() -> None:
    scope = EvaluationScope(resource_ids=(ResourceId("reference"),))

    with pytest.raises(ValueError, match="requires excluded resources"):
        CompatibilityCondition(
            id=ConditionId("condition"),
            kind=ConditionKind.EXPLICIT_RESOURCE_SCOPE,
            scope=scope,
            anchor_resource_id=ResourceId("reference"),
        )

    with pytest.raises(ValueError, match="exclusions must be outside scope"):
        CompatibilityCondition(
            id=ConditionId("condition"),
            kind=ConditionKind.EXPLICIT_RESOURCE_SCOPE,
            scope=scope,
            anchor_resource_id=ResourceId("reference"),
            excluded_resource_ids=(ResourceId("reference"),),
        )


def test_anchor_sequence_condition_requires_explicit_sequence_scope() -> None:
    scope = EvaluationScope(resource_ids=(ResourceId("reference"),))

    with pytest.raises(ValueError, match="requires explicit sequence scope"):
        CompatibilityCondition(
            id=ConditionId("condition"),
            kind=ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE,
            scope=scope,
            anchor_resource_id=ResourceId("reference"),
        )


def test_interpretation_result_rejects_duplicate_ids() -> None:
    finding = CompatibilityFinding(
        id=FindingId("finding"),
        kind=FindingKind.UNRESOLVED_REQUIREMENT,
        constraint_ids=(ConstraintId("constraint"),),
        requirement_ids=(RequirementId("requirement"),),
        evidence_ids=(),
        resource_ids=(ResourceId("consumer"),),
    )

    with pytest.raises(ValueError, match="finding IDs must be unique"):
        InterpretationResult(findings=(finding, finding))


def test_condition_requires_anchor_inside_scope() -> None:
    scope = EvaluationScope(resource_ids=(ResourceId("reference"),))

    with pytest.raises(ValueError, match="anchor resource must be inside"):
        CompatibilityCondition(
            id=ConditionId("condition"),
            kind=ConditionKind.EXPLICIT_RESOURCE_SCOPE,
            scope=scope,
            anchor_resource_id=ResourceId("other"),
            excluded_resource_ids=(ResourceId("other"),),
        )
