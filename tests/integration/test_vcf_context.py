"""Integration tests for real pysam VCF/VCF.gz observation extraction."""

from __future__ import annotations

import gzip
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest

from refcompat.inspectors.vcf import VcfParseError, inspect_vcf_context
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


class _PysamCompressionModule(Protocol):
    tabix_compress: Callable[[str, str, bool], object]


def _resource(path: Path) -> Resource:
    return Resource(ResourceId(path.name), ResourceKind.VCF, ArtifactIdentity(path))


def _write_vcf(path: Path) -> None:
    path.write_text(
        """##fileformat=VCFv4.5
##reference=file:///refs/grch38.fa
##contig=<ID=chr1,length=100,assembly=GRCh38,md5=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa>
##contig=<ID=chr2,length=200>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t10\t.\tA\tG\t.\tPASS\t.
chr1\t20\t.\tC\tT\t.\tPASS\t.
chrUn\t5\t.\tG\tA\t.\tPASS\t.
""",
        encoding="utf-8",
    )


def _assert_snapshot(path: Path) -> None:
    snapshot = inspect_vcf_context(_resource(path))

    assert snapshot.header.file_format == "VCFv4.5"
    assert snapshot.header.reference_claims == ("file:///refs/grch38.fa",)
    assert snapshot.header.contigs[0].assembly == "GRCh38"
    assert snapshot.header.contigs[0].md5 == "a" * 32
    assert snapshot.declared_sequence_names == ("chr1", "chr2")
    assert snapshot.used_sequence_names == ("chr1", "chrUn")
    assert snapshot.undeclared_used_sequence_names == ("chrUn",)
    assert snapshot.declared_unused_sequence_names == ("chr2",)
    assert snapshot.record_count == 3


def test_real_pysam_reads_plain_vcf(tmp_path: Path) -> None:
    path = tmp_path / "variants.vcf"
    _write_vcf(path)
    _assert_snapshot(path)


def test_real_pysam_reads_bgzipped_vcf(tmp_path: Path) -> None:
    source = tmp_path / "variants.vcf"
    compressed = tmp_path / "variants.vcf.gz"
    _write_vcf(source)

    module = cast(_PysamCompressionModule, import_module("pysam"))
    module.tabix_compress(str(source), str(compressed), True)

    _assert_snapshot(compressed)


def test_real_pysam_rejects_plain_gzip_through_normalized_error(tmp_path: Path) -> None:
    source = tmp_path / "variants.vcf"
    compressed = tmp_path / "variants.vcf.gz"
    _write_vcf(source)
    with gzip.open(compressed, "wb") as handle:
        handle.write(source.read_bytes())

    with pytest.raises(VcfParseError, match="cannot parse VCF"):
        inspect_vcf_context(_resource(compressed))


def test_real_pysam_reads_header_only_vcf(tmp_path: Path) -> None:
    path = tmp_path / "header-only.vcf"
    path.write_text(
        """##fileformat=VCFv4.5
##reference=file:///refs/grch38.fa
##contig=<ID=chr1,length=100>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
""",
        encoding="utf-8",
    )

    snapshot = inspect_vcf_context(_resource(path))

    assert snapshot.record_count == 0
    assert snapshot.chrom_usage == ()
    assert snapshot.declared_sequence_names == ("chr1",)


def test_real_pysam_preserves_multiple_reference_claims(tmp_path: Path) -> None:
    path = tmp_path / "references.vcf"
    path.write_text(
        """##fileformat=VCFv4.5
##reference=file:///refs/first.fa
##reference=https://example.test/second.fa
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
""",
        encoding="utf-8",
    )

    snapshot = inspect_vcf_context(_resource(path))

    assert snapshot.header.reference_claims == (
        "file:///refs/first.fa",
        "https://example.test/second.fa",
    )


def test_real_pysam_pins_normalized_duplicate_and_malformed_contigs(tmp_path: Path) -> None:
    path = tmp_path / "normalized-header.vcf"
    path.write_text(
        """##fileformat=VCFv4.5
##contig=<ID=chr1,length=100,assembly=first>
##contig=<ID=chr1,length=200,assembly=second>
##contig=<ID=chrBad,length=notanumber>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
""",
        encoding="utf-8",
    )

    snapshot = inspect_vcf_context(_resource(path))

    observed = [(item.name, item.length, item.assembly) for item in snapshot.header.contigs]
    assert observed == [("chr1", 100, "first")]


def test_real_pysam_preserves_explicit_zero_contig_length(tmp_path: Path) -> None:
    path = tmp_path / "zero-length.vcf"
    path.write_text(
        """##fileformat=VCFv4.5
##contig=<ID=chrZero,length=0>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
""",
        encoding="utf-8",
    )

    snapshot = inspect_vcf_context(_resource(path))

    assert snapshot.header.contigs[0].length == 0


def test_real_pysam_classifies_empty_declared_metadata_as_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "empty-md5.vcf"
    path.write_text(
        """##fileformat=VCFv4.5
##contig=<ID=chr1,length=100,md5=>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
""",
        encoding="utf-8",
    )

    with pytest.raises(VcfParseError, match="empty contig md5"):
        inspect_vcf_context(_resource(path))
