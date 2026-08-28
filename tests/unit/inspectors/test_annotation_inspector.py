"""Unit tests for the narrow streaming GTF/GFF3 observation boundary."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from refcompat.inspectors.annotation import (
    AnnotationParseError,
    AnnotationUnreadableError,
    UnsupportedAnnotationResourceError,
    inspect_annotation_context,
    iter_annotation_features,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def test_inspect_gtf_streams_sparse_sequence_usage_and_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "genes.gtf"
    path.write_text(
        "##description: evidence-based annotation of GRCh38, version 49\n"
        "##provider: GENCODE\n"
        "track name=genes\n"
        "# ordinary comment\n"
        'chr2\tHAVANA\tgene\t20\t90\t.\t+\t.\tgene_id "g1";\n'
        'chr1\tHAVANA\texon\t5\t20\t.\t+\t.\tgene_id "g2";\n'
        'chr2\tHAVANA\texon\t10\t40\t.\t+\t.\tgene_id "g1";\n',
        encoding="utf-8",
    )

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GTF))

    assert snapshot.feature_count == 3
    assert snapshot.used_sequence_names == ("chr2", "chr1")
    assert [
        (item.sequence_name, item.feature_count, item.minimum_start, item.maximum_end)
        for item in snapshot.sequence_usage
    ] == [("chr2", 2, 10, 90), ("chr1", 1, 5, 20)]
    assert [(claim.name, claim.value) for claim in snapshot.provenance_claims] == [
        ("##description", "evidence-based annotation of GRCh38, version 49"),
        ("##provider", "GENCODE"),
    ]
    assert snapshot.sequence_regions == ()
    assert snapshot.fasta_boundary is None


def test_iter_gtf_features_preserves_file_order_and_source_lines(tmp_path: Path) -> None:
    path = tmp_path / "genes.gtf"
    path.write_text(
        "# header\n"
        'chr1\tsrc\tgene\t10\t20\t.\t+\t.\tgene_id "g1";\n'
        "\n"
        'chr2\tsrc\texon\t30\t40\t.\t-\t.\tgene_id "g2";\n',
        encoding="utf-8",
    )

    records = tuple(iter_annotation_features(_resource(path, ResourceKind.GTF)))

    assert [
        (record.ordinal, record.line_number, record.sequence_name, record.start, record.end)
        for record in records
    ] == [(0, 2, "chr1", 10, 20), (1, 4, "chr2", 30, 40)]


def test_inspect_gff3_observes_directives_decoded_seqids_and_circular_feature(
    tmp_path: Path,
) -> None:
    path = tmp_path / "genes.gff3"
    path.write_text(
        "##gff-version 3\n"
        "##sequence-region chr%3A1 1 100\n"
        "##species https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606\n"
        "##genome-build NCBI GRCh38\n"
        "#!genome-build-accession GCF_000001405.40\n"
        "#!annotation-source RefSeq GCF_000001405.40-RS_2025_08\n"
        "chr%3A1\tGenBank\tregion\t1\t100\t.\t+\t.\tID=chr1;Is_circular=true\n"
        "chr%3A1\tGenBank\tgene\t90\t120\t.\t+\t.\tID=g1;Target=tx1%201 1 31 +\n"
        "##FASTA\n"
        ">chr:1\n"
        "ACGT\n",
        encoding="utf-8",
    )

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GFF3))

    assert snapshot.gff_version == "3"
    assert snapshot.feature_count == 2
    assert snapshot.used_sequence_names == ("chr:1",)
    assert snapshot.sequence_usage[0].first_raw_sequence_name == "chr%3A1"
    assert not snapshot.sequence_usage[0].has_multiple_raw_sequence_names
    assert snapshot.sequence_usage[0].minimum_start == 1
    assert snapshot.sequence_usage[0].maximum_end == 120
    assert snapshot.sequence_regions[0].raw_sequence_name == "chr%3A1"
    assert snapshot.sequence_regions[0].sequence_name == "chr:1"
    assert [(claim.name, claim.value) for claim in snapshot.provenance_claims] == [
        (
            "##species",
            "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606",
        ),
        ("##genome-build", "NCBI GRCh38"),
        ("#!genome-build-accession", "GCF_000001405.40"),
        ("#!annotation-source", "RefSeq GCF_000001405.40-RS_2025_08"),
    ]
    assert snapshot.sequence_usage[0].circular_feature_count == 1
    assert snapshot.sequence_usage[0].first_circular_feature_line == 7
    assert snapshot.fasta_boundary is not None
    assert snapshot.fasta_boundary.line_number == 9
    assert snapshot.fasta_boundary.explicit_directive


def test_gff3_aggregates_distinct_raw_encodings_of_same_logical_seqid(tmp_path: Path) -> None:
    path = tmp_path / "encoded.gff3"
    path.write_text(
        "chr%3A1\tsrc\tgene\t1\t2\t.\t+\t.\tID=g1\nchr%3a1\tsrc\texon\t3\t4\t.\t+\t.\tID=e1\n",
        encoding="utf-8",
    )

    resource = _resource(path, ResourceKind.GFF3)
    snapshot = inspect_annotation_context(resource)
    records = tuple(iter_annotation_features(resource))

    assert snapshot.used_sequence_names == ("chr:1",)
    assert snapshot.sequence_usage[0].first_raw_sequence_name == "chr%3A1"
    assert snapshot.sequence_usage[0].has_multiple_raw_sequence_names
    assert snapshot.sequence_usage[0].feature_count == 2
    assert tuple(record.raw_sequence_name for record in records) == ("chr%3A1", "chr%3a1")


def test_gff3_implicit_fasta_boundary_stops_feature_parsing(tmp_path: Path) -> None:
    path = tmp_path / "embedded.gff3"
    path.write_text(
        "chr1\tsrc\tgene\t1\t2\t.\t+\t.\tID=g1\n>chr1\nTHIS\tIS\tNOT\tA\tFEATURE\n",
        encoding="utf-8",
    )

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GFF3))
    records = tuple(iter_annotation_features(_resource(path, ResourceKind.GFF3)))

    assert snapshot.feature_count == 1
    assert snapshot.fasta_boundary is not None
    assert snapshot.fasta_boundary.line_number == 2
    assert not snapshot.fasta_boundary.explicit_directive
    assert len(records) == 1


def test_inspect_annotation_reads_gzip_by_content_magic(tmp_path: Path) -> None:
    path = tmp_path / "genes.data"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write('chr1\tsrc\tgene\t1\t10\t.\t+\t.\tgene_id "g1";\n')

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GTF))

    assert snapshot.feature_count == 1
    assert snapshot.used_sequence_names == ("chr1",)


def test_inspect_annotation_observes_ncbi_pragmas_in_gtf(tmp_path: Path) -> None:
    path = tmp_path / "genes.gtf"
    path.write_text(
        "#!genome-build GRCh38.p14\n"
        "#!genome-build-accession GCF_000001405.40\n"
        "#!annotation-date 08/01/2026\n"
        "#!annotation-source NCBI RefSeq\n"
        'chr1\tsrc\tgene\t1\t10\t.\t+\t.\tgene_id "g1";\n',
        encoding="utf-8",
    )

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GTF))

    assert [claim.name for claim in snapshot.provenance_claims] == [
        "#!genome-build",
        "#!genome-build-accession",
        "#!annotation-date",
        "#!annotation-source",
    ]


def test_gff3_target_coordinates_do_not_create_anchor_features(tmp_path: Path) -> None:
    path = tmp_path / "alignments.gff3"
    path.write_text(
        "chr1\tsrc\tcDNA_match\t10\t20\t.\t+\t.\tID=m1;Target=tx1 1000 2000 +\n",
        encoding="utf-8",
    )

    record = next(iter_annotation_features(_resource(path, ResourceKind.GFF3)))

    assert (record.start, record.end) == (10, 20)


def test_gtf_track_prefixed_seqid_with_tabs_is_a_feature(tmp_path: Path) -> None:
    path = tmp_path / "track-name.gtf"
    path.write_text(
        'track scaffold\tsrc\tgene\t1\t10\t.\t+\t.\tgene_id "g1";\n',
        encoding="utf-8",
    )

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GTF))

    assert snapshot.used_sequence_names == ("track scaffold",)


def test_gff3_ignores_unknown_directive_with_known_prefix(tmp_path: Path) -> None:
    path = tmp_path / "extension.gff3"
    path.write_text(
        "##sequence-region-note provider-extension\nchr1\tsrc\tgene\t1\t2\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )

    snapshot = inspect_annotation_context(_resource(path, ResourceKind.GFF3))

    assert snapshot.feature_count == 1
    assert snapshot.sequence_regions == ()


def test_gtf_does_not_treat_gff3_fasta_header_as_a_boundary(tmp_path: Path) -> None:
    path = tmp_path / "genes.gtf"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")

    with pytest.raises(AnnotationParseError, match="9 tab-separated"):
        inspect_annotation_context(_resource(path, ResourceKind.GTF))


@pytest.mark.parametrize(
    ("kind", "line", "message"),
    [
        (ResourceKind.GTF, "chr1\tsrc\tgene\t1\t2\t.\t+\t.\n", "9 tab-separated"),
        (
            ResourceKind.GFF3,
            "chr%ZZ\tsrc\tgene\t1\t2\t.\t+\t.\tID=g1\n",
            "seqid escaping",
        ),
        (
            ResourceKind.GFF3,
            "chr1\tsrc\tgene\t0\t2\t.\t+\t.\tID=g1\n",
            "positive integer",
        ),
        (
            ResourceKind.GTF,
            'chr1\tsrc\tgene\t3\t2\t.\t+\t.\tgene_id "g1";\n',
            "start exceeds end",
        ),
    ],
)
def test_annotation_parser_rejects_invalid_required_coordinate_syntax(
    tmp_path: Path, kind: ResourceKind, line: str, message: str
) -> None:
    path = tmp_path / "invalid.txt"
    path.write_text(line, encoding="utf-8")

    with pytest.raises(AnnotationParseError, match=message):
        inspect_annotation_context(_resource(path, kind))


def test_gff3_rejects_reversed_sequence_region_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "invalid-region.gff3"
    path.write_text("##sequence-region chr1 10 5\n", encoding="utf-8")

    with pytest.raises(AnnotationParseError, match="sequence-region start exceeds end"):
        inspect_annotation_context(_resource(path, ResourceKind.GFF3))


def test_gff3_rejects_non_gff3_version_when_declared(tmp_path: Path) -> None:
    path = tmp_path / "wrong.gff3"
    path.write_text(
        "##gff-version 2\nchr1\tsrc\tgene\t1\t2\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )

    with pytest.raises(AnnotationParseError, match="gff-version"):
        inspect_annotation_context(_resource(path, ResourceKind.GFF3))


def test_inspect_annotation_rejects_wrong_resource_kind(tmp_path: Path) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nA\n", encoding="utf-8")

    with pytest.raises(UnsupportedAnnotationResourceError):
        inspect_annotation_context(_resource(path, ResourceKind.FASTA))


def test_inspect_annotation_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AnnotationUnreadableError):
        inspect_annotation_context(_resource(tmp_path / "missing.gtf", ResourceKind.GTF))


def test_inspect_annotation_rejects_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "invalid.gtf"
    path.write_bytes(b"chr1\tsrc\tgene\t1\t2\t.\t+\t.\t\xff\n")

    with pytest.raises(AnnotationParseError, match="UTF-8"):
        inspect_annotation_context(_resource(path, ResourceKind.GTF))
