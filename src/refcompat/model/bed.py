"""BED-specific immutable observation values.

BED coordinates remain in their native zero-based, half-open form. These
values describe parsed facts only; they do not resolve sequence names against
a FASTA anchor or decide compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import StrEnum
from refcompat.model.resources import ResourceId, ResourceKind

_BED_COORDINATE_MAX = (1 << 64) - 1


class BedLayout(StrEnum):
    """Explicit standard BED layouts supported by the Milestone 9 contract.

    BED has no in-band schema marker, so callers must select one of these
    layouts rather than asking an inspector to infer standard field meaning
    from a row's column count. BED10 and BED11 are intentionally absent because
    BEDv1 permits block fields only as the complete BED12 group.
    """

    BED3 = "bed3"
    BED4 = "bed4"
    BED5 = "bed5"
    BED6 = "bed6"
    BED7 = "bed7"
    BED8 = "bed8"
    BED9 = "bed9"
    BED12 = "bed12"

    @property
    def field_count(self) -> int:
        """Return the exact number of standard fields in this layout."""

        return int(self.value.removeprefix("bed"))


@dataclass(frozen=True, slots=True)
class BedFeatureRecord:
    """One streamed BED feature with reference-coordinate fields only."""

    resource_id: ResourceId
    ordinal: int
    line_number: int
    chrom: str
    chrom_start: int
    chrom_end: int
    thick_start: int | None = None
    thick_end: int | None = None
    block_sizes: tuple[int, ...] = ()
    block_starts: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("BED feature resource ID must not be empty")
        if self.ordinal < 0:
            raise ValueError("BED feature ordinal must not be negative")
        if self.line_number < 1:
            raise ValueError("BED feature line number must be positive")
        if not self.chrom:
            raise ValueError("BED feature chrom must not be empty")
        if self.chrom_start < 0 or self.chrom_end < 0:
            raise ValueError("BED feature coordinates must not be negative")
        if self.chrom_start > _BED_COORDINATE_MAX or self.chrom_end > _BED_COORDINATE_MAX:
            raise ValueError("BED feature coordinates must fit unsigned 64-bit integers")
        if self.chrom_start > self.chrom_end:
            raise ValueError("BED feature start must not exceed end")

        if self.thick_start is not None and not (
            self.chrom_start <= self.thick_start <= self.chrom_end
        ):
            raise ValueError("BED thick start must lie within the feature")
        if self.thick_end is not None:
            if self.thick_start is None:
                raise ValueError("BED thick end requires thick start")
            if not self.thick_start <= self.thick_end <= self.chrom_end:
                raise ValueError("BED thick end must lie after thick start within the feature")

        if bool(self.block_sizes) != bool(self.block_starts):
            raise ValueError("BED block sizes and starts must be supplied together")
        if len(self.block_sizes) != len(self.block_starts):
            raise ValueError("BED block sizes and starts must have equal lengths")
        if self.block_sizes:
            self._validate_blocks()

    def _validate_blocks(self) -> None:
        span = self.chrom_end - self.chrom_start
        if len(self.block_sizes) > span:
            raise ValueError("BED block count must not exceed feature length")
        if any(size < 0 for size in self.block_sizes):
            raise ValueError("BED block sizes must not be negative")
        if any(start < 0 for start in self.block_starts):
            raise ValueError("BED block starts must not be negative")
        if self.block_starts[0] != 0:
            raise ValueError("first BED block must start at the feature start")

        previous_end = 0
        for start, size in zip(self.block_starts, self.block_sizes, strict=True):
            block_end = start + size
            if block_end > span:
                raise ValueError("BED block must remain within the feature")
            if start < previous_end:
                raise ValueError("BED blocks must be ordered and non-overlapping")
            previous_end = block_end
        if previous_end != span:
            raise ValueError("last BED block must end at the feature end")

    @property
    def is_zero_length(self) -> bool:
        """Whether the feature represents a valid boundary position."""

        return self.chrom_start == self.chrom_end

    @property
    def block_count(self) -> int:
        """Return the number of parsed BED12 blocks."""

        return len(self.block_sizes)


@dataclass(frozen=True, slots=True)
class BedSequenceUsage:
    """Compact streaming summary for one BED ``chrom`` value."""

    chrom: str
    feature_count: int
    minimum_start: int
    maximum_end: int
    first_feature_line: int
    zero_length_feature_count: int = 0

    def __post_init__(self) -> None:
        if not self.chrom:
            raise ValueError("BED usage chrom must not be empty")
        if self.feature_count < 1:
            raise ValueError("BED usage feature count must be positive")
        if self.minimum_start < 0 or self.maximum_end < 0:
            raise ValueError("BED usage coordinates must not be negative")
        if self.minimum_start > _BED_COORDINATE_MAX or self.maximum_end > _BED_COORDINATE_MAX:
            raise ValueError("BED usage coordinates must fit unsigned 64-bit integers")
        if self.minimum_start > self.maximum_end:
            raise ValueError("BED usage minimum start must not exceed maximum end")
        if self.first_feature_line < 1:
            raise ValueError("BED usage first feature line must be positive")
        if not 0 <= self.zero_length_feature_count <= self.feature_count:
            raise ValueError("BED zero-length count must be within feature count")


@dataclass(frozen=True, slots=True)
class BedContextSnapshot:
    """Compact native-coordinate observations from one BED resource."""

    resource_id: ResourceId
    resource_kind: ResourceKind
    layout: BedLayout
    feature_count: int
    sequence_usage: tuple[BedSequenceUsage, ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("BED snapshot resource ID must not be empty")
        if self.resource_kind is not ResourceKind.BED:
            raise ValueError("BED snapshot requires a BED resource kind")
        if not isinstance(self.layout, BedLayout):
            raise ValueError("BED snapshot requires an explicit supported layout")
        if self.feature_count < 0:
            raise ValueError("BED feature count must not be negative")
        chroms = tuple(item.chrom for item in self.sequence_usage)
        if len(set(chroms)) != len(chroms):
            raise ValueError("BED sequence usage chrom values must be unique")
        if sum(item.feature_count for item in self.sequence_usage) != self.feature_count:
            raise ValueError("BED sequence usage counts must sum to feature count")
        if self.feature_count == 0 and self.sequence_usage:
            raise ValueError("empty BED feature stream cannot have sequence usage")

    @property
    def used_sequence_names(self) -> tuple[str, ...]:
        """BED ``chrom`` values in first-observed feature order."""

        return tuple(item.chrom for item in self.sequence_usage)
