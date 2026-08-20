"""Unit tests for authoritative FASTA random access through a temporary computed FAI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from refcompat.inspectors.fasta_sequence import (
    FastaSequenceFetchError,
    FastaSequenceProviderIncompatibleError,
    UnsupportedFastaSequenceResourceError,
    open_fasta_sequence_reader,
)
from refcompat.model.fasta_index import ComputedFastaIndex, FastaIndexData, FastaIndexRecord
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(path: Path, kind: ResourceKind = ResourceKind.FASTA) -> Resource:
    return Resource(ResourceId("reference"), kind, ArtifactIdentity(path))


def _computed() -> ComputedFastaIndex:
    return ComputedFastaIndex(
        ResourceId("reference"),
        FastaIndexData((FastaIndexRecord("chr1", 4, 6, 4, 5),)),
    )


def test_open_reader_uses_temporary_computed_fai_not_adjacent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nACGT\n", encoding="utf-8")
    adjacent = Path(f"{fasta}.fai")
    adjacent.write_text("stale\n", encoding="utf-8")
    captured_index: Path | None = None
    closed = False

    class FakeFastaFile:
        def __init__(self, filename: str, *, filepath_index: str) -> None:
            nonlocal captured_index
            assert filename == str(fasta)
            captured_index = Path(filepath_index)
            assert captured_index != adjacent
            assert captured_index.read_text(encoding="utf-8") == "chr1\t4\t6\t4\t5\n"

        def fetch(self, reference: str, start: int, end: int) -> str:
            assert reference == "chr1"
            return "ACGT"[start:end]

        def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(
        "refcompat.inspectors.fasta_sequence.compute_expected_fasta_index",
        lambda _: _computed(),
    )
    monkeypatch.setattr(
        "refcompat.inspectors.fasta_sequence.import_module",
        lambda _: SimpleNamespace(FastaFile=FakeFastaFile),
    )

    with open_fasta_sequence_reader(_resource(fasta)) as reader:
        assert reader.resource_id == ResourceId("reference")
        assert reader.sequence_length("chr1") == 4
        assert reader.sequence_length("missing") is None
        assert reader.fetch("chr1", 1, 3) == "CG"
        assert captured_index is not None and captured_index.exists()

    assert closed
    assert captured_index is not None and not captured_index.exists()
    assert adjacent.read_text(encoding="utf-8") == "stale\n"


def test_reader_rejects_wrong_resource_kind(tmp_path: Path) -> None:
    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")

    with pytest.raises(UnsupportedFastaSequenceResourceError):
        open_fasta_sequence_reader(_resource(path, ResourceKind.VCF))


def test_reader_normalizes_fetch_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nACGT\n", encoding="utf-8")

    class FakeFastaFile:
        def __init__(self, filename: str, *, filepath_index: str) -> None:
            pass

        def fetch(self, reference: str, start: int, end: int) -> str:
            raise IndexError("synthetic")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "refcompat.inspectors.fasta_sequence.compute_expected_fasta_index",
        lambda _: _computed(),
    )
    monkeypatch.setattr(
        "refcompat.inspectors.fasta_sequence.import_module",
        lambda _: SimpleNamespace(FastaFile=FakeFastaFile),
    )

    with (
        open_fasta_sequence_reader(_resource(fasta)) as reader,
        pytest.raises(FastaSequenceFetchError, match="cannot fetch"),
    ):
        reader.fetch("chr1", 0, 1)


def test_reader_rejects_provider_slice_with_wrong_length(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nACGT\n", encoding="utf-8")

    class FakeFastaFile:
        def __init__(self, filename: str, *, filepath_index: str) -> None:
            pass

        def fetch(self, reference: str, start: int, end: int) -> str:
            return ""

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "refcompat.inspectors.fasta_sequence.compute_expected_fasta_index",
        lambda _: _computed(),
    )
    monkeypatch.setattr(
        "refcompat.inspectors.fasta_sequence.import_module",
        lambda _: SimpleNamespace(FastaFile=FakeFastaFile),
    )

    with (
        open_fasta_sequence_reader(_resource(fasta)) as reader,
        pytest.raises(FastaSequenceProviderIncompatibleError, match="unexpected length"),
    ):
        reader.fetch("chr1", 0, 1)
