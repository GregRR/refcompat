"""Real-pysam integration coverage for the Milestone 8 BCF observation boundary."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest

from refcompat.inspectors.vcf import VcfParseError, inspect_vcf_context, iter_vcf_ref_records
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def _write_vcf(path: Path) -> None:
    path.write_text(
        """##fileformat=VCFv4.2
##reference=file:///refs/reference.fa
##contig=<ID=chr1,length=8>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t2\t.\tC\tT\t.\tPASS\t.
chr1\t5\t.\tA\tG\t.\tPASS\t.
""",
        encoding="utf-8",
    )


def _convert_to_bcf(vcf_path: Path, bcf_path: Path) -> None:
    pysam = cast(Any, import_module("pysam"))
    with (
        pysam.VariantFile(str(vcf_path)) as source,
        pysam.VariantFile(str(bcf_path), "wb", header=source.header) as target,
    ):
        for record in source:
            target.write(record)


def test_real_pysam_bcf_exposes_vcf_logical_context_and_one_based_pos(tmp_path: Path) -> None:
    vcf_path = tmp_path / "variants.vcf"
    bcf_path = tmp_path / "variants.bcf"
    _write_vcf(vcf_path)
    _convert_to_bcf(vcf_path, bcf_path)

    snapshot = inspect_vcf_context(_resource(bcf_path, ResourceKind.BCF))
    records = tuple(iter_vcf_ref_records(_resource(bcf_path, ResourceKind.BCF)))

    assert snapshot.header.file_format == "VCFv4.2"
    assert snapshot.header.reference_claims == ("file:///refs/reference.fa",)
    assert snapshot.declared_sequence_names == ("chr1",)
    assert snapshot.used_sequence_names == ("chr1",)
    assert snapshot.record_count == 2
    observed = [
        (record.ordinal, record.sequence_name, record.position, record.ref) for record in records
    ]
    assert observed == [
        (0, "chr1", 2, "C"),
        (1, "chr1", 5, "A"),
    ]
    assert not Path(f"{bcf_path}.csi").exists()


@pytest.mark.parametrize(
    ("declared_kind", "artifact_kind"),
    [
        (ResourceKind.VCF, ResourceKind.BCF),
        (ResourceKind.BCF, ResourceKind.VCF),
    ],
)
def test_real_pysam_rejects_declared_variant_encoding_mismatch(
    tmp_path: Path,
    declared_kind: ResourceKind,
    artifact_kind: ResourceKind,
) -> None:
    vcf_path = tmp_path / "variants.vcf"
    bcf_path = tmp_path / "variants.bcf"
    _write_vcf(vcf_path)
    _convert_to_bcf(vcf_path, bcf_path)
    path = bcf_path if artifact_kind is ResourceKind.BCF else vcf_path

    with pytest.raises(VcfParseError, match="resource declared as"):
        inspect_vcf_context(_resource(path, declared_kind))
