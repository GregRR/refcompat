"""Minimal decisive failure cores for categorical bundle verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat._compat import StrEnum, assert_never
from refcompat.model.constraints import ConstraintId
from refcompat.model.contracts import RequirementId
from refcompat.model.evidence import EvidenceId
from refcompat.model.interpretation import FindingId
from refcompat.model.resources import ResourceId
from refcompat.model.verdict import CompatibilityVerdict

ConflictCoreId = NewType("ConflictCoreId", str)


class ConflictCoreKind(StrEnum):
    """Decisive non-positive relationship represented by one compact core."""

    CONTRADICTION = "contradiction"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ConflictCore:
    """Smallest useful trace currently available for one decisive finding.

    The core intentionally keeps only direct trace identifiers. Evidence items
    retain their own capability, observation, and sequence-binding provenance,
    so those transitive objects are not duplicated here.
    """

    id: ConflictCoreId
    kind: ConflictCoreKind
    constraint_ids: tuple[ConstraintId, ...]
    requirement_ids: tuple[RequirementId, ...]
    finding_ids: tuple[FindingId, ...]
    evidence_ids: tuple[EvidenceId, ...]
    resource_ids: tuple[ResourceId, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("conflict-core ID must not be empty")
        _validate_nonempty_unique(self.constraint_ids, noun="conflict-core constraint IDs")
        _validate_nonempty_unique(self.requirement_ids, noun="conflict-core requirement IDs")
        _validate_nonempty_unique(self.finding_ids, noun="conflict-core finding IDs")
        _validate_unique(self.evidence_ids, noun="conflict-core evidence IDs")
        _validate_nonempty_unique(self.resource_ids, noun="conflict-core resource IDs")
        if self.kind is ConflictCoreKind.CONTRADICTION and not self.evidence_ids:
            raise ValueError("contradiction conflict core requires traceable evidence")


@dataclass(frozen=True, slots=True)
class ConflictCoreExtraction:
    """Conflict-core extraction for one already-aggregated bundle verdict.

    ``decisive_constraint_ids`` mirrors only the mandatory constraints that
    determined a non-positive verdict. Positive verdicts have no decisive
    constraints or cores. An indeterminate result caused solely by absence of
    any applicable mandatory basis also has no evidence core.
    """

    verdict: CompatibilityVerdict
    decisive_constraint_ids: tuple[ConstraintId, ...] = ()
    cores: tuple[ConflictCore, ...] = ()

    def __post_init__(self) -> None:
        _validate_unique(
            self.decisive_constraint_ids,
            noun="conflict-core decisive constraint IDs",
        )
        core_ids = tuple(core.id for core in self.cores)
        _validate_unique(core_ids, noun="conflict-core IDs")

        covered = {constraint_id for core in self.cores for constraint_id in core.constraint_ids}
        if covered != set(self.decisive_constraint_ids):
            raise ValueError("conflict cores must cover exactly the decisive constraints")

        if self.verdict in (
            CompatibilityVerdict.COMPATIBLE,
            CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
        ):
            if self.decisive_constraint_ids or self.cores:
                raise ValueError("positive verdict cannot carry conflict cores")
            return

        if self.verdict is CompatibilityVerdict.INCOMPATIBLE:
            if not self.decisive_constraint_ids or not self.cores:
                raise ValueError("incompatible verdict requires contradiction conflict cores")
            if any(core.kind is not ConflictCoreKind.CONTRADICTION for core in self.cores):
                raise ValueError("incompatible verdict may carry only contradiction cores")
            return

        if self.verdict is CompatibilityVerdict.INDETERMINATE:
            if self.decisive_constraint_ids:
                if not self.cores:
                    raise ValueError("unresolved indeterminate verdict requires conflict cores")
                if any(core.kind is not ConflictCoreKind.UNRESOLVED for core in self.cores):
                    raise ValueError("indeterminate verdict may carry only unresolved cores")
            elif self.cores:
                raise ValueError(
                    "indeterminate verdict without decisive constraints cannot carry conflict cores"
                )
            return

        assert_never(self.verdict)


def _validate_nonempty_unique(values: tuple[object, ...], *, noun: str) -> None:
    if not values:
        raise ValueError(f"{noun} must not be empty")
    _validate_unique(values, noun=noun)


def _validate_unique(values: tuple[object, ...], *, noun: str) -> None:
    if any(not value for value in values):
        raise ValueError(f"{noun} must not contain empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{noun} must be unique")
