"""Format-neutral directly observed resource facts and source locations.

Observations preserve facts extracted from supplied resources without adding
compatibility conclusions. Format-specific inspectors may expose richer
immutable models, while this vocabulary provides the traceability primitive
that later evidence and report layers can reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat.model.resources import ResourceId

ObservationId = NewType("ObservationId", str)
ObservationKind = NewType("ObservationKind", str)
type ObservationValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Format-neutral location of an observation within a supplied resource.

    An inspector may identify a 1-based source line, a 0-based logical record
    index, a field/tag name, a human-readable locator, or a useful combination
    of those values.
    """

    line_number: int | None = None
    record_index: int | None = None
    field: str | None = None
    locator: str | None = None

    def __post_init__(self) -> None:
        if self.line_number is not None and self.line_number < 1:
            raise ValueError("source line number must be positive")
        if self.record_index is not None and self.record_index < 0:
            raise ValueError("source record index must not be negative")
        if self.field is not None and not self.field:
            raise ValueError("source field must not be empty")
        if self.locator is not None and not self.locator:
            raise ValueError("source locator must not be empty")
        if all(
            value is None
            for value in (self.line_number, self.record_index, self.field, self.locator)
        ):
            raise ValueError("source location must identify at least one location component")


@dataclass(frozen=True, slots=True)
class ResourceObservation:
    """One immutable fact directly extracted from a supplied resource.

    ``kind`` is an inspector-owned fact label rather than a compatibility
    conclusion. Milestone 1 intentionally leaves observation-ID generation to
    the evaluation/report owner instead of freezing an ID scheme before the
    generalized evidence graph exists.
    """

    id: ObservationId
    resource_id: ResourceId
    kind: ObservationKind
    value: ObservationValue
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("observation ID must not be empty")
        if not self.resource_id:
            raise ValueError("observation resource ID must not be empty")
        if not self.kind:
            raise ValueError("observation kind must not be empty")
