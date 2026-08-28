"""Exhaustive annotation-coordinate validation results.

These models retain annotation-specific local detail while the generic
compatibility layer consumes only aggregate coordinate-bounds capabilities.
Feature and GFF3 sequence-region coordinates remain in their native one-based
closed form.
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import StrEnum
from refcompat.model.annotation import AnnotationFeatureRecord, Gff3SequenceRegion
from refcompat.model.resources import ResourceId


class AnnotationCoordinateCheckState(StrEnum):
    """Outcome for one annotation feature against the selected FASTA anchor."""

    REPRESENTABLE = "representable"
    OUT_OF_BOUNDS = "out_of_bounds"
    UNRESOLVED_SEQUENCE = "unresolved_sequence"
    CIRCULAR_BOUNDS_UNRESOLVED = "circular_bounds_unresolved"


@dataclass(frozen=True, slots=True)
class AnnotationCoordinateCheck:
    """One non-mutating feature-coordinate check with local diagnostic context."""

    feature: AnnotationFeatureRecord
    state: AnnotationCoordinateCheckState
    anchor_sequence_name: str | None = None
    anchor_sequence_length: int | None = None

    def __post_init__(self) -> None:
        resolved_states = {
            AnnotationCoordinateCheckState.REPRESENTABLE,
            AnnotationCoordinateCheckState.OUT_OF_BOUNDS,
            AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED,
        }
        if self.state in resolved_states:
            if not self.anchor_sequence_name:
                raise ValueError("resolved annotation coordinate check requires an anchor name")
            if self.anchor_sequence_length is None or self.anchor_sequence_length < 0:
                raise ValueError("resolved annotation coordinate check requires anchor length")
        elif self.anchor_sequence_name is not None or self.anchor_sequence_length is not None:
            raise ValueError("unresolved annotation sequence cannot carry anchor coordinates")


class Gff3SequenceRegionCheckState(StrEnum):
    """Outcome for one GFF3 sequence-region declaration against the FASTA anchor."""

    REPRESENTABLE = "representable"
    OUT_OF_BOUNDS = "out_of_bounds"
    UNRESOLVED_SEQUENCE = "unresolved_sequence"


@dataclass(frozen=True, slots=True)
class Gff3SequenceRegionCheck:
    """One non-mutating GFF3 sequence-region check."""

    region: Gff3SequenceRegion
    state: Gff3SequenceRegionCheckState
    anchor_sequence_name: str | None = None
    anchor_sequence_length: int | None = None

    def __post_init__(self) -> None:
        if self.state in (
            Gff3SequenceRegionCheckState.REPRESENTABLE,
            Gff3SequenceRegionCheckState.OUT_OF_BOUNDS,
        ):
            if not self.anchor_sequence_name:
                raise ValueError("resolved sequence-region check requires an anchor name")
            if self.anchor_sequence_length is None or self.anchor_sequence_length < 0:
                raise ValueError("resolved sequence-region check requires anchor length")
        elif self.anchor_sequence_name is not None or self.anchor_sequence_length is not None:
            raise ValueError("unresolved sequence-region cannot carry anchor coordinates")


@dataclass(frozen=True, slots=True)
class Gff3SequenceRegionValidationResult:
    """Exhaustive checks for all GFF3 sequence-region declarations."""

    annotation_resource_id: ResourceId
    fasta_resource_id: ResourceId
    region_count: int
    representable_count: int
    out_of_bounds_count: int
    unresolved_sequence_count: int
    checks: tuple[Gff3SequenceRegionCheck, ...] = ()

    def __post_init__(self) -> None:
        if not self.annotation_resource_id:
            raise ValueError("sequence-region validation resource ID must not be empty")
        if not self.fasta_resource_id:
            raise ValueError("sequence-region validation FASTA resource ID must not be empty")
        counts = (
            self.region_count,
            self.representable_count,
            self.out_of_bounds_count,
            self.unresolved_sequence_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("sequence-region validation counts must not be negative")
        if (
            self.representable_count + self.out_of_bounds_count + self.unresolved_sequence_count
            != self.region_count
        ):
            raise ValueError("sequence-region validation outcomes must cover every directive")
        if len(self.checks) != self.region_count:
            raise ValueError("sequence-region validation must retain every directive check")
        names = tuple(check.region.sequence_name for check in self.checks)
        if len(set(names)) != len(names):
            raise ValueError("sequence-region validation seqids must be unique")
        state_counts = {
            state: sum(check.state is state for check in self.checks)
            for state in Gff3SequenceRegionCheckState
        }
        if state_counts != {
            Gff3SequenceRegionCheckState.REPRESENTABLE: self.representable_count,
            Gff3SequenceRegionCheckState.OUT_OF_BOUNDS: self.out_of_bounds_count,
            Gff3SequenceRegionCheckState.UNRESOLVED_SEQUENCE: self.unresolved_sequence_count,
        }:
            raise ValueError("sequence-region validation checks must match aggregate outcomes")

    @property
    def unresolved_count(self) -> int:
        """Sequence-region declarations whose anchor seqid could not be resolved."""

        return self.unresolved_sequence_count


@dataclass(frozen=True, slots=True)
class AnnotationCoordinateSequenceSummary:
    """Exhaustive feature-coordinate outcomes for one annotation-local seqid."""

    sequence_name: str
    feature_count: int
    representable_count: int = 0
    out_of_bounds_count: int = 0
    unresolved_sequence_count: int = 0
    circular_bounds_unresolved_count: int = 0

    def __post_init__(self) -> None:
        if not self.sequence_name:
            raise ValueError("annotation coordinate summary sequence name must not be empty")
        counts = (
            self.feature_count,
            self.representable_count,
            self.out_of_bounds_count,
            self.unresolved_sequence_count,
            self.circular_bounds_unresolved_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("annotation coordinate summary counts must not be negative")
        if (
            self.representable_count
            + self.out_of_bounds_count
            + self.unresolved_sequence_count
            + self.circular_bounds_unresolved_count
            != self.feature_count
        ):
            raise ValueError("annotation coordinate summary outcomes must cover every feature")

    @property
    def unresolved_count(self) -> int:
        """Features whose coordinate relationship is not yet established."""

        return self.unresolved_sequence_count + self.circular_bounds_unresolved_count


@dataclass(frozen=True, slots=True)
class AnnotationCoordinateValidationResult:
    """Exhaustive annotation-coordinate validation against one FASTA anchor.

    Feature aggregate/per-seqid counts cover every feature. ``problem_checks``
    retains only the first representative feature check for each non-matching
    outcome on each seqid, keeping diagnostics bounded by seqid/outcome
    categories. ``sequence_region_validation`` separately retains every GFF3
    ``##sequence-region`` check; the generic coordinate capability combines
    both feature rows and region declarations into one exhaustive statement set.
    """

    annotation_resource_id: ResourceId
    fasta_resource_id: ResourceId
    feature_count: int
    representable_count: int
    out_of_bounds_count: int
    unresolved_sequence_count: int
    circular_bounds_unresolved_count: int
    sequence_summaries: tuple[AnnotationCoordinateSequenceSummary, ...] = ()
    problem_checks: tuple[AnnotationCoordinateCheck, ...] = ()
    sequence_region_validation: Gff3SequenceRegionValidationResult | None = None

    def __post_init__(self) -> None:
        if not self.annotation_resource_id:
            raise ValueError("annotation validation resource ID must not be empty")
        if not self.fasta_resource_id:
            raise ValueError("annotation validation FASTA resource ID must not be empty")
        counts = (
            self.feature_count,
            self.representable_count,
            self.out_of_bounds_count,
            self.unresolved_sequence_count,
            self.circular_bounds_unresolved_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("annotation validation counts must not be negative")
        if (
            self.representable_count
            + self.out_of_bounds_count
            + self.unresolved_sequence_count
            + self.circular_bounds_unresolved_count
            != self.feature_count
        ):
            raise ValueError("annotation validation outcomes must cover every feature")

        names = tuple(summary.sequence_name for summary in self.sequence_summaries)
        if len(set(names)) != len(names):
            raise ValueError("annotation validation sequence summaries must have unique names")
        if sum(summary.feature_count for summary in self.sequence_summaries) != self.feature_count:
            raise ValueError("annotation validation sequence summaries must cover every feature")
        summary_totals = (
            sum(summary.representable_count for summary in self.sequence_summaries),
            sum(summary.out_of_bounds_count for summary in self.sequence_summaries),
            sum(summary.unresolved_sequence_count for summary in self.sequence_summaries),
            sum(summary.circular_bounds_unresolved_count for summary in self.sequence_summaries),
        )
        if summary_totals != (
            self.representable_count,
            self.out_of_bounds_count,
            self.unresolved_sequence_count,
            self.circular_bounds_unresolved_count,
        ):
            raise ValueError("annotation validation summary outcomes must match aggregate counts")

        if any(
            check.feature.resource_id != self.annotation_resource_id
            for check in self.problem_checks
        ):
            raise ValueError("annotation validation problem checks must belong to the annotation")
        if any(
            check.state is AnnotationCoordinateCheckState.REPRESENTABLE
            for check in self.problem_checks
        ):
            raise ValueError("annotation validation problem checks cannot contain matches")

        expected_problem_keys = {
            (summary.sequence_name, state)
            for summary in self.sequence_summaries
            for state, count in (
                (AnnotationCoordinateCheckState.OUT_OF_BOUNDS, summary.out_of_bounds_count),
                (
                    AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
                    summary.unresolved_sequence_count,
                ),
                (
                    AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED,
                    summary.circular_bounds_unresolved_count,
                ),
            )
            if count > 0
        }
        problem_keys = {(check.feature.sequence_name, check.state) for check in self.problem_checks}
        if len(problem_keys) != len(self.problem_checks):
            raise ValueError(
                "annotation validation problem checks must be unique per seqid/outcome"
            )
        if problem_keys != expected_problem_keys:
            raise ValueError(
                "annotation validation problem checks must represent every seqid/outcome category"
            )

        ordinals = tuple(check.feature.ordinal for check in self.problem_checks)
        if ordinals != tuple(sorted(ordinals)):
            raise ValueError("annotation validation problem checks must preserve feature order")
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("annotation validation problem-check ordinals must be unique")

        region_validation = self.sequence_region_validation
        if region_validation is not None:
            if region_validation.annotation_resource_id != self.annotation_resource_id:
                raise ValueError("sequence-region validation must belong to the annotation")
            if region_validation.fasta_resource_id != self.fasta_resource_id:
                raise ValueError("sequence-region validation must use the same FASTA anchor")

    @property
    def unresolved_count(self) -> int:
        """All feature rows whose coordinate relationship remains unresolved."""

        return self.unresolved_sequence_count + self.circular_bounds_unresolved_count

    @property
    def coordinate_count(self) -> int:
        """All feature rows plus GFF3 sequence-region statements checked."""

        region_count = (
            self.sequence_region_validation.region_count
            if self.sequence_region_validation is not None
            else 0
        )
        return self.feature_count + region_count

    @property
    def coordinate_representable_count(self) -> int:
        """All feature/region coordinate statements proven representable."""

        region_count = (
            self.sequence_region_validation.representable_count
            if self.sequence_region_validation is not None
            else 0
        )
        return self.representable_count + region_count

    @property
    def coordinate_conflict_count(self) -> int:
        """All feature/region coordinate statements proven outside the anchor."""

        region_count = (
            self.sequence_region_validation.out_of_bounds_count
            if self.sequence_region_validation is not None
            else 0
        )
        return self.out_of_bounds_count + region_count

    @property
    def coordinate_unresolved_count(self) -> int:
        """All feature/region coordinate statements not yet established."""

        region_count = (
            self.sequence_region_validation.unresolved_count
            if self.sequence_region_validation is not None
            else 0
        )
        return self.unresolved_count + region_count
