"""Tests for conservative GFF3 embedded-FASTA sequence binding."""

from pathlib import Path

import pytest

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationSequenceUsage,
    Gff3EmbeddedFastaSequence,
    Gff3FastaBoundary,
    Gff3SequenceRegion,
)
from refcompat.model.contracts import (
    CapabilityId,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.identity import (
    CollectionCompleteness,
    Md5Digest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.reasoning.annotation_binding import (
    annotation_binding_identity_capabilities,
    annotation_embedded_identity_capabilities,
    derive_annotation_sequence_bindings,
)
from refcompat.reasoning.reference_context import build_reference_context

_ANNOTATION = ResourceId("annotation")
_FASTA = ResourceId("fasta")
_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_TTTT = Md5Digest("2f803268a6367d0943978eb5f84cc62e")


def _snapshot(
    local_name: str = "1",
    *,
    embedded: tuple[Gff3EmbeddedFastaSequence, ...] | None = None,
) -> AnnotationContextSnapshot:
    return AnnotationContextSnapshot(
        _ANNOTATION,
        ResourceKind.GFF3,
        feature_count=1,
        sequence_usage=(AnnotationSequenceUsage(local_name, local_name, 1, 1, 4, 1),),
        embedded_fasta_sequences=(
            embedded
            if embedded is not None
            else (Gff3EmbeddedFastaSequence(local_name, 4, _MD5_ACGT, 3),)
        ),
        fasta_boundary=Gff3FastaBoundary(2, True),
    )


def _context(
    *sequences: SnapshotSequence,
    scope_names: tuple[str, ...] | None = None,
) -> ReferenceContext:
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    annotation = Resource(
        _ANNOTATION,
        ResourceKind.GFF3,
        ArtifactIdentity(Path("genes.gff3")),
    )
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION), anchor_sequence_names=scope_names),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )
    return build_reference_context(request, anchor)


def test_embedded_fasta_identity_is_content_derived_only_for_relevant_seqids() -> None:
    snapshot = _snapshot(
        embedded=(
            Gff3EmbeddedFastaSequence("1", 4, _MD5_ACGT, 3),
            Gff3EmbeddedFastaSequence("target-protein", 4, _MD5_TTTT, 5),
        )
    )

    capabilities = annotation_embedded_identity_capabilities(snapshot)

    assert len(capabilities) == 1
    assert capabilities[0].sequence_name == "1"
    assert capabilities[0].identity == _MD5_ACGT
    assert capabilities[0].provenance is SequenceIdentityProvenance.CONTENT_DERIVED


def test_sequence_region_only_seqid_can_contribute_embedded_identity() -> None:
    snapshot = AnnotationContextSnapshot(
        _ANNOTATION,
        ResourceKind.GFF3,
        feature_count=0,
        sequence_regions=(Gff3SequenceRegion("1", "1", 1, 4, 1),),
        fasta_boundary=Gff3FastaBoundary(2, True),
        embedded_fasta_sequences=(Gff3EmbeddedFastaSequence("1", 4, _MD5_ACGT, 3),),
    )

    capabilities = annotation_embedded_identity_capabilities(snapshot)

    assert len(capabilities) == 1
    assert capabilities[0].sequence_name == "1"
    assert capabilities[0].identity == _MD5_ACGT


def test_unique_full_anchor_identity_creates_cross_name_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))

    bindings = derive_annotation_sequence_bindings(_snapshot(), context)

    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "1"
    assert bindings[0].anchor_sequence_name == "chr1"
    assert bindings[0].identity_values == (_MD5_ACGT,)


def test_duplicate_full_anchor_identity_blocks_binding() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chrDup", 4, 1, md5=_MD5_ACGT),
    )

    assert derive_annotation_sequence_bindings(_snapshot(), context) == ()


def test_incomplete_anchor_md5_coverage_does_not_manufacture_binding() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("unknown", 4, 1),
    )

    assert derive_annotation_sequence_bindings(_snapshot(), context) == ()


def test_anchor_scope_cannot_manufacture_uniqueness() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chrDup", 4, 1, md5=_MD5_ACGT),
        scope_names=("chr1",),
    )

    assert derive_annotation_sequence_bindings(_snapshot(), context) == ()


def test_unique_target_outside_anchor_scope_does_not_bind() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("other", 4, 1, md5=_MD5_TTTT),
        scope_names=("other",),
    )

    assert derive_annotation_sequence_bindings(_snapshot(), context) == ()


def test_exact_same_name_identity_does_not_create_redundant_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))

    assert derive_annotation_sequence_bindings(_snapshot("chr1"), context) == ()


def test_gtf_never_exposes_embedded_fasta_identity_capability() -> None:
    snapshot = AnnotationContextSnapshot(
        _ANNOTATION,
        ResourceKind.GTF,
        feature_count=1,
        sequence_usage=(AnnotationSequenceUsage("1", "1", 1, 1, 4, 1),),
    )

    assert annotation_embedded_identity_capabilities(snapshot) == ()


def test_gtf_can_bind_from_independently_content_derived_identity() -> None:
    snapshot = AnnotationContextSnapshot(
        _ANNOTATION,
        ResourceKind.GTF,
        feature_count=1,
        sequence_usage=(AnnotationSequenceUsage("1", "1", 1, 1, 4, 1),),
    )
    capability = SequenceIdentityCapability(
        CapabilityId("external-content:1"),
        _ANNOTATION,
        "1",
        _MD5_ACGT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))

    bindings = derive_annotation_sequence_bindings(
        snapshot,
        context,
        binding_identity_capabilities=(capability,),
    )

    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "1"
    assert bindings[0].anchor_sequence_name == "chr1"


def test_additional_annotation_binding_identity_must_be_content_derived() -> None:
    snapshot = _snapshot(embedded=())
    capability = SequenceIdentityCapability(
        CapabilityId("declared:1"),
        _ANNOTATION,
        "1",
        _MD5_ACGT,
        SequenceIdentityProvenance.DECLARED_METADATA,
    )

    with pytest.raises(ValueError, match="must be content-derived"):
        annotation_binding_identity_capabilities(snapshot, (capability,))


def test_additional_annotation_binding_identity_must_be_reference_relevant() -> None:
    snapshot = _snapshot(embedded=())
    capability = SequenceIdentityCapability(
        CapabilityId("external-content:unused"),
        _ANNOTATION,
        "unused",
        _MD5_ACGT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    with pytest.raises(ValueError, match="must be reference-relevant"):
        annotation_binding_identity_capabilities(snapshot, (capability,))


def test_additional_annotation_binding_identity_must_belong_to_annotation() -> None:
    snapshot = _snapshot(embedded=())
    capability = SequenceIdentityCapability(
        CapabilityId("external-content:wrong-resource"),
        ResourceId("other"),
        "1",
        _MD5_ACGT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    with pytest.raises(ValueError, match="must belong to the annotation"):
        annotation_binding_identity_capabilities(snapshot, (capability,))


def test_additional_annotation_binding_identity_ids_must_be_unique() -> None:
    snapshot = _snapshot(embedded=())
    first = SequenceIdentityCapability(
        CapabilityId("external-content:duplicate"),
        _ANNOTATION,
        "1",
        _MD5_ACGT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    second = SequenceIdentityCapability(
        CapabilityId("external-content:duplicate"),
        _ANNOTATION,
        "1",
        _MD5_TTTT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    with pytest.raises(ValueError, match="IDs must be unique"):
        annotation_binding_identity_capabilities(snapshot, (first, second))
