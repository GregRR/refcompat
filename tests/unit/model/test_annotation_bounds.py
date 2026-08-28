"""Tests for annotation-coordinate validation result invariants."""

from dataclasses import replace

import pytest

from refcompat.model.annotation import AnnotationFeatureRecord, Gff3SequenceRegion
from refcompat.model.annotation_bounds import (
    AnnotationCoordinateCheck,
    AnnotationCoordinateCheckState,
    AnnotationCoordinateSequenceSummary,
    AnnotationCoordinateValidationResult,
    Gff3SequenceRegionCheck,
    Gff3SequenceRegionCheckState,
    Gff3SequenceRegionValidationResult,
)
from refcompat.model.resources import ResourceId

_ANNOTATION = ResourceId("annotation")
_FASTA = ResourceId("fasta")


def _feature(ordinal: int = 0, sequence_name: str = "chr1") -> AnnotationFeatureRecord:
    return AnnotationFeatureRecord(
        _ANNOTATION,
        ordinal,
        ordinal + 1,
        sequence_name,
        sequence_name,
        "gene",
        1,
        10,
    )


def test_resolved_coordinate_check_requires_anchor_context() -> None:
    with pytest.raises(ValueError, match="requires an anchor name"):
        AnnotationCoordinateCheck(_feature(), AnnotationCoordinateCheckState.OUT_OF_BOUNDS)

    unresolved = AnnotationCoordinateCheck(
        _feature(),
        AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
    )
    with pytest.raises(ValueError, match="cannot carry anchor coordinates"):
        replace(unresolved, anchor_sequence_name="chr1", anchor_sequence_length=100)


def test_sequence_summary_outcomes_must_cover_every_feature() -> None:
    with pytest.raises(ValueError, match="cover every feature"):
        AnnotationCoordinateSequenceSummary(
            "chr1",
            feature_count=2,
            representable_count=1,
        )


def test_validation_requires_summary_and_problem_coverage() -> None:
    summary = AnnotationCoordinateSequenceSummary(
        "chr1",
        feature_count=1,
        out_of_bounds_count=1,
    )
    with pytest.raises(ValueError, match="problem checks"):
        AnnotationCoordinateValidationResult(
            _ANNOTATION,
            _FASTA,
            feature_count=1,
            representable_count=0,
            out_of_bounds_count=1,
            unresolved_sequence_count=0,
            circular_bounds_unresolved_count=0,
            sequence_summaries=(summary,),
        )


def test_problem_checks_preserve_feature_order() -> None:
    first = AnnotationCoordinateCheck(
        _feature(0, "missing"),
        AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
    )
    second = AnnotationCoordinateCheck(
        _feature(1, "chrM"),
        AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED,
        anchor_sequence_name="chrM",
        anchor_sequence_length=100,
    )
    summaries = (
        AnnotationCoordinateSequenceSummary(
            "missing",
            feature_count=1,
            unresolved_sequence_count=1,
        ),
        AnnotationCoordinateSequenceSummary(
            "chrM",
            feature_count=1,
            circular_bounds_unresolved_count=1,
        ),
    )
    with pytest.raises(ValueError, match="preserve feature order"):
        AnnotationCoordinateValidationResult(
            _ANNOTATION,
            _FASTA,
            feature_count=2,
            representable_count=0,
            out_of_bounds_count=0,
            unresolved_sequence_count=1,
            circular_bounds_unresolved_count=1,
            sequence_summaries=summaries,
            problem_checks=(second, first),
        )


def test_problem_checks_are_unique_per_seqid_and_outcome() -> None:
    first = AnnotationCoordinateCheck(
        _feature(0, "missing"),
        AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
    )
    duplicate = AnnotationCoordinateCheck(
        _feature(1, "missing"),
        AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
    )
    summary = AnnotationCoordinateSequenceSummary(
        "missing",
        feature_count=2,
        unresolved_sequence_count=2,
    )

    with pytest.raises(ValueError, match="unique per seqid/outcome"):
        AnnotationCoordinateValidationResult(
            _ANNOTATION,
            _FASTA,
            feature_count=2,
            representable_count=0,
            out_of_bounds_count=0,
            unresolved_sequence_count=2,
            circular_bounds_unresolved_count=0,
            sequence_summaries=(summary,),
            problem_checks=(first, duplicate),
        )


