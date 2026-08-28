"""Tests for conservative offline CRAM reference planning."""

from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    ArtifactIdentity,
    CollectionCompleteness,
    CramOfflineReferenceAction,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ReferenceContext,
    Resource,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceDictionaryRecord,
    SnapshotSequence,
)
from refcompat.reasoning import build_reference_context, plan_cram_offline_reference

_FASTA = ResourceId("fasta")
_CRAM = ResourceId("reads")
_MD5_A = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_B = Md5Digest("2f803268a6367d0943978eb5f84cc62e")
_MD5_C = Md5Digest("b41c1949bef0cb7c83998d0a5d83bcc2")


def _request_and_context(
    anchor_path: Path,
    *,
    kind: ResourceKind = ResourceKind.CRAM,
    scope_names: tuple[str, ...] | None = None,
) -> tuple[EvaluationRequest, ReferenceContext]:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(anchor_path)),
        Resource(_CRAM, kind, ArtifactIdentity(Path("reads.cram"))),
    )
    request = EvaluationRequest(
        resources,
        _FASTA,
        EvaluationScope((_FASTA, _CRAM), scope_names),
    )
    anchor_snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 4, 0, md5=_MD5_A),
            SnapshotSequence("chr2", 4, 1, md5=_MD5_B),
        ),
    )
    return request, build_reference_context(request, anchor_snapshot)


def _cram(*records: SequenceDictionaryRecord) -> AlignmentHeaderSnapshot:
    return AlignmentHeaderSnapshot(
        _CRAM,
        ResourceKind.CRAM,
        AlignmentHeaderData(sequences=records),
    )


def test_exact_m5_verified_dictionary_can_use_explicit_local_anchor(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n>chr2\nTGCA\n")
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(
        _cram(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
        ),
        context,
        request,
    )

    assert plan.action is CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR
    assert plan.anchor_path_readable
    assert plan.reference_path == anchor_path


def test_verified_subset_can_use_full_local_anchor(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n>chr2\nTGCA\n")
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(
        _cram(SequenceDictionaryRecord("chr1", 4, md5=_MD5_A)),
        context,
        request,
    )

    assert plan.action is CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR


def test_cross_name_m5_identity_does_not_prove_provider_addressability(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n>chr2\nTGCA\n")
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(
        _cram(SequenceDictionaryRecord("1", 4, md5=_MD5_A)),
        context,
        request,
    )

    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING
    assert plan.reference_path is None


def test_missing_m5_defers_reference_dependent_decoding(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n")
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(
        _cram(SequenceDictionaryRecord("chr1", 4)),
        context,
        request,
    )

    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING


@pytest.mark.parametrize(
    "record",
    [
        SequenceDictionaryRecord("chr1", 5, md5=_MD5_A),
        SequenceDictionaryRecord("chr1", 4, md5=_MD5_C),
        SequenceDictionaryRecord("extra", 4, md5=_MD5_C),
    ],
)
def test_conflicting_or_extra_dictionary_defers_reference_dependent_decoding(
    tmp_path: Path,
    record: SequenceDictionaryRecord,
) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n>chr2\nTGCA\n")
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(_cram(record), context, request)

    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING


def test_unreadable_anchor_path_defers_even_for_verified_header(tmp_path: Path) -> None:
    anchor_path = tmp_path / "missing.fa"
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(
        _cram(SequenceDictionaryRecord("chr1", 4, md5=_MD5_A)),
        context,
        request,
    )

    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING
    assert not plan.anchor_path_readable


def test_declared_ur_is_not_an_automatic_offline_reference_source(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n")
    alternate_path = tmp_path / "header-reference.fa"
    alternate_path.write_text(">chr1\nACGT\n")
    request, context = _request_and_context(anchor_path)

    plan = plan_cram_offline_reference(
        _cram(
            SequenceDictionaryRecord(
                "chr1",
                4,
                uri=alternate_path.as_uri(),
            )
        ),
        context,
        request,
    )

    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING
    assert plan.reference_path is None


def test_bam_snapshot_is_not_valid_for_cram_reference_planning(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.fa"
    anchor_path.write_text(">chr1\nACGT\n")
    request, context = _request_and_context(anchor_path, kind=ResourceKind.BAM)
    snapshot = AlignmentHeaderSnapshot(
        _CRAM,
        ResourceKind.BAM,
        AlignmentHeaderData(sequences=(SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),)),
    )

    with pytest.raises(ValueError, match="requires a CRAM snapshot"):
        plan_cram_offline_reference(snapshot, context, request)
