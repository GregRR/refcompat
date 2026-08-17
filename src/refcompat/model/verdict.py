"""Categorical bundle verdict and traceable aggregation basis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from refcompat.model.constraints import ConstraintId
from refcompat.model.interpretation import ConditionId, FindingId


class CompatibilityVerdict(StrEnum):
    """Top-level categorical compatibility conclusion for one evaluation scope."""

    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_CONDITIONS = "compatible_with_conditions"
    INCOMPATIBLE = "incompatible"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class VerdictAggregation:
    """Traceable top-level verdict derived from mandatory constraint states.

    The state partitions retain the mandatory constraint IDs used by the
    aggregator. ``basis_finding_ids`` cites conflict/unresolved findings that
    materially determined an incompatible or indeterminate result. Conditions
    are preserved for scope traceability regardless of verdict, but only turn a
    positive conclusion into ``COMPATIBLE_WITH_CONDITIONS``.
    """

    verdict: CompatibilityVerdict
    mandatory_constraint_ids: tuple[ConstraintId, ...]
    satisfied_mandatory_constraint_ids: tuple[ConstraintId, ...] = ()
    unsatisfied_mandatory_constraint_ids: tuple[ConstraintId, ...] = ()
    unresolved_mandatory_constraint_ids: tuple[ConstraintId, ...] = ()
    not_applicable_mandatory_constraint_ids: tuple[ConstraintId, ...] = ()
    condition_ids: tuple[ConditionId, ...] = ()
    basis_finding_ids: tuple[FindingId, ...] = ()

    def __post_init__(self) -> None:
        _validate_unique(self.mandatory_constraint_ids, noun="mandatory constraint IDs")
        _validate_unique(
            self.satisfied_mandatory_constraint_ids,
            noun="satisfied mandatory constraint IDs",
        )
        _validate_unique(
            self.unsatisfied_mandatory_constraint_ids,
            noun="unsatisfied mandatory constraint IDs",
        )
        _validate_unique(
            self.unresolved_mandatory_constraint_ids,
            noun="unresolved mandatory constraint IDs",
        )
        _validate_unique(
            self.not_applicable_mandatory_constraint_ids,
            noun="not-applicable mandatory constraint IDs",
        )
        _validate_unique(self.condition_ids, noun="verdict condition IDs")
        _validate_unique(self.basis_finding_ids, noun="verdict basis finding IDs")

        state_groups = (
            set(self.satisfied_mandatory_constraint_ids),
            set(self.unsatisfied_mandatory_constraint_ids),
            set(self.unresolved_mandatory_constraint_ids),
            set(self.not_applicable_mandatory_constraint_ids),
        )
        if any(
            left & right
            for index, left in enumerate(state_groups)
            for right in state_groups[index + 1 :]
        ):
            raise ValueError("mandatory constraint state partitions must be disjoint")
        if set().union(*state_groups) != set(self.mandatory_constraint_ids):
            raise ValueError(
                "mandatory constraint state partitions must cover all mandatory constraints"
            )

        has_applicable = bool(
            self.satisfied_mandatory_constraint_ids
            or self.unsatisfied_mandatory_constraint_ids
            or self.unresolved_mandatory_constraint_ids
        )
        if self.verdict is CompatibilityVerdict.INCOMPATIBLE:
            if not self.unsatisfied_mandatory_constraint_ids:
                raise ValueError(
                    "incompatible verdict requires an unsatisfied mandatory constraint"
                )
            if not self.basis_finding_ids:
                raise ValueError("incompatible verdict requires a traceable conflict finding")
            return

        if self.unsatisfied_mandatory_constraint_ids:
            raise ValueError(
                "only an incompatible verdict may carry unsatisfied mandatory constraints"
            )

        if self.verdict is CompatibilityVerdict.INDETERMINATE:
            if has_applicable and not self.unresolved_mandatory_constraint_ids:
                raise ValueError(
                    "indeterminate verdict with applicable mandatory constraints "
                    "requires unresolved state"
                )
            if self.unresolved_mandatory_constraint_ids and not self.basis_finding_ids:
                raise ValueError("unresolved indeterminate verdict requires a traceable finding")
            if not has_applicable and self.basis_finding_ids:
                raise ValueError(
                    "indeterminate verdict without applicable mandatory constraints "
                    "cannot cite basis findings"
                )
            return

        if self.unresolved_mandatory_constraint_ids:
            raise ValueError("positive verdict cannot carry unresolved mandatory constraints")
        if not self.satisfied_mandatory_constraint_ids:
            raise ValueError(
                "positive verdict requires a satisfied applicable mandatory constraint"
            )
        if self.basis_finding_ids:
            raise ValueError("positive verdict cannot cite conflict/unresolved basis findings")

        if self.verdict is CompatibilityVerdict.COMPATIBLE:
            if self.condition_ids:
                raise ValueError("unconditional compatible verdict cannot carry conditions")
            return
        if self.verdict is CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS:
            if not self.condition_ids:
                raise ValueError("conditional compatible verdict requires an explicit condition")
            return
        assert_never(self.verdict)


def _validate_unique(values: tuple[object, ...], *, noun: str) -> None:
    if any(not value for value in values):
        raise ValueError(f"{noun} must not contain empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{noun} must be unique")
