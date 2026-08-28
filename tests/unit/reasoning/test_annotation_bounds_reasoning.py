"""Tests for exhaustive exact-name annotation coordinate validation."""

from pathlib import Path

import pytest

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationFeatureRecord,
    AnnotationSequenceUsage,
    Gff3EmbeddedFastaSequence,
    Gff3FastaBoundary,
    Gff3SequenceRegion,
)
from refcompat.model.annotation_bounds import (
    AnnotationCoordinateCheckState,
    Gff3SequenceRegionCheckState,
)
from refcompat.model.contracts import CapabilityId
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.identity import (
    CollectionCompleteness,
    Md5Digest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import (
    ReferenceContext,
    SequenceBinding,
    SequenceBindingId,
    SequenceBindingMethod,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.reasoning.annotation_bounds import (
    AnnotationCoordinateEvaluationError,
    evaluate_annotation_coordinates,
)
from refcompat.reasoning.reference_context import build_reference_context

_ANNOTATION = ResourceId("annotation")
_FASTA = ResourceId("fasta")


def _context(
    *sequences: tuple[str, int],
    scope_names: tuple[str, ...] | None = None,
) -> ReferenceContext:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa"))),
        Resource(_ANNOTATION, ResourceKind.GTF, ArtifactIdentity(Path("genes.gtf"))),
    )
    request = EvaluationRequest(
        resources,
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION), anchor_sequence_names=scope_names),
    )
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=tuple(
            SnapshotSequence(name, length, ordinal)
            for ordinal, (name, length) in enumerate(sequences)
        ),
    )
    return build_reference_context(request, snapshot)


def _feature(
    ordinal: int,
    sequence_name: str,
    start: int,
    end: int,
    *,
    circular: bool = False,
) -> AnnotationFeatureRecord:
    return AnnotationFeatureRecord(
        _ANNOTATION,
        ordinal,
        ordinal + 1,
        sequence_name,
        sequence_name,
        "gene",
        start,
        end,
        is_circular=circular,
    )


def _snapshot(
    *usage: tuple[str, int, int, int, int],
    kind: ResourceKind = ResourceKind.GTF,
    regions: tuple[Gff3SequenceRegion, ...] = (),
    embedded: tuple[Gff3EmbeddedFastaSequence, ...] = (),
) -> AnnotationContextSnapshot:
    """Build usage as name, count, min start, max end, circular count."""

    return AnnotationContextSnapshot(
        _ANNOTATION,
        kind,
        feature_count=sum(item[1] for item in usage),
        sequence_usage=tuple(
            AnnotationSequenceUsage(
                sequence_name=name,
                first_raw_sequence_name=name,
                feature_count=count,
                minimum_start=minimum_start,
                maximum_end=maximum_end,
                first_feature_line=index + 1,
                circular_feature_count=circular_count,
                first_circular_feature_line=(index + 1 if circular_count else None),
            )
            for index, (name, count, minimum_start, maximum_end, circular_count) in enumerate(usage)
        ),
        sequence_regions=regions,
        fasta_boundary=(Gff3FastaBoundary(100, True) if embedded else None),
        embedded_fasta_sequences=embedded,
    )


def _binding(local_name: str, anchor_name: str) -> SequenceBinding:
    return SequenceBinding(
        SequenceBindingId(f"binding:{local_name}:{anchor_name}"),
        _ANNOTATION,
        local_name,
        _FASTA,
        anchor_name,
        SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
        (Md5Digest("f1f8f4bf413b16ad135722aa4591043e"),),
        (CapabilityId("local-capability"), CapabilityId("anchor-capability")),
    )


def test_exact_name_features_are_representable_at_closed_boundary() -> None:
    snapshot = _snapshot(("chr1", 2, 1, 100, 0))
    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 10), _feature(1, "chr1", 100, 100)),
        _context(("chr1", 100)),
    )

    assert result.feature_count == 2
    assert result.representable_count == 2
    assert result.out_of_bounds_count == 0
    assert result.unresolved_count == 0
    assert result.problem_checks == ()


