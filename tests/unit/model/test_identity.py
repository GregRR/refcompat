"""Tests for biological identity value invariants."""

from dataclasses import FrozenInstanceError

import pytest

from refcompat.model.identity import (
    CollectionCompleteness,
    Md5Digest,
    RefgetSequenceId,
    SeqColAttributeDigest,
    SeqColDigest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.resources import ResourceId


def test_refget_sequence_id_requires_sq_prefix() -> None:
    with pytest.raises(ValueError, match="SQ"):
        RefgetSequenceId("aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2")


def test_seqcol_digest_rejects_refget_sequence_identifier() -> None:
    with pytest.raises(ValueError, match="SeqCol"):
        SeqColDigest("SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2")


def test_md5_is_normalized_to_lowercase_and_immutable() -> None:
    digest = Md5Digest("5F63CFAA3EF61F88C9635FB9D18EC945")
    assert digest.value == "5f63cfaa3ef61f88c9635fb9d18ec945"
    with pytest.raises(FrozenInstanceError):
        digest.value = "0" * 32  # type: ignore[misc]


def test_sparse_snapshot_can_preserve_unknown_identity_fields() -> None:
    snapshot = SequenceCollectionSnapshot(
        resource_id=ResourceId("annotation"),
        completeness=CollectionCompleteness.USED_SUBSET,
        sequences=(SnapshotSequence(local_name="chr1"),),
    )

    assert snapshot.collection_digest is None
    assert snapshot.sequences[0].length is None
    assert snapshot.sequences[0].refget_id is None


def test_snapshot_rejects_partially_known_order() -> None:
    with pytest.raises(ValueError, match="all known or all unknown"):
        SequenceCollectionSnapshot(
            resource_id=ResourceId("mixed-order"),
            completeness=CollectionCompleteness.PARTIAL,
            sequences=(
                SnapshotSequence(local_name="chr1", ordinal=0),
                SnapshotSequence(local_name="chr2"),
            ),
        )


@pytest.mark.parametrize(
    "completeness",
    [
        CollectionCompleteness.PARTIAL,
        CollectionCompleteness.USED_SUBSET,
        CollectionCompleteness.UNKNOWN,
    ],
)
def test_sparse_snapshot_rejects_collection_level_digests(
    completeness: CollectionCompleteness,
) -> None:
    with pytest.raises(ValueError, match="collection-level SeqCol digests require"):
        SequenceCollectionSnapshot(
            resource_id=ResourceId("sparse"),
            completeness=completeness,
            collection_digest=SeqColDigest("A" * 32),
        )


def test_declared_complete_snapshot_can_preserve_collection_level_digests() -> None:
    snapshot = SequenceCollectionSnapshot(
        resource_id=ResourceId("declared"),
        completeness=CollectionCompleteness.DECLARED_COMPLETE,
        collection_digest=SeqColDigest("A" * 32),
        names_digest=SeqColAttributeDigest("B" * 32),
    )
    assert snapshot.collection_digest is not None
    assert snapshot.names_digest is not None
