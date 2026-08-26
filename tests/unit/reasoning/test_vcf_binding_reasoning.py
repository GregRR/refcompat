"""Tests for evidence-backed VCF sequence-name binding."""

from pathlib import Path

from refcompat.model import (
    ArtifactIdentity,
    CollectionCompleteness,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ReferenceContext,
    Resource,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceIdentityProvenance,
    SnapshotSequence,
    VcfChromUsage,
    VcfContextSnapshot,
    VcfContigDeclaration,
    VcfHeaderData,
)
from refcompat.reasoning import build_reference_context
from refcompat.reasoning.vcf_binding import (
    derive_vcf_sequence_bindings,
    vcf_binding_identity_capabilities,
)

_FASTA = ResourceId("fasta")
_VCF = ResourceId("variants")
_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_TTTT = Md5Digest("2f803268a6367d0943978eb5f84cc62e")


def _context(
    *sequences: SnapshotSequence,
    scope_names: tuple[str, ...] | None = None,
) -> ReferenceContext:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(
        resources,
        _FASTA,
        EvaluationScope((_FASTA, _VCF), scope_names),
    )
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )
    return build_reference_context(request, snapshot)


def _vcf(*contigs: VcfContigDeclaration, used_name: str = "1") -> VcfContextSnapshot:
    return VcfContextSnapshot(
        _VCF,
        VcfHeaderData("VCFv4.5", contigs=contigs),
        record_count=1,
        chrom_usage=(VcfChromUsage(used_name, 1),),
    )


def test_unique_declared_md5_derives_cross_name_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _vcf(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value))

    capabilities = vcf_binding_identity_capabilities(snapshot, context)
    bindings = derive_vcf_sequence_bindings(snapshot, context)

    assert len(capabilities) == 1
    assert capabilities[0].provenance is SequenceIdentityProvenance.DECLARED_METADATA
    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "1"
    assert bindings[0].anchor_sequence_name == "chr1"
    assert bindings[0].identity_values == (_MD5_ACGT,)


def test_familiar_name_without_identity_does_not_bind() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _vcf(VcfContigDeclaration("1", length=4))

    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_invalid_declared_md5_does_not_bind() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _vcf(VcfContigDeclaration("1", length=4, md5="not-an-md5"))

    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_duplicate_anchor_content_does_not_bind_even_when_scope_hides_duplicate() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chrDup", 4, 1, md5=_MD5_ACGT),
        scope_names=("chr1",),
    )
    snapshot = _vcf(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value))

    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_unique_target_outside_anchor_scope_does_not_bind() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chr2", 4, 1, md5=_MD5_TTTT),
        scope_names=("chr1",),
    )
    snapshot = _vcf(VcfContigDeclaration("2", length=4, md5=_MD5_TTTT.value), used_name="2")

    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_declared_length_conflict_prevents_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _vcf(VcfContigDeclaration("1", length=5, md5=_MD5_ACGT.value))

    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_same_name_identity_does_not_create_unnecessary_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _vcf(
        VcfContigDeclaration("chr1", length=4, md5=_MD5_ACGT.value),
        used_name="chr1",
    )

    assert vcf_binding_identity_capabilities(snapshot, context) == ()
    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_declared_but_unused_identity_does_not_create_binding_capability() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chr2", 4, 1, md5=_MD5_TTTT),
    )
    snapshot = _vcf(
        VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),
        VcfContigDeclaration("2", length=4, md5=_MD5_TTTT.value),
        used_name="1",
    )

    capabilities = vcf_binding_identity_capabilities(snapshot, context)

    assert tuple(capability.sequence_name for capability in capabilities) == ("1",)


def test_incomplete_anchor_md5_coverage_does_not_manufacture_uniqueness() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("unknown", 4, 1),
    )
    snapshot = _vcf(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value))

    assert derive_vcf_sequence_bindings(snapshot, context) == ()


def test_verified_identity_can_override_misleading_same_string_name() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chr2", 4, 1, md5=_MD5_TTTT),
    )
    snapshot = _vcf(
        VcfContigDeclaration("chr1", length=4, md5=_MD5_TTTT.value),
        used_name="chr1",
    )

    bindings = derive_vcf_sequence_bindings(snapshot, context)

    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "chr1"
    assert bindings[0].anchor_sequence_name == "chr2"
    assert bindings[0].identity_values == (_MD5_TTTT,)


def test_two_local_names_can_bind_to_one_unique_anchor_sequence() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(
                VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),
                VcfContigDeclaration("chrOne", length=4, md5=_MD5_ACGT.value),
            ),
        ),
        record_count=2,
        chrom_usage=(VcfChromUsage("1", 1), VcfChromUsage("chrOne", 1)),
    )

    bindings = derive_vcf_sequence_bindings(snapshot, context)

    assert tuple(
        (binding.local_sequence_name, binding.anchor_sequence_name) for binding in bindings
    ) == (("1", "chr1"), ("chrOne", "chr1"))