def test_missing_exact_name_remains_unresolved_without_alias_guess() -> None:
    snapshot = _snapshot(("1", 1, 1, 10, 0))
    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "1", 1, 10),),
        _context(("chr1", 100)),
    )

    assert result.unresolved_sequence_count == 1
    check = result.problem_checks[0]
    assert check.state is AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE
    assert check.anchor_sequence_name is None


def test_resolved_ordinary_out_of_bounds_feature_is_hard_local_conflict() -> None:
    snapshot = _snapshot(("chr1", 1, 90, 101, 0))
    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 90, 101),),
        _context(("chr1", 100)),
    )

    assert result.out_of_bounds_count == 1
    check = result.problem_checks[0]
    assert check.state is AnnotationCoordinateCheckState.OUT_OF_BOUNDS
    assert check.anchor_sequence_name == "chr1"
    assert check.anchor_sequence_length == 100


def test_gff3_possible_circular_seqid_defers_out_of_bounds_conclusion() -> None:
    snapshot = _snapshot(("chrM", 2, 1, 120, 1), kind=ResourceKind.GFF3)
    result = evaluate_annotation_coordinates(
        snapshot,
        (
            _feature(0, "chrM", 1, 100, circular=True),
            _feature(1, "chrM", 90, 120),
        ),
        _context(("chrM", 100)),
    )

    assert result.representable_count == 1
    assert result.out_of_bounds_count == 0
    assert result.circular_bounds_unresolved_count == 1
    problem_check = result.problem_checks[0]
    assert problem_check.state is AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED


def test_same_gff3_out_of_bounds_interval_conflicts_without_circular_evidence() -> None:
    snapshot = _snapshot(("chrM", 1, 90, 120, 0), kind=ResourceKind.GFF3)
    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chrM", 90, 120),),
        _context(("chrM", 100)),
    )

    assert result.out_of_bounds_count == 1
    assert result.circular_bounds_unresolved_count == 0


def test_explicit_anchor_scope_can_leave_exact_name_unresolved() -> None:
    snapshot = _snapshot(("chr2", 1, 1, 10, 0))
    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr2", 1, 10),),
        _context(("chr1", 100), ("chr2", 100), scope_names=("chr1",)),
    )

    assert result.unresolved_sequence_count == 1


def test_problem_checks_are_bounded_per_seqid_and_outcome() -> None:
    features = tuple(_feature(index, "missing", index + 1, index + 1) for index in range(1000))
    snapshot = _snapshot(("missing", len(features), 1, 1000, 0))

    result = evaluate_annotation_coordinates(
        snapshot,
        features,
        _context(("chr1", 1000)),
    )

    assert result.unresolved_sequence_count == 1000
    assert len(result.problem_checks) == 1
    assert result.problem_checks[0].feature.ordinal == 0
    assert result.problem_checks[0].state is AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE


def test_sequence_summaries_preserve_first_observed_feature_order() -> None:
    snapshot = _snapshot(("chr2", 2, 1, 11, 0), ("chr1", 1, 5, 5, 0))
    result = evaluate_annotation_coordinates(
        snapshot,
        (
            _feature(0, "chr2", 1, 10),
            _feature(1, "chr1", 5, 5),
            _feature(2, "chr2", 11, 11),
        ),
        _context(("chr1", 100), ("chr2", 100)),
    )

    assert tuple(summary.sequence_name for summary in result.sequence_summaries) == (
        "chr2",
        "chr1",
    )


def test_evaluator_rejects_nonexhaustive_or_crosswired_feature_stream() -> None:
    snapshot = _snapshot(("chr1", 1, 1, 10, 0))
    context = _context(("chr1", 100))

    with pytest.raises(AnnotationCoordinateEvaluationError, match="exhaustive, contiguous"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(1, "chr1", 1, 10),),
            context,
        )

    other = AnnotationFeatureRecord(
        ResourceId("other"),
        0,
        1,
        "chr1",
        "chr1",
        "gene",
        1,
        10,
    )
    with pytest.raises(AnnotationCoordinateEvaluationError, match="different annotation"):
        evaluate_annotation_coordinates(snapshot, (other,), context)


