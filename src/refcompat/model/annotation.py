"""GTF/GFF3 reference-coordinate observations.

These immutable models preserve annotation facts needed by RCHECK-060 without
turning format metadata into reference authority or constructing gene-model
hierarchies. Feature coordinates remain in their native one-based closed form.
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat.model.resources import ResourceId, ResourceKind


@dataclass(frozen=True, slots=True)
class AnnotationFeatureRecord:
    """One streamed annotation feature with reference-relevant fields only."""

    resource_id: ResourceId
    ordinal: int
    line_number: int
    raw_sequence_name: str
    sequence_name: str
    feature_type: str
    start: int
    end: int
    is_circular: bool = False

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("annotation feature resource ID must not be empty")
        if self.ordinal < 0:
            raise ValueError("annotation feature ordinal must not be negative")
        if self.line_number < 1:
            raise ValueError("annotation feature line number must be positive")
        if not self.raw_sequence_name:
            raise ValueError("annotation feature raw sequence name must not be empty")
        if not self.sequence_name:
            raise ValueError("annotation feature sequence name must not be empty")
        if not self.feature_type:
            raise ValueError("annotation feature type must not be empty")
        if self.start < 1 or self.end < 1:
            raise ValueError("annotation feature coordinates must be positive")
        if self.start > self.end:
            raise ValueError("annotation feature start must not exceed end")


@dataclass(frozen=True, slots=True)
class AnnotationSequenceUsage:
    """Bounded streaming summary for one decoded/logical annotation seqid."""

    sequence_name: str
    first_raw_sequence_name: str
    feature_count: int
    minimum_start: int
    maximum_end: int
    first_feature_line: int
    has_multiple_raw_sequence_names: bool = False
    circular_feature_count: int = 0
    first_circular_feature_line: int | None = None

    def __post_init__(self) -> None:
        if not self.sequence_name:
            raise ValueError("annotation usage sequence name must not be empty")
        if not self.first_raw_sequence_name:
            raise ValueError("annotation usage raw sequence name must not be empty")
        if self.feature_count < 1:
            raise ValueError("annotation usage feature count must be positive")
        if self.minimum_start < 1 or self.maximum_end < 1:
            raise ValueError("annotation usage coordinates must be positive")
        if self.minimum_start > self.maximum_end:
            raise ValueError("annotation usage minimum start must not exceed maximum end")
        if self.first_feature_line < 1:
            raise ValueError("annotation usage first feature line must be positive")
        if not 0 <= self.circular_feature_count <= self.feature_count:
            raise ValueError("annotation circular feature count must be within feature count")
        if self.circular_feature_count == 0 and self.first_circular_feature_line is not None:
            raise ValueError("zero circular feature count cannot have a first circular line")
        if self.circular_feature_count > 0 and (
            self.first_circular_feature_line is None or self.first_circular_feature_line < 1
        ):
            raise ValueError("circular feature usage requires a positive first circular line")


@dataclass(frozen=True, slots=True)
class Gff3SequenceRegion:
    """One GFF3 ``##sequence-region`` declaration in native coordinates."""

    raw_sequence_name: str
    sequence_name: str
    start: int
    end: int
    line_number: int

    def __post_init__(self) -> None:
        if not self.raw_sequence_name:
            raise ValueError("GFF3 sequence-region raw sequence name must not be empty")
        if not self.sequence_name:
            raise ValueError("GFF3 sequence-region sequence name must not be empty")
        if self.start < 1 or self.end < 1:
            raise ValueError("GFF3 sequence-region coordinates must be positive")
        if self.start > self.end:
            raise ValueError("GFF3 sequence-region start must not exceed end")
        if self.line_number < 1:
            raise ValueError("GFF3 sequence-region line number must be positive")


@dataclass(frozen=True, slots=True)
class AnnotationProvenanceClaim:
    """One parser-recognized annotation provenance/header claim."""

    name: str
    value: str
    line_number: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("annotation provenance claim name must not be empty")
        if not self.value:
            raise ValueError("annotation provenance claim value must not be empty")
        if self.line_number < 1:
            raise ValueError("annotation provenance claim line number must be positive")


@dataclass(frozen=True, slots=True)
class Gff3FastaBoundary:
    """Location where annotation rows end and embedded FASTA begins."""

    line_number: int
    explicit_directive: bool

    def __post_init__(self) -> None:
        if self.line_number < 1:
            raise ValueError("GFF3 FASTA boundary line number must be positive")


@dataclass(frozen=True, slots=True)
class AnnotationContextSnapshot:
    """Compact reference-context observations from one GTF or GFF3 resource."""

    resource_id: ResourceId
    resource_kind: ResourceKind
    feature_count: int
    sequence_usage: tuple[AnnotationSequenceUsage, ...] = ()
    gff_version: str | None = None
    sequence_regions: tuple[Gff3SequenceRegion, ...] = ()
    provenance_claims: tuple[AnnotationProvenanceClaim, ...] = ()
    fasta_boundary: Gff3FastaBoundary | None = None

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("annotation snapshot resource ID must not be empty")
        if self.resource_kind not in (ResourceKind.GTF, ResourceKind.GFF3):
            raise ValueError("annotation snapshot requires a GTF or GFF3 resource kind")
        if self.feature_count < 0:
            raise ValueError("annotation feature count must not be negative")
        usage_names = tuple(item.sequence_name for item in self.sequence_usage)
        if len(set(usage_names)) != len(usage_names):
            raise ValueError("annotation sequence usage names must be unique")
        if sum(item.feature_count for item in self.sequence_usage) != self.feature_count:
            raise ValueError("annotation sequence usage counts must sum to feature count")
        if self.feature_count == 0 and self.sequence_usage:
            raise ValueError("empty annotation feature stream cannot have sequence usage")
        if self.resource_kind is ResourceKind.GTF and (
            self.gff_version is not None or self.sequence_regions or self.fasta_boundary is not None
        ):
            raise ValueError("GTF snapshot cannot contain GFF3-only observations")
        if self.resource_kind is ResourceKind.GTF and any(
            usage.circular_feature_count for usage in self.sequence_usage
        ):
            raise ValueError("GTF sequence usage cannot carry GFF3 Is_circular evidence")

    @property
    def used_sequence_names(self) -> tuple[str, ...]:
        """Decoded/logical seqids in first-observed feature order."""

        return tuple(item.sequence_name for item in self.sequence_usage)
