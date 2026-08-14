"""Known-answer and boundary integration tests for the refget/SeqCol adapter."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

import refcompat.identity.refget as refget_adapter
from refcompat.identity import (
    Ga4ghRefgetIdentityProvider,
    IdentityProviderIncompatibleError,
    ReferenceParseError,
    ReferenceUnreadableError,
)
from refcompat.model.identity import CollectionCompleteness
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "fasta"


def _fasta_resource(path: Path) -> Resource:
    return Resource(
        id=ResourceId("reference"),
        kind=ResourceKind.FASTA,
        artifact=ArtifactIdentity(path),
    )


def test_ga4gh_known_answer_fasta_identity() -> None:
    """Match the refget 0.12 compliance fixture rather than a self-derived answer.

    The FASTA content and expected SeqCol/refget values are taken from the
    upstream BSD-2-Clause refget v0.12.0 compliance fixtures:
    https://github.com/refgenie/refget/blob/v0.12.0/test_fasta/base.fa
    https://github.com/refgenie/refget/blob/v0.12.0/test_fasta/test_fasta_digests.json
    """
    snapshot = Ga4ghRefgetIdentityProvider().inspect_fasta(
        _fasta_resource(_FIXTURES / "ga4gh_base.fa")
    )

    assert snapshot.completeness is CollectionCompleteness.COMPLETE
    assert snapshot.collection_digest is not None
    assert snapshot.names_digest is not None
    assert snapshot.lengths_digest is not None
    assert snapshot.sequences_digest is not None
    assert snapshot.collection_digest.value == "XZlrcEGi6mlopZ2uD8ObHkQB1d0oDwKk"
    assert snapshot.names_digest.value == "Fw1r9eRxfOZD98KKrhlYQNEdSRHoVxAG"
    assert snapshot.lengths_digest.value == "cGRMZIb3AVgkcAfNv39RN7hnT5Chk7RX"
    assert snapshot.sequences_digest.value == "0uDQVLuHaOZi1u76LjV__yrVUIz9Bwhr"
    assert snapshot.provider is not None
    assert snapshot.provider.name == "refget"
    assert snapshot.provider.version.startswith("0.12.")

    assert [(sequence.local_name, sequence.length) for sequence in snapshot.sequences] == [
        ("chrX", 8),
        ("chr1", 4),
        ("chr2", 4),
    ]
    assert [
        sequence.refget_id.value if sequence.refget_id is not None else None
        for sequence in snapshot.sequences
    ] == [
        "SQ.iYtREV555dUFKg2_agSJW6suquUyPpMw",
        "SQ.YBbVX0dLKG1ieEDCiMmkrTZFt_Z5Vdaj",
        "SQ.AcLxtBuKEPk_7PGE_H4dGElwZHCujwH6",
    ]
    assert [
        sequence.md5.value if sequence.md5 is not None else None for sequence in snapshot.sequences
    ] == [
        "5f63cfaa3ef61f88c9635fb9d18ec945",
        "31fc6ca291a32fb9df82b85e5f077e31",
        "92c6a56c9e9459d8a42b96f7884710bc",
    ]

    # The public domain snapshot must contain only RefCompat-owned immutable
    # values; upstream refget/gtars objects stop at the adapter boundary.
    assert snapshot.__class__.__module__.startswith("refcompat.")
    assert all(
        sequence.__class__.__module__.startswith("refcompat.") for sequence in snapshot.sequences
    )


def test_same_fasta_produces_deterministic_snapshot() -> None:
    provider = Ga4ghRefgetIdentityProvider()
    resource = _fasta_resource(_FIXTURES / "ga4gh_base.fa")
    assert provider.inspect_fasta(resource) == provider.inspect_fasta(resource)


def test_local_fasta_identity_does_not_attempt_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_connect(_socket: socket.socket, _address: object) -> None:
        raise AssertionError("local FASTA identity attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_connect)
    snapshot = Ga4ghRefgetIdentityProvider().inspect_fasta(
        _fasta_resource(_FIXTURES / "ga4gh_base.fa")
    )
    assert snapshot.sequences


@pytest.mark.parametrize("content", ["", "ACTGACTGACTG\n", "This is not a FASTA file.\n"])
def test_empty_or_headerless_input_is_normalized_as_parse_error(
    tmp_path: Path, content: str
) -> None:
    fasta = tmp_path / "malformed.fa"
    fasta.write_text(content)
    with pytest.raises(ReferenceParseError, match="contains no sequence records"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(fasta))


def test_anonymous_fasta_record_is_normalized_as_parse_error(tmp_path: Path) -> None:
    fasta = tmp_path / "anonymous.fa"
    fasta.write_text(">\nACGT\n")
    with pytest.raises(ReferenceParseError, match="without a local name"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(fasta))


def test_duplicate_fasta_sequence_names_are_rejected_as_ambiguous(tmp_path: Path) -> None:
    fasta = tmp_path / "duplicate.fa"
    fasta.write_text(">chr1\nACGT\n>chr1\nTGCA\n")
    with pytest.raises(ReferenceParseError, match="duplicate sequence name"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(fasta))


def test_missing_fasta_is_normalized_as_unreadable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.fa"
    with pytest.raises(ReferenceUnreadableError, match="cannot read FASTA"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(missing))


class _MissingShapeCollection:
    digest = "A" * 32


class _ShapeStubRefget:
    __version__ = "0.12.test"

    def digest_fasta(self, _fasta: str | Path) -> object:
        return _MissingShapeCollection()


class _OSErrorStubRefget:
    __version__ = "0.12.test"

    def __init__(self, *, delete_path: bool) -> None:
        self.delete_path = delete_path

    def digest_fasta(self, fasta: str | Path) -> object:
        path = Path(fasta)
        if self.delete_path:
            path.unlink()
        raise OSError("simulated upstream FASTA error")


def test_missing_provider_result_shape_is_provider_incompatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nACGT\n")
    monkeypatch.setattr(refget_adapter, "_load_refget", lambda: _ShapeStubRefget())
    with pytest.raises(
        IdentityProviderIncompatibleError, match="unsupported FASTA identity result"
    ):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(fasta))


def test_upstream_oserror_on_still_readable_file_is_parse_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nACGT\n")
    monkeypatch.setattr(
        refget_adapter,
        "_load_refget",
        lambda: _OSErrorStubRefget(delete_path=False),
    )
    with pytest.raises(ReferenceParseError, match="cannot parse FASTA"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(fasta))


def test_upstream_oserror_after_file_disappears_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nACGT\n")
    monkeypatch.setattr(
        refget_adapter,
        "_load_refget",
        lambda: _OSErrorStubRefget(delete_path=True),
    )
    with pytest.raises(ReferenceUnreadableError, match="cannot read FASTA"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(_fasta_resource(fasta))
