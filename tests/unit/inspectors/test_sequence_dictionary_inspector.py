"""Unit tests for narrow SAM/Picard sequence-dictionary inspection."""

from __future__ import annotations

from pathlib import Path

import pytest

from refcompat.inspectors.sequence_dictionary import (
    SequenceDictionaryComputationError,
    SequenceDictionaryParseError,
    SequenceDictionaryUnreadableError,
    UnsupportedSequenceDictionaryResourceError,
    expected_sequence_dictionary_from_snapshot,
    read_sequence_dictionary,
)
from refcompat.model.identity import (
    CollectionCompleteness,
    Md5Digest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.sequence_dictionary import MoleculeTopology

_DEFAULT_MD5 = Md5Digest("31fc6ca291a32fb9df82b85e5f077e31")


def _dictionary_resource(path: Path) -> Resource:
    return Resource(
        id=ResourceId("dictionary"),
        kind=ResourceKind.SEQUENCE_DICTIONARY,
        artifact=ArtifactIdentity(path),
    )


def _complete_snapshot(
    *,
    name: str = "chr1",
    length: int = 4,
    md5: Md5Digest | None = _DEFAULT_MD5,
) -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        resource_id=ResourceId("reference"),
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence(
                local_name=name,
                length=length,
                ordinal=0,
                md5=md5,
            ),
        ),
    )


def test_read_sequence_dictionary_preserves_relevant_sq_metadata(tmp_path: Path) -> None:
    path = tmp_path / "reference.dict"
    path.write_text(
        "@HD\tVN:1.6\n"
        "@SQ\tSN:chrM\tLN:16569\tM5:d41d8cd98f00b204e9800998ecf8427e"
        "\tAN:MT,M,chrMT\tAS:GRCh38\tSP:Homo sapiens\tUR:file:reference.fa"
        "\tTP:circular\tAH:*\tZZ:ignored\n"
    )

    snapshot = read_sequence_dictionary(_dictionary_resource(path))
    assert snapshot.data.sam_version == "1.6"
    record = snapshot.records[0]
    assert record.name == "chrM"
    assert record.length == 16569
    assert record.md5 == Md5Digest("d41d8cd98f00b204e9800998ecf8427e")
    assert record.alternate_names == ("MT", "M", "chrMT")
    assert record.assembly == "GRCh38"
    assert record.species == "Homo sapiens"
    assert record.uri == "file:reference.fa"
    assert record.topology is MoleculeTopology.CIRCULAR
    assert record.alternate_locus == "*"


def test_dictionary_without_hd_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "reference.dict"
    path.write_text("@SQ\tSN:chr1\tLN:4\n")
    snapshot = read_sequence_dictionary(_dictionary_resource(path))
    assert snapshot.data.sam_version is None


def test_wrong_resource_kind_is_rejected(tmp_path: Path) -> None:
    resource = Resource(
        id=ResourceId("reference"),
        kind=ResourceKind.FASTA,
        artifact=ArtifactIdentity(tmp_path / "reference.fa"),
    )
    with pytest.raises(UnsupportedSequenceDictionaryResourceError):
        read_sequence_dictionary(resource)


def test_missing_dictionary_is_unreadable(tmp_path: Path) -> None:
    with pytest.raises(SequenceDictionaryUnreadableError, match="cannot read"):
        read_sequence_dictionary(_dictionary_resource(tmp_path / "missing.dict"))


def test_non_utf8_dictionary_is_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "reference.dict"
    path.write_bytes(b"@SQ\tSN:chr1\tLN:4\xff\n")
    with pytest.raises(SequenceDictionaryParseError, match="valid UTF-8"):
        read_sequence_dictionary(_dictionary_resource(path))


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("", "empty"),
        ("\n", "blank"),
        ("chr1\t4\n", "non-header"),
        ("@PG\tID:tool\n@SQ\tSN:chr1\tLN:4\n", "unexpected SAM header"),
        ("@SQX\tSN:chr1\tLN:4\n", "unexpected SAM header"),
        ("@SQ\tSN:chr1\tLN:4\n@HD\tVN:1.6\n", "@HD must appear"),
        ("@HD\tSO:unsorted\n@SQ\tSN:chr1\tLN:4\n", "valid VN"),
        ("@SQ\tSN:chr1\tSN:one\tLN:4\n", "duplicate SAM header tag"),
        ("@SQ\tLN:4\n", "requires SN and LN"),
        ("@SQ\tSN:chr1\n", "requires SN and LN"),
        ("@SQ\tSN:chr1\tLN:nope\n", "invalid @SQ LN"),
        ("@SQ\tSN:chr1\tLN:0\n", "invalid @SQ record"),
        ("@SQ\tSN:chr1\tLN:4\tM5:nope\n", "invalid @SQ record"),
        ("@SQ\tSN:chr1\tLN:4\tTP:unknown\n", "invalid @SQ record"),
        ("@SQ\tSN:chr 1\tLN:4\n", "invalid @SQ record"),
        ("@SQ\tSN:*chr1\tLN:4\n", "invalid @SQ record"),
        ("@SQ\tSN:=chr1\tLN:4\n", "invalid @SQ record"),
    ],
)
def test_malformed_dictionary_is_rejected(tmp_path: Path, content: str, match: str) -> None:
    path = tmp_path / "reference.dict"
    path.write_text(content)
    with pytest.raises(SequenceDictionaryParseError, match=match):
        read_sequence_dictionary(_dictionary_resource(path))


def test_duplicate_sn_or_an_across_records_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "reference.dict"
    path.write_text("@SQ\tSN:chr1\tLN:4\tAN:1\n@SQ\tSN:1\tLN:4\n")
    with pytest.raises(SequenceDictionaryParseError, match="invalid sequence dictionary"):
        read_sequence_dictionary(_dictionary_resource(path))


def test_expected_dictionary_is_derived_from_complete_snapshot() -> None:
    expected = expected_sequence_dictionary_from_snapshot(_complete_snapshot())
    assert expected.fasta_resource_id == ResourceId("reference")
    assert expected.records[0].name == "chr1"
    assert expected.records[0].length == 4
    assert expected.records[0].md5 == Md5Digest("31fc6ca291a32fb9df82b85e5f077e31")


def test_incomplete_snapshot_cannot_form_expected_dictionary() -> None:
    snapshot = SequenceCollectionSnapshot(
        resource_id=ResourceId("reference"),
        completeness=CollectionCompleteness.USED_SUBSET,
        sequences=(SnapshotSequence(local_name="chr1", length=4, ordinal=0),),
    )
    with pytest.raises(SequenceDictionaryComputationError, match="complete"):
        expected_sequence_dictionary_from_snapshot(snapshot)


@pytest.mark.parametrize(
    ("name", "length", "md5", "match"),
    [
        ("chr1", 0, Md5Digest("d41d8cd98f00b204e9800998ecf8427e"), "zero-length"),
        ("chr1", 4, None, "M5 identity is unavailable"),
        ("chr 1", 4, Md5Digest("31fc6ca291a32fb9df82b85e5f077e31"), "cannot be represented"),
    ],
)
def test_unrepresentable_fasta_snapshot_is_computation_error(
    name: str, length: int, md5: Md5Digest | None, match: str
) -> None:
    with pytest.raises(SequenceDictionaryComputationError, match=match):
        expected_sequence_dictionary_from_snapshot(
            _complete_snapshot(name=name, length=length, md5=md5)
        )