def test_unresolved_count_combines_name_and_circular_states() -> None:
    result = AnnotationCoordinateValidationResult(
        _ANNOTATION,
        _FASTA,
        feature_count=2,
        representable_count=0,
        out_of_bounds_count=0,
        unresolved_sequence_count=1,
        circular_bounds_unresolved_count=1,
        sequence_summaries=(
            AnnotationCoordinateSequenceSummary(
                "missing",
                feature_count=1,
                unresolved_sequence_count=1,
            ),
            AnnotationCoordinateSequenceSummary(
                "chrM",
                feature_count=1,
                circular_bounds_unresolved_count=1,
            ),
        ),
        problem_checks=(
            AnnotationCoordinateCheck(
                _feature(0, "missing"),
                AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
            ),
            AnnotationCoordinateCheck(
                _feature(1, "chrM"),
                AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED,
                anchor_sequence_name="chrM",
                anchor_sequence_length=100,
            ),
        ),
    )

    assert result.unresolved_count == 2


def test_sequence_region_validation_covers_every_directive() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 100, 1)
    check = Gff3SequenceRegionCheck(
        region,
        Gff3SequenceRegionCheckState.REPRESENTABLE,
        anchor_sequence_name="chr1",
        anchor_sequence_length=100,
    )

    result = Gff3SequenceRegionValidationResult(
        _ANNOTATION,
        _FASTA,
        region_count=1,
        representable_count=1,
        out_of_bounds_count=0,
        unresolved_sequence_count=0,
        checks=(check,),
    )

    assert result.unresolved_count == 0

    with pytest.raises(ValueError, match="cover every directive"):
        replace(result, representable_count=0)


def test_coordinate_totals_include_sequence_region_validation() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 101, 1)
    region_validation = Gff3SequenceRegionValidationResult(
        _ANNOTATION,
        _FASTA,
        region_count=1,
        representable_count=0,
        out_of_bounds_count=1,
        unresolved_sequence_count=0,
        checks=(
            Gff3SequenceRegionCheck(
                region,
                Gff3SequenceRegionCheckState.OUT_OF_BOUNDS,
                anchor_sequence_name="chr1",
                anchor_sequence_length=100,
            ),
        ),
    )
    result = AnnotationCoordinateValidationResult(
        _ANNOTATION,
        _FASTA,
        feature_count=1,
        representable_count=1,
        out_of_bounds_count=0,
        unresolved_sequence_count=0,
        circular_bounds_unresolved_count=0,
        sequence_summaries=(
            AnnotationCoordinateSequenceSummary(
                "chr1",
                feature_count=1,
                representable_count=1,
            ),
        ),
        sequence_region_validation=region_validation,
    )

    assert result.coordinate_count == 2
    assert result.coordinate_representable_count == 1
    assert result.coordinate_conflict_count == 1
    assert result.coordinate_unresolved_count == 0


def test_circular_representable_features_count_as_coordinate_support() -> None:
    result = AnnotationCoordinateValidationResult(
        _ANNOTATION,
        _FASTA,
        feature_count=1,
        representable_count=0,
        out_of_bounds_count=0,
        unresolved_sequence_count=0,
        circular_bounds_unresolved_count=0,
        circular_representable_count=1,
        sequence_summaries=(
            AnnotationCoordinateSequenceSummary(
                "chrM",
                feature_count=1,
                circular_representable_count=1,
            ),
        ),
    )

    assert result.coordinate_representable_count == 1
    check = AnnotationCoordinateCheck(
        _feature(0, "chrM"),
        AnnotationCoordinateCheckState.CIRCULAR_REPRESENTABLE,
        anchor_sequence_name="chrM",
        anchor_sequence_length=100,
    )
    assert check.state is AnnotationCoordinateCheckState.CIRCULAR_REPRESENTABLE