def test_evaluator_rejects_stream_that_does_not_match_inspected_snapshot_count() -> None:
    snapshot = _snapshot(("chr1", 2, 1, 10, 0))
    with pytest.raises(AnnotationCoordinateEvaluationError, match="snapshot feature count"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chr1", 1, 10),),
            _context(("chr1", 100)),
        )


def test_evaluator_rejects_stale_snapshot_circular_usage() -> None:
    snapshot = _snapshot(("chrM", 1, 90, 120, 0), kind=ResourceKind.GFF3)
    with pytest.raises(AnnotationCoordinateEvaluationError, match="seqid/bounds/circular usage"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chrM", 90, 120, circular=True),),
            _context(("chrM", 100)),
        )


def test_gff3_sequence_region_is_checked_against_anchor() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 10, 90, 1)
    snapshot = _snapshot(
        ("chr1", 1, 20, 30, 0),
        kind=ResourceKind.GFF3,
        regions=(region,),
    )

    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 20, 30),),
        _context(("chr1", 100)),
    )

    assert result.sequence_region_validation is not None
    assert result.sequence_region_validation.region_count == 1
    assert result.sequence_region_validation.representable_count == 1
    assert result.sequence_region_validation.checks[0].state is (
        Gff3SequenceRegionCheckState.REPRESENTABLE
    )
    assert result.coordinate_count == 2
    assert result.coordinate_representable_count == 2


def test_gff3_sequence_region_outside_anchor_is_coordinate_conflict() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 101, 1)
    snapshot = _snapshot(
        ("chr1", 1, 1, 10, 0),
        kind=ResourceKind.GFF3,
        regions=(region,),
    )

    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 10),),
        _context(("chr1", 100)),
    )

    assert result.sequence_region_validation is not None
    assert result.sequence_region_validation.out_of_bounds_count == 1
    assert result.coordinate_conflict_count == 1


def test_gff3_sequence_region_only_unfamiliar_seqid_remains_unresolved() -> None:
    region = Gff3SequenceRegion("1", "1", 1, 100, 1)
    snapshot = _snapshot(kind=ResourceKind.GFF3, regions=(region,))

    result = evaluate_annotation_coordinates(
        snapshot,
        (),
        _context(("chr1", 100)),
    )

    assert result.sequence_region_validation is not None
    assert result.sequence_region_validation.unresolved_sequence_count == 1
    assert result.coordinate_count == 1
    assert result.coordinate_unresolved_count == 1


def test_gff3_feature_outside_declared_region_is_invalid_without_circular_evidence() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 80, 1)
    snapshot = _snapshot(
        ("chr1", 1, 70, 90, 0),
        kind=ResourceKind.GFF3,
        regions=(region,),
    )

    with pytest.raises(AnnotationCoordinateEvaluationError, match="outside its declared"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chr1", 70, 90),),
            _context(("chr1", 100)),
        )


def test_gff3_feature_outside_declared_region_defers_with_circular_evidence() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 80, 1)
    snapshot = _snapshot(
        ("chr1", 1, 70, 90, 1),
        kind=ResourceKind.GFF3,
        regions=(region,),
    )

    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 70, 90, circular=True),),
        _context(("chr1", 100)),
    )

    assert result.circular_bounds_unresolved_count == 1
    assert result.out_of_bounds_count == 0


def test_stale_feature_stream_is_rejected_before_sequence_region_semantic_error() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 80, 1)
    snapshot = _snapshot(
        ("chr1", 1, 1, 10, 0),
        kind=ResourceKind.GFF3,
        regions=(region,),
    )

    with pytest.raises(AnnotationCoordinateEvaluationError, match="seqid/bounds/circular usage"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chr1", 70, 90),),
            _context(("chr1", 100)),
        )


