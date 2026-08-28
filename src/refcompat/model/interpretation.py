"""Structured findings and explicit-scope conditions.

This layer interprets already-evaluated constraints and evidence without
assigning a whole-bundle compatibility verdict. Findings summarize concrete
conflicts or unresolved questions. Conditions record explicit request scope
that must bound any later compatibility claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat._compat import StrEnum, assert_never
from refcompat.model.constraints import ConstraintId
from refcompat.model.contracts import RequirementId
from refcompat.model.evaluation import EvaluationScope
from refcompat.model.evidence import EvidenceId
from refcompat.model.resources import ResourceId

FindingId = NewType("FindingId", str)
ConditionId = NewType("ConditionId", str)


class FindingKind(StrEnum):
    """Current structured interpretations of typed sequence constraints."""

    MISSING_REQUIRED_SEQUENCE = "missing_required_sequence"
    SEQUENCE_LENGTH_CONFLICT = "sequence_length_conflict"
    SEQUENCE_IDENTITY_CONFLICT = "sequence_identity_conflict"
    SEQUENCE_ORDER_CONFLICT = "sequence_order_conflict"
    COORDINATE_BOUNDS_CONFLICT = "coordinate_bounds_conflict"
    REFERENCE_BASE_CONFLICT = "reference_base_conflict"
    UNRESOLVED_REQUIREMENT = "unresolved_requirement"


class ConditionKind(StrEnum):
    """Explicit scope boundaries that constrain later compatibility claims."""

    EXPLICIT_RESOURCE_SCOPE = "explicit_resource_scope"
    EXPLICIT_ANCHOR_SEQUENCE_SCOPE = "explicit_anchor_sequence_scope"


@dataclass(frozen=True, slots=True)
class CompatibilityFinding:
    """One interpreted conflict or unresolved question with backward traceability.

    The current interpreter emits one finding per non-satisfied applicable
    constraint. The tuple-shaped references deliberately permit later
    interpretation layers to summarize several constraints into one finding
    without changing the model shape.
    """

    id: FindingId
    kind: FindingKind
    constraint_ids: tuple[ConstraintId, ...]
    requirement_ids: tuple[RequirementId, ...]
    evidence_ids: tuple[EvidenceId, ...]
    resource_ids: tuple[ResourceId, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("finding ID must not be empty")
        _validate_nonempty_unique(self.constraint_ids, noun="finding constraint IDs")
        _validate_nonempty_unique(self.requirement_ids, noun="finding requirement IDs")
        _validate_nonempty_unique(self.resource_ids, noun="finding resource IDs")
        _validate_unique(self.evidence_ids, noun="finding evidence IDs")

        if self.kind is not FindingKind.UNRESOLVED_REQUIREMENT and not self.evidence_ids:
            raise ValueError("conflict finding requires at least one evidence item")


@dataclass(frozen=True, slots=True)
class CompatibilityCondition:
    """Structured explicit scope boundary for a later compatibility claim.

    A condition records *where an evaluation was intentionally bounded*; it
    does not claim that compatibility was established inside that scope. The
    later bundle-verdict layer may cite these conditions when a positive result
    is valid only for the caller-selected resource or anchor-sequence scope.
    """

    id: ConditionId
    kind: ConditionKind
    scope: EvaluationScope
    anchor_resource_id: ResourceId
    constraint_ids: tuple[ConstraintId, ...] = ()
    excluded_resource_ids: tuple[ResourceId, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("condition ID must not be empty")
        if not self.anchor_resource_id:
            raise ValueError("condition anchor resource ID must not be empty")
        if self.anchor_resource_id not in self.scope.resource_ids:
            raise ValueError("condition anchor resource must be inside condition scope")
        _validate_unique(self.constraint_ids, noun="condition constraint IDs")
        _validate_unique(self.excluded_resource_ids, noun="condition excluded resource IDs")

        if self.kind is ConditionKind.EXPLICIT_RESOURCE_SCOPE:
            if not self.excluded_resource_ids:
                raise ValueError("resource-scope condition requires excluded resources")
            if set(self.excluded_resource_ids) & set(self.scope.resource_ids):
                raise ValueError("resource-scope condition exclusions must be outside scope")
            return
        if self.kind is ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE:
            if self.scope.anchor_sequence_names is None:
                raise ValueError("anchor-sequence condition requires explicit sequence scope")
            if self.excluded_resource_ids:
                raise ValueError("anchor-sequence condition cannot exclude resources")
            return
        assert_never(self.kind)


@dataclass(frozen=True, slots=True)
class InterpretationResult:
    """Structured interpretation below evidence aggregation and above verdicts."""

    findings: tuple[CompatibilityFinding, ...] = ()
    conditions: tuple[CompatibilityCondition, ...] = ()

    def __post_init__(self) -> None:
        finding_ids = tuple(finding.id for finding in self.findings)
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("interpretation finding IDs must be unique")
        condition_ids = tuple(condition.id for condition in self.conditions)
        if len(set(condition_ids)) != len(condition_ids):
            raise ValueError("interpretation condition IDs must be unique")


def _validate_nonempty_unique(values: tuple[object, ...], *, noun: str) -> None:
    if not values:
        raise ValueError(f"{noun} must not be empty")
    _validate_unique(values, noun=noun)


def _validate_unique(values: tuple[object, ...], *, noun: str) -> None:
    if any(not value for value in values):
        raise ValueError(f"{noun} must not contain empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{noun} must be unique")
