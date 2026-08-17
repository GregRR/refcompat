"""Unit tests for categorical verdict aggregation results."""

from __future__ import annotations

import pytest

from refcompat.model.constraints import ConstraintId
from refcompat.model.interpretation import ConditionId, FindingId
from refcompat.model.verdict import CompatibilityVerdict, VerdictAggregation

_C1 = ConstraintId("c1")
_C2 = ConstraintId("c2")
_FINDING = FindingId("finding")
_CONDITION = ConditionId("condition")


def test_compatible_requires_satisfied_mandatory_basis_without_conditions() -> None:
    result = VerdictAggregation(
        verdict=CompatibilityVerdict.COMPATIBLE,
        mandatory_constraint_ids=(_C1,),
        satisfied_mandatory_constraint_ids=(_C1,),
    )
    assert result.verdict is CompatibilityVerdict.COMPATIBLE

    with pytest.raises(ValueError, match="cannot carry conditions"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.COMPATIBLE,
            mandatory_constraint_ids=(_C1,),
            satisfied_mandatory_constraint_ids=(_C1,),
            condition_ids=(_CONDITION,),
        )


def test_conditional_compatible_requires_explicit_condition() -> None:
    with pytest.raises(ValueError, match="requires an explicit condition"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
            mandatory_constraint_ids=(_C1,),
            satisfied_mandatory_constraint_ids=(_C1,),
        )


def test_incompatible_requires_unsatisfied_constraint_and_finding() -> None:
    with pytest.raises(ValueError, match="requires an unsatisfied mandatory"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.INCOMPATIBLE,
            mandatory_constraint_ids=(_C1,),
            unresolved_mandatory_constraint_ids=(_C1,),
            basis_finding_ids=(_FINDING,),
        )

    with pytest.raises(ValueError, match="traceable conflict finding"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.INCOMPATIBLE,
            mandatory_constraint_ids=(_C1,),
            unsatisfied_mandatory_constraint_ids=(_C1,),
        )


def test_indeterminate_allows_no_applicable_mandatory_constraints() -> None:
    assert (
        VerdictAggregation(
            verdict=CompatibilityVerdict.INDETERMINATE,
            mandatory_constraint_ids=(),
        ).mandatory_constraint_ids
        == ()
    )

    assert VerdictAggregation(
        verdict=CompatibilityVerdict.INDETERMINATE,
        mandatory_constraint_ids=(_C1,),
        not_applicable_mandatory_constraint_ids=(_C1,),
    ).not_applicable_mandatory_constraint_ids == (_C1,)

    with pytest.raises(ValueError, match="cannot cite basis findings"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.INDETERMINATE,
            mandatory_constraint_ids=(),
            basis_finding_ids=(_FINDING,),
        )


def test_state_partitions_must_be_disjoint_and_complete() -> None:
    with pytest.raises(ValueError, match="must be disjoint"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.INCOMPATIBLE,
            mandatory_constraint_ids=(_C1,),
            satisfied_mandatory_constraint_ids=(_C1,),
            unsatisfied_mandatory_constraint_ids=(_C1,),
            basis_finding_ids=(_FINDING,),
        )

    with pytest.raises(ValueError, match="must cover all mandatory"):
        VerdictAggregation(
            verdict=CompatibilityVerdict.INDETERMINATE,
            mandatory_constraint_ids=(_C1, _C2),
            unresolved_mandatory_constraint_ids=(_C1,),
            basis_finding_ids=(_FINDING,),
        )