def test_gff3_feature_beyond_matching_embedded_fasta_is_invalid() -> None:
    embedded = Gff3EmbeddedFastaSequence(
        "chr1",
        80,
        Md5Digest("0" * 32),
        100,
    )
    snapshot = _snapshot(
        ("chr1", 1, 70, 90, 0),
        kind=ResourceKind.GFF3,
        embedded=(embedded,),
    )

    with pytest.raises(AnnotationCoordinateEvaluationError, match="matching embedded FASTA"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chr1", 70, 90),),
            _context(("chr1", 100)),
        )


def test_gff3_feature_beyond_embedded_fasta_defers_with_circular_evidence() -> None:
    embedded = Gff3EmbeddedFastaSequence(
        "chr1",
        80,
        Md5Digest("0" * 32),
        100,
    )
    snapshot = _snapshot(
        ("chr1", 1, 70, 90, 1),
        kind=ResourceKind.GFF3,
        embedded=(embedded,),
    )

    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 70, 90, circular=True),),
        _context(("chr1", 100)),
    )

    assert result.circular_bounds_unresolved_count == 1
    assert result.out_of_bounds_count == 0


def test_gff3_sequence_region_beyond_matching_embedded_fasta_is_invalid() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 90, 1)
    embedded = Gff3EmbeddedFastaSequence(
        "chr1",
        80,
        Md5Digest("0" * 32),
        100,
    )
    snapshot = _snapshot(
        ("chr1", 1, 1, 10, 0),
        kind=ResourceKind.GFF3,
        regions=(region,),
        embedded=(embedded,),
    )

    with pytest.raises(AnnotationCoordinateEvaluationError, match="sequence-region exceeds"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chr1", 1, 10),),
            _context(("chr1", 100)),
        )


def test_stale_stream_is_rejected_before_embedded_fasta_feature_semantic_error() -> None:
    embedded = Gff3EmbeddedFastaSequence(
        "chr1",
        80,
        Md5Digest("0" * 32),
        100,
    )
    snapshot = _snapshot(
        ("chr1", 1, 1, 10, 0),
        kind=ResourceKind.GFF3,
        embedded=(embedded,),
    )

    with pytest.raises(AnnotationCoordinateEvaluationError, match="seqid/bounds/circular usage"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "chr1", 70, 90),),
            _context(("chr1", 100)),
        )


def test_verified_binding_resolves_cross_name_feature_coordinates() -> None:
    snapshot = _snapshot(("1", 1, 1, 10, 0))
    binding = _binding("1", "chr1")

    result = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "1", 1, 10),),
        _context(("chr1", 100)),
        (binding,),
    )

    assert result.representable_count == 1
    assert result.sequence_binding_ids == (binding.id,)
    assert result.problem_checks == ()


def test_verified_binding_resolves_cross_name_sequence_region() -> None:
    region = Gff3SequenceRegion("1", "1", 1, 100, 1)
    snapshot = _snapshot(kind=ResourceKind.GFF3, regions=(region,))
    binding = _binding("1", "chr1")

    result = evaluate_annotation_coordinates(
        snapshot,
        (),
        _context(("chr1", 100)),
        (binding,),
    )

    assert result.sequence_region_validation is not None
    check = result.sequence_region_validation.checks[0]
    assert check.state is Gff3SequenceRegionCheckState.REPRESENTABLE
    assert check.anchor_sequence_name == "chr1"


def test_annotation_evaluator_rejects_binding_for_irrelevant_local_seqid() -> None:
    snapshot = _snapshot(("1", 1, 1, 10, 0))

    with pytest.raises(ValueError, match="reference-relevant"):
        evaluate_annotation_coordinates(
            snapshot,
            (_feature(0, "1", 1, 10),),
            _context(("chr1", 100)),
            (_binding("other", "chr1"),),
        )
