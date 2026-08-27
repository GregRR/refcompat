"""Tests for evidence-backed BAM/CRAM sequence-name binding."""

from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
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
    SequenceDictionaryRecord,
    SequenceIdentityProvenance,
    SnapshotSequence,
)
from refcompat.reasoning import build_reference_context
from refcompat.reasoning.alignment_binding import (
    alignment_binding_identity_capabilities,
    derive_alignment_sequence_bindings,
)

_FASTA = ResourceId("fasta")
_ALIGNMENT = ResourceId("reads")
_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_TTTT = Md5Digest("2f803268a6367d0943978eb5f84cc62e")


def _context(
    *sequences: SnapshotSequence,
    scope_names: tuple[str, ...] | None = None,
    alignment_kind: ResourceKind = ResourceKind.BAM,
) -> ReferenceContext:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_ALIGNMENT, alignment_kind, ArtifactIdentity(path=Path("reads.bam"))),
    )
    request = EvaluationRequest(
        resources,
        _FASTA,
        EvaluationScope((_FASTA, _ALIGNMENT), scope_names),
    )
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )
    return build_reference_context(request, snapshot)


def _alignment(
    *records: SequenceDictionaryRecord,
    kind: ResourceKind = ResourceKind.BAM,
    resource_id: ResourceId = _ALIGNMENT,
) -> AlignmentHeaderSnapshot:
    return AlignmentHeaderSnapshot(
        resource_id,
        kind,
        AlignmentHeaderData(sequences=records),
    )


@pytest.mark.parametrize("kind", [ResourceKind.BAM, ResourceKind.CRAM])
def test_unique_declared_m5_derives_cross_name_binding(kind: ResourceKind) -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        alignment_kind=kind,
    )
    snapshot = _alignment(
        SequenceDictionaryRecord(name="1", length=4, md5=_MD5_ACGT),
        kind=kind,
    )

    capabilities = alignment_binding_identity_capabilities(snapshot, context)
    bindings = derive_alignment_sequence_bindings(snapshot, context)

    assert len(capabilities) == 1
    assert capabilities[0].provenance is SequenceIdentityProvenance.DECLARED_METADATA
    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "1"
    assert bindings[0].anchor_sequence_name == "chr1"
    assert bindings[0].identity_values == (_MD5_ACGT,)


def test_alternate_name_without_m5_does_not_bind() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _alignment(SequenceDictionaryRecord(name="1", length=4, alternate_names=("chr1",)))

    assert derive_alignment_sequence_bindings(snapshot, context) == ()


def test_duplicate_anchor_content_does_not_bind_even_when_scope_hides_duplicate() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chrDup", 4, 1, md5=_MD5_ACGT),
        scope_names=("chr1",),
    )
    snapshot = _alignment(SequenceDictionaryRecord(name="1", length=4, md5=_MD5_ACGT))

    assert derive_alignment_sequence_bindings(snapshot, context) == ()


def test_unique_target_outside_anchor_scope_does_not_bind() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chr2", 4, 1, md5=_MD5_TTTT),
        scope_names=("chr1",),
    )
    snapshot = _alignment(SequenceDictionaryRecord(name="2", length=4, md5=_MD5_TTTT))

    assert derive_alignment_sequence_bindings(snapshot, context) == ()


def test_declared_length_conflict_prevents_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _alignment(SequenceDictionaryRecord(name="1", length=5, md5=_MD5_ACGT))

    assert derive_alignment_sequence_bindings(snapshot, context) == ()


def test_same_name_identity_does_not_create_unnecessary_binding() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _alignment(SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_ACGT))

    assert alignment_binding_identity_capabilities(snapshot, context) == ()
    assert derive_alignment_sequence_bindings(snapshot, context) == ()


def test_incomplete_anchor_m5_coverage_does_not_manufacture_uniqueness() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("unknown", 4, 1),
    )
    snapshot = _alignment(SequenceDictionaryRecord(name="1", length=4, md5=_MD5_ACGT))

    assert derive_alignment_sequence_bindings(snapshot, context) == ()


def test_verified_identity_can_override_misleading_same_string_name() -> None:
    context = _context(
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chr2", 4, 1, md5=_MD5_TTTT),
    )
    snapshot = _alignment(SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_TTTT))

    bindings = derive_alignment_sequence_bindings(snapshot, context)

    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "chr1"
    assert bindings[0].anchor_sequence_name == "chr2"
    assert bindings[0].identity_values == (_MD5_TTTT,)


def test_two_local_names_can_bind_to_one_unique_anchor_sequence() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _alignment(
        SequenceDictionaryRecord(name="1", length=4, md5=_MD5_ACGT),
        SequenceDictionaryRecord(name="chrOne", length=4, md5=_MD5_ACGT),
    )

    bindings = derive_alignment_sequence_bindings(snapshot, context)

    assert tuple(
        (binding.local_sequence_name, binding.anchor_sequence_name) for binding in bindings
    ) == (("1", "chr1"), ("chrOne", "chr1"))


def test_alignment_binding_rejects_anchor_resource_cross_wiring() -> None:
    context = _context(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT))
    snapshot = _alignment(
        SequenceDictionaryRecord(name="1", length=4, md5=_MD5_ACGT),
        resource_id=_FASTA,
    )

    with pytest.raises(ValueError, match="cannot be the FASTA anchor"):
        derive_alignment_sequence_bindings(snapshot, context)
