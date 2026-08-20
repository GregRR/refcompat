"""Real-pysam/refget integration tests for exhaustive VCF REF-to-FASTA validation."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from refcompat.inspectors.fasta_sequence import open_fasta_sequence_reader
from refcompat.inspectors.vcf import iter_vcf_ref_records
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.vcf_ref import VcfRefCheckState, VcfRefValidationResult
from refcompat.reasoning.vcf_ref import evaluate_vcf_ref_records


class _PysamCompressionModule(Protocol):
    tabix_compress: Callable[[str, str, bool], object]


def _resource(path: Path, resource_id: str, kind: ResourceKind) -> Resource:
    return Resource(ResourceId(resource_id), kind, ArtifactIdentity(path))


def _write_fasta(path: Path) -> None:
    path.write_text(">chr1\nACGTACGT\n>chr2\nTTTT\n", encoding="utf-8")


def _write_vcf(path: Path) -> None:
    path.write_text(
        """##fileformat=VCFv4.5
##contig=<ID=chr1,length=8>
##contig=<ID=chr2,length=4>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t1\t.\tA\tG\t.\tPASS\t.
chr1\t4\t.\tTA\tT\t.\tPASS\t.
chr1\t3\t.\tT\tA\t.\tPASS\t.
chr1\t9\t.\tA\tG\t.\tPASS\t.
chrUn\t1\t.\tA\tG\t.\tPASS\t.
chr2\t1\t.\tT\tC\t.\tPASS\t.
""",
        encoding="utf-8",
    )


def _evaluate(vcf: Path, fasta: Path) -> VcfRefValidationResult:
    vcf_resource = _resource(vcf, "variants", ResourceKind.VCF)
    fasta_resource = _resource(fasta, "reference", ResourceKind.FASTA)
    with open_fasta_sequence_reader(fasta_resource) as reference:
        return evaluate_vcf_ref_records(
            vcf_resource_id=vcf_resource.id,
            fasta_resource_id=fasta_resource.id,
            records=iter_vcf_ref_records(vcf_resource),
            reference=reference,
        )


def test_real_providers_exhaustively_classify_vcf_ref_records(tmp_path: Path) -> None:
    fasta = tmp_path / "reference.fa"
    vcf = tmp_path / "variants.vcf"
    _write_fasta(fasta)
    _write_vcf(vcf)

    result = _evaluate(vcf, fasta)

    assert result.record_count == 6
    assert result.match_count == 3
    assert result.mismatch_count == 1
    assert result.out_of_bounds_count == 1
    assert result.unresolved_sequence_count == 1
    assert [(check.record.ordinal, check.state) for check in result.problem_records] == [
        (2, VcfRefCheckState.MISMATCH),
        (3, VcfRefCheckState.OUT_OF_BOUNDS),
        (4, VcfRefCheckState.UNRESOLVED_SEQUENCE),
    ]
    assert result.problem_records[0].fasta_bases == "G"


def test_real_providers_validate_bgzipped_vcf_without_variant_index(tmp_path: Path) -> None:
    fasta = tmp_path / "reference.fa"
    source = tmp_path / "variants.vcf"
    compressed = tmp_path / "variants.vcf.gz"
    _write_fasta(fasta)
    _write_vcf(source)

    module = cast(_PysamCompressionModule, import_module("pysam"))
    module.tabix_compress(str(source), str(compressed), True)

    result = _evaluate(compressed, fasta)

    assert result.record_count == 6
    assert not Path(f"{compressed}.tbi").exists()
    assert not Path(f"{compressed}.csi").exists()


def test_authoritative_reader_does_not_create_or_trust_adjacent_fai(tmp_path: Path) -> None:
    fasta = tmp_path / "reference.fa"
    vcf = tmp_path / "variants.vcf"
    _write_fasta(fasta)
    vcf.write_text(
        """##fileformat=VCFv4.5
##contig=<ID=chr1,length=8>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t8\t.\tT\tC\t.\tPASS\t.
""",
        encoding="utf-8",
    )
    adjacent = Path(f"{fasta}.fai")
    stale_fai = "chr1\t4\t6\t8\t9\n"
    adjacent.write_text(stale_fai, encoding="utf-8")

    result = _evaluate(vcf, fasta)

    assert result.record_count == 1
    assert result.match_count == 1
    assert result.out_of_bounds_count == 0
    assert result.problem_records == ()
    assert adjacent.read_text(encoding="utf-8") == stale_fai
