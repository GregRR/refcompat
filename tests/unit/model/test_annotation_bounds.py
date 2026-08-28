"""Tests for annotation-coordinate validation result invariants."""

from dataclasses import replace

import pytest

from refcompat.model.annotation import AnnotationFeatureRecord
from refcompat.model.annotation_bounds import (
    AnnotationCoordinateCheck,
    AnnotationCoordinateCheckState,
    AnnotationCoordinateSequenceSummary,
    AnnotationCoordinateValidationResult,
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
