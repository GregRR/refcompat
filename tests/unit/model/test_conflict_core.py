"""Unit tests for minimal decisive conflict-core models."""

from __future__ import annotations

import pytest

from refcompat.model.conflict_core import (
    ConflictCore,
    ConflictCoreExtraction,
    ConflictCoreId,
    ConflictCoreKind,
)
from refcompat.model.constraints import ConstraintId
from refcompat.model.contracts import RequirementId
from refcompat.model.evidence import EvidenceId
from refcompat.model.interpretation import FindingId
from refcompat.model.resources import ResourceId
from refcompat.model.verdict import CompatibilityVerdict


def _core(*, kind: ConflictCoreKind = ConflictCoreKind.CONTRADICTION) -> ConflictCore:
    return ConflictCore(
        id=ConflictCoreId("core"),
        kind=kind,
        constraint_ids=(ConstraintId("constraint"),),
        requirement_ids=(RequirementId("requirement"),),
        finding_ids=(FindingId("finding"),),
        evidence_ids=(EvidenceId("evidence"),) if kind is ConflictCoreKind.CONTRADICTION else (),
        resource_ids=(ResourceId("resource"),),
    )


def test_contradiction_core_requires_traceable_evidence() -> None:
    with pytest.raises(ValueError, match="requires traceable evidence"):
        ConflictCore(
            id=ConflictCoreId("core"),
            kind=ConflictCoreKind.CONTRADICTION,
            constraint_ids=(ConstraintId("constraint"),),
            requirement_ids=(RequirementId("requirement"),),
            finding_ids=(FindingId("finding"),),
            evidence_ids=(),
            resource_ids=(ResourceId("resource"),),
        )


def test_unresolved_core_may_have_no_evidence() -> None:
    core = _core(kind=ConflictCoreKind.UNRESOLVED)
    assert core.evidence_ids == ()


def test_conflict_core_rejects_duplicate_trace_ids() -> None:
    with pytest.raises(ValueError, match="constraint IDs must be unique"):
        ConflictCore(
            id=ConflictCoreId("core"),
            kind=ConflictCoreKind.UNRESOLVED,
            constraint_ids=(ConstraintId("constraint"), ConstraintId("constraint")),
            requirement_ids=(RequirementId("requirement"),),
            finding_ids=(FindingId("finding"),),
            evidence_ids=(),
            resource_ids=(ResourceId("resource"),),
        )


def test_positive_extraction_cannot_carry_conflict_cores() -> None:
    with pytest.raises(ValueError, match="positive verdict cannot carry conflict cores"):
        ConflictCoreExtraction(
            verdict=CompatibilityVerdict.COMPATIBLE,
            decisive_constraint_ids=(ConstraintId("constraint"),),
            cores=(_core(),),
        )


def test_incompatible_extraction_requires_contradiction_core() -> None:
    core = _core()
    result = ConflictCoreExtraction(
        verdict=CompatibilityVerdict.INCOMPATIBLE,
        decisive_constraint_ids=core.constraint_ids,
        cores=(core,),
    )
    assert result.cores == (core,)


def test_indeterminate_without_applicable_basis_allows_no_core() -> None:
    result = ConflictCoreExtraction(verdict=CompatibilityVerdict.INDETERMINATE)
    assert result.decisive_constraint_ids == ()
    assert result.cores == ()


def test_extraction_requires_exact_decisive_constraint_coverage() -> None:
    core = _core()
    with pytest.raises(ValueError, match="cover exactly the decisive constraints"):
        ConflictCoreExtraction(
            verdict=CompatibilityVerdict.INCOMPATIBLE,
            decisive_constraint_ids=(ConstraintId("different"),),
            cores=(core,),
        )


def test_indeterminate_decisive_core_must_be_unresolved() -> None:
    core = _core()
    with pytest.raises(ValueError, match="only unresolved cores"):
        ConflictCoreExtraction(
            verdict=CompatibilityVerdict.INDETERMINATE,
            decisive_constraint_ids=core.constraint_ids,
            cores=(core,),
        )
