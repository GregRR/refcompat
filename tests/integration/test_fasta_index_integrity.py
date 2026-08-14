import socket
from pathlib import Path

import pytest

from refcompat.inspectors.fasta_index import (
    FastaIndexComputationError,
    compute_expected_fasta_index,
    read_fasta_index,
)
from refcompat.model.fasta_index import FastaIndexDifferenceKind, FastaIndexRecord
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.reasoning.fasta_index import evaluate_fasta_index_integrity

FIXTURES = Path(__file__).parents[1] / "fixtures" / "fai"


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def test_htslib_known_answer_fai_and_refget_computation_agree() -> None:
    """Cross-check refget/gtars against the canonical HTSlib faidx(5) example."""

    fasta_path = FIXTURES / "htslib_example.fa"
    index_path = FIXTURES / "htslib_example.fa.fai"
    fasta = _resource(fasta_path, ResourceKind.FASTA)
    index = _resource(index_path, ResourceKind.FASTA_INDEX)

    observed = read_fasta_index(index)
    expected = compute_expected_fasta_index(fasta)

    known_answer = (
        FastaIndexRecord("one", 66, 5, 30, 31),
        FastaIndexRecord("two", 28, 98, 14, 15),
    )
    assert observed.resource_id == index.id
    assert expected.fasta_resource_id == fasta.id
    assert observed.records == known_answer
    assert expected.records == known_answer
    assert all(record.__class__.__module__.startswith("refcompat.") for record in expected.records)

    result = evaluate_fasta_index_integrity(
        expected=expected,
        observed=observed,
    )
    assert result.verified


def test_fasta_index_computation_does_not_attempt_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fasta_path = FIXTURES / "htslib_example.fa"
    fasta = _resource(fasta_path, ResourceKind.FASTA)
    attempts: list[tuple[object, ...]] = []

    def fail_connect(self: socket.socket, *args: object, **kwargs: object) -> None:
        attempts.append(args)
        raise AssertionError("FAI computation attempted network access")

    monkeypatch.setattr(socket.socket, "connect", fail_connect)

    data = compute_expected_fasta_index(fasta)
    assert len(data.records) == 2
    assert attempts == []


def test_same_sequence_content_with_different_wrapping_is_layout_mismatch_only(
    tmp_path: Path,
) -> None:
    wrapped_path = tmp_path / "wrapped.fa"
    unwrapped_path = tmp_path / "unwrapped.fa"
    unwrapped_index_path = tmp_path / "unwrapped.fa.fai"

    wrapped_path.write_text(">chr1\nACGT\nACGT\n", encoding="utf-8")
    unwrapped_path.write_text(">chr1\nACGTACGT\n", encoding="utf-8")
    # Independent known geometry for the unwrapped representation.
    unwrapped_index_path.write_text("chr1\t8\t6\t8\t9\n", encoding="utf-8")

    wrapped = _resource(wrapped_path, ResourceKind.FASTA)
    unwrapped = _resource(unwrapped_path, ResourceKind.FASTA)
    unwrapped_index = _resource(unwrapped_index_path, ResourceKind.FASTA_INDEX)

    wrapped_expected = compute_expected_fasta_index(wrapped)
    unwrapped_expected = compute_expected_fasta_index(unwrapped)
    observed_unwrapped = read_fasta_index(unwrapped_index)

    assert wrapped_expected.records == (FastaIndexRecord("chr1", 8, 6, 4, 5),)
    assert unwrapped_expected.records == observed_unwrapped.records

    result = evaluate_fasta_index_integrity(
        expected=wrapped_expected,
        observed=observed_unwrapped,
    )
    assert {difference.kind for difference in result.differences} == {
        FastaIndexDifferenceKind.LINE_BASES,
        FastaIndexDifferenceKind.LINE_BYTES,
    }


def test_zero_length_sequence_is_computation_limitation(tmp_path: Path) -> None:
    path = tmp_path / "zero-length.fa"
    path.write_text(">chr1\n>chr2\nACGT\n", encoding="utf-8")

    with pytest.raises(FastaIndexComputationError, match="zero-length FASTA sequence: chr1"):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


def test_compute_expected_fasta_index_is_deterministic() -> None:
    fasta_path = FIXTURES / "htslib_example.fa"
    fasta = _resource(fasta_path, ResourceKind.FASTA)

    first = compute_expected_fasta_index(fasta)
    second = compute_expected_fasta_index(fasta)

    assert first == second


def test_crlf_fasta_geometry_counts_two_terminator_bytes(tmp_path: Path) -> None:
    path = tmp_path / "crlf.fa"
    path.write_bytes(b">chr1\r\nACGT\r\nACGT\r\n")

    computed = compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))

    assert computed.records == (FastaIndexRecord("chr1", 8, 7, 4, 6),)
