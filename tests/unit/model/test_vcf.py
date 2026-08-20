"""Unit tests for VCF reference-context observation models."""

from __future__ import annotations

import pytest

from refcompat.model.resources import ResourceId
from refcompat.model.vcf import (
    VcfChromUsage,
    VcfContextSnapshot,
    VcfContigDeclaration,
    VcfHeaderData,
)


def test_vcf_context_distinguishes_declared_and_used_sequences() -> None:
    snapshot = VcfContextSnapshot(
        resource_id=ResourceId("variants"),
        header=VcfHeaderData(
            file_format="VCFv4.5",
            reference_claims=("file:///refs/grch38.fa",),
            contigs=(
                VcfContigDeclaration("chr1", 100, md5="a" * 32, assembly="GRCh38"),
                VcfContigDeclaration("chr2", 200),
            ),
        ),
        record_count=3,
        chrom_usage=(VcfChromUsage("chr1", 2), VcfChromUsage("chrUn", 1)),
    )

    assert snapshot.declared_sequence_names == ("chr1", "chr2")
    assert snapshot.used_sequence_names == ("chr1", "chrUn")
    assert snapshot.undeclared_used_sequence_names == ("chrUn",)
    assert snapshot.declared_unused_sequence_names == ("chr2",)


def test_vcf_context_allows_empty_record_stream() -> None:
    snapshot = VcfContextSnapshot(
        resource_id=ResourceId("variants"),
        header=VcfHeaderData(file_format="VCFv4.5"),
        record_count=0,
    )

    assert snapshot.chrom_usage == ()
    assert snapshot.used_sequence_names == ()


def test_vcf_header_rejects_duplicate_contig_declarations() -> None:
    with pytest.raises(ValueError, match="unique names"):
        VcfHeaderData(
            file_format="VCFv4.5",
            contigs=(VcfContigDeclaration("chr1"), VcfContigDeclaration("chr1")),
        )


def test_vcf_context_rejects_usage_count_mismatch() -> None:
    with pytest.raises(ValueError, match="sum to the record count"):
        VcfContextSnapshot(
            resource_id=ResourceId("variants"),
            header=VcfHeaderData(file_format="VCFv4.5"),
            record_count=2,
            chrom_usage=(VcfChromUsage("chr1", 1),),
        )
