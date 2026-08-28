"""Unit tests for GTF/GFF3 reference-coordinate observation models."""

from __future__ import annotations

import pytest

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationFeatureRecord,
    AnnotationSequenceUsage,
    Gff3FastaBoundary,
    Gff3SequenceRegion,
)
from refcompat.model.resources import ResourceId, ResourceKind


def _usage(
    sequence_name: str = "chr1",
    *,
    count: int = 1,
    circular_count: int = 0,
) -> AnnotationSequenceUsage:
    return AnnotationSequenceUsage(
        sequence_name=sequence_name,
        first_raw_sequence_name=sequence_name,
        feature_count=count,
        minimum_start=1,
        maximum_end=100,
        first_feature_line=2,
        circular_feature_count=circular_count,
        first_circular_feature_line=2 if circular_count else None,
    )


def test_annotation_snapshot_preserves_sparse_usage_order() -> None:
    snapshot = AnnotationContextSnapshot(
        resource_id=ResourceId("annotation"),
        resource_kind=ResourceKind.GTF,
        feature_count=3,
        sequence_usage=(
            AnnotationSequenceUsage("chr2", "chr2", 2, 10, 90, 3),
            AnnotationSequenceUsage("chr1", "chr1", 1, 5, 20, 8),
        ),
    )

    assert snapshot.used_sequence_names == ("chr2", "chr1")


def test_annotation_snapshot_accepts_gff3_only_observations_for_gff3() -> None:
    snapshot = AnnotationContextSnapshot(
        resource_id=ResourceId("annotation"),
        resource_kind=ResourceKind.GFF3,
        feature_count=1,
        sequence_usage=(_usage(circular_count=1),),
        gff_version="3",
        sequence_regions=(Gff3SequenceRegion("chr1", "chr1", 1, 100, 1),),
        fasta_boundary=Gff3FastaBoundary(line_number=3, explicit_directive=True),
    )

    assert snapshot.sequence_usage[0].circular_feature_count == 1
    assert snapshot.fasta_boundary is not None


def test_annotation_feature_rejects_nonpositive_or_reversed_coordinates() -> None:
    with pytest.raises(ValueError, match="positive"):
        AnnotationFeatureRecord(ResourceId("annotation"), 0, 1, "chr1", "chr1", "gene", 0, 10)

    with pytest.raises(ValueError, match="start must not exceed end"):
        AnnotationFeatureRecord(ResourceId("annotation"), 0, 1, "chr1", "chr1", "gene", 11, 10)


def test_annotation_snapshot_rejects_usage_count_mismatch() -> None:
    with pytest.raises(ValueError, match="sum to feature count"):
        AnnotationContextSnapshot(
            resource_id=ResourceId("annotation"),
            resource_kind=ResourceKind.GTF,
            feature_count=2,
            sequence_usage=(_usage(),),
        )


def test_gtf_snapshot_rejects_gff3_only_observations() -> None:
    with pytest.raises(ValueError, match="GFF3-only"):
        AnnotationContextSnapshot(
            resource_id=ResourceId("annotation"),
            resource_kind=ResourceKind.GTF,
            feature_count=0,
            gff_version="3",
        )


def test_gtf_snapshot_rejects_is_circular_usage() -> None:
    with pytest.raises(ValueError, match="Is_circular"):
        AnnotationContextSnapshot(
            resource_id=ResourceId("annotation"),
            resource_kind=ResourceKind.GTF,
            feature_count=1,
            sequence_usage=(_usage(circular_count=1),),
        )


def test_annotation_usage_requires_consistent_circular_summary() -> None:
    with pytest.raises(ValueError, match="first circular line"):
        AnnotationSequenceUsage(
            sequence_name="chr1",
            first_raw_sequence_name="chr1",
            feature_count=1,
            minimum_start=1,
            maximum_end=100,
            first_feature_line=2,
            first_circular_feature_line=2,
        )


def test_gff3_snapshot_rejects_duplicate_logical_sequence_regions() -> None:
    region = Gff3SequenceRegion("chr1", "chr1", 1, 100, 1)

    with pytest.raises(ValueError, match="sequence-region seqids must be unique"):
        AnnotationContextSnapshot(
            ResourceId("annotation"),
            ResourceKind.GFF3,
            feature_count=0,
            sequence_regions=(region, region),
        )


def test_embedded_fasta_sequence_requires_nonempty_name_and_positive_length() -> None:
    from refcompat.model.annotation import Gff3EmbeddedFastaSequence
    from refcompat.model.identity import Md5Digest

    md5 = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
    with pytest.raises(ValueError, match="name"):
        Gff3EmbeddedFastaSequence("", 4, md5, 1)
    with pytest.raises(ValueError, match="length"):
        Gff3EmbeddedFastaSequence("chr1", -1, md5, 1)


def test_annotation_snapshot_rejects_embedded_fasta_without_boundary() -> None:
    from refcompat.model.annotation import Gff3EmbeddedFastaSequence
    from refcompat.model.identity import Md5Digest

    with pytest.raises(ValueError, match="require a FASTA boundary"):
        AnnotationContextSnapshot(
            ResourceId("annotation"),
            ResourceKind.GFF3,
            0,
            embedded_fasta_sequences=(
                Gff3EmbeddedFastaSequence(
                    "chr1",
                    4,
                    Md5Digest("f1f8f4bf413b16ad135722aa4591043e"),
                    2,
                ),
            ),
        )
