"""End-to-end scientific-parity coverage for Milestone 8 BCF RCHECK-050 reuse."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest

from refcompat.inspectors.vcf import inspect_vcf_context, iter_vcf_ref_records
from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityVerdict,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceBinding,
    SequenceBindingMethod,
    SequenceCollectionSnapshot,
    SnapshotSequence,
    VcfContextSnapshot,
    VcfContractProjection,
    VcfRefConflictPattern,
    VcfRefValidationResult,
    VerdictAggregation,
)
from refcompat.reasoning import (
    aggregate_bundle_verdict,
    build_reference_context,
    derive_vcf_sequence_bindings,
    evaluate_vcf_ref_records,
    project_vcf_contract,
    reason_bundle,
)

_FASTA = ResourceId("reference")
_VARIANTS = ResourceId("variants")
_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")


class _Reference:
    @property
    def resource_id(self) -> ResourceId:
        return _FASTA

    def sequence_length(self, sequence_name: str) -> int | None:
        return 4 if sequence_name == "chr1" else None

    def fetch(self, sequence_name: str, start: int, end: int) -> str:
        assert sequence_name == "chr1"
        return "ACGT"[start:end]


@dataclass(frozen=True, slots=True)
class _VariantReasoning:
    snapshot: VcfContextSnapshot
    bindings: tuple[SequenceBinding, ...]
    validation: VcfRefValidationResult
    projection: VcfContractProjection
    bundle: BundleReasoningResult
    verdict: VerdictAggregation


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(_VARIANTS, kind, ArtifactIdentity(path))


def _write_vcf(path: Path, *, first_ref: str) -> None:
    path.write_text(
        "\n".join(
            (
                "##fileformat=VCFv4.2",
                f"##contig=<ID=1,length=4,md5={_MD5_ACGT.value}>",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                f"1\t2\t.\t{first_ref}\tA\t.\tPASS\t.",
                "1\t4\t.\tT\tA\t.\tPASS\t.",
                "",
            )
        ),
        encoding="ascii",
    )


def _convert_to_bcf(vcf_path: Path, bcf_path: Path) -> None:
    pysam = cast(Any, import_module("pysam"))
    with (
        pysam.VariantFile(str(vcf_path)) as source,
        pysam.VariantFile(str(bcf_path), "wb", header=source.header) as target,
    ):
        for record in source:
            target.write(record)


def _reason(path: Path, kind: ResourceKind) -> _VariantReasoning:
    variants = _resource(path, kind)
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("reference.fa")))
    request = EvaluationRequest(
        resources=(fasta, variants),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _VARIANTS)),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),),
    )
    context = build_reference_context(request, anchor)
    snapshot = inspect_vcf_context(variants)
    bindings = derive_vcf_sequence_bindings(snapshot, context)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VARIANTS,
        fasta_resource_id=_FASTA,
        records=iter_vcf_ref_records(variants),
        reference=_Reference(),
        sequence_bindings=bindings,
    )
    projection = project_vcf_contract(
        snapshot,
        validation,
        context,
        sequence_bindings=bindings,
    )
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.reference_base_capability,),
    )
    return _VariantReasoning(
        snapshot=snapshot,
        bindings=bindings,
        validation=validation,
        projection=projection,
        bundle=bundle,
        verdict=aggregate_bundle_verdict(bundle),
    )


def _assert_scientific_parity(vcf: _VariantReasoning, bcf: _VariantReasoning) -> None:
    assert bcf.snapshot == vcf.snapshot
    assert bcf.bindings == vcf.bindings
    assert bcf.validation == vcf.validation
    assert bcf.projection == vcf.projection
    assert bcf.bundle.contracts == vcf.bundle.contracts
    assert bcf.bundle.reference_context == vcf.bundle.reference_context
    assert bcf.bundle.sequence_bindings == vcf.bundle.sequence_bindings
    assert bcf.bundle.constraints == vcf.bundle.constraints
    assert bcf.bundle.evaluations == vcf.bundle.evaluations
    assert bcf.bundle.evidence == vcf.bundle.evidence
    assert bcf.bundle.interpretation == vcf.bundle.interpretation
    assert bcf.bundle.derived_capabilities == vcf.bundle.derived_capabilities
    assert bcf.bundle.supplemental_capabilities == vcf.bundle.supplemental_capabilities
    assert bcf.verdict == vcf.verdict


@pytest.mark.parametrize(
    ("first_ref", "expected_verdict", "expected_pattern"),
    [
        ("C", CompatibilityVerdict.COMPATIBLE, VcfRefConflictPattern.NONE),
        ("T", CompatibilityVerdict.INCOMPATIBLE, VcfRefConflictPattern.ISOLATED),
    ],
)
def test_bcf_reuses_vcf_rcheck050_science_end_to_end(
    tmp_path: Path,
    first_ref: str,
    expected_verdict: CompatibilityVerdict,
    expected_pattern: VcfRefConflictPattern,
) -> None:
    vcf_path = tmp_path / "variants.vcf"
    bcf_path = tmp_path / "variants.bcf"
    _write_vcf(vcf_path, first_ref=first_ref)
    _convert_to_bcf(vcf_path, bcf_path)

    vcf = _reason(vcf_path, ResourceKind.VCF)
    bcf = _reason(bcf_path, ResourceKind.BCF)

    _assert_scientific_parity(vcf, bcf)
    assert bcf.bindings[0].method is SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
    assert bcf.bindings[0].local_sequence_name == "1"
    assert bcf.bindings[0].anchor_sequence_name == "chr1"
    assert bcf.validation.record_count == 2
    assert bcf.validation.sequence_binding_ids == (bcf.bindings[0].id,)
    assert bcf.projection.conflict_pattern.pattern is expected_pattern
    assert bcf.verdict.verdict is expected_verdict
    assert not Path(f"{bcf_path}.csi").exists()


def test_bcf_pos_two_reaches_the_same_zero_based_fasta_base_as_vcf(tmp_path: Path) -> None:
    vcf_path = tmp_path / "variants.vcf"
    bcf_path = tmp_path / "variants.bcf"
    _write_vcf(vcf_path, first_ref="C")
    _convert_to_bcf(vcf_path, bcf_path)

    bcf = _reason(bcf_path, ResourceKind.BCF)

    assert bcf.validation.match_count == 2
    assert bcf.validation.mismatch_count == 0
    assert bcf.validation.out_of_bounds_count == 0
    assert bcf.validation.unresolved_sequence_count == 0
