from pathlib import Path
from types import SimpleNamespace

import pytest

from refcompat.inspectors.fasta_index import (
    FastaIndexComputationError,
    FastaIndexParseError,
    FastaIndexProviderIncompatibleError,
    FastaIndexUnreadableError,
    UnsupportedFastaIndexRepresentationError,
    UnsupportedFastaIndexResourceError,
    compute_expected_fasta_index,
    read_fasta_index,
)
from refcompat.model.fasta_index import FastaIndexRecord
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def test_read_fasta_index_parses_five_column_records(tmp_path: Path) -> None:
    path = tmp_path / "reference.fa.fai"
    path.write_text("chr1\t8\t6\t4\t5\nchr2\t4\t22\t4\t5\n", encoding="utf-8")

    data = read_fasta_index(_resource(path, ResourceKind.FASTA_INDEX))

    assert data.resource_id == ResourceId(path.name)
    assert data.records == (
        FastaIndexRecord("chr1", 8, 6, 4, 5),
        FastaIndexRecord("chr2", 4, 22, 4, 5),
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "chr1 8 6 4 5\n",
        "chr1\t8\t6\t4\n",
        "chr1\t8\t6\t4\t5\textra\n",
        "chr1\teight\t6\t4\t5\n",
        "chr1\t8\t6\t4\t3\n",
        "chr1\t8\t6\t4\t5\nchr1\t8\t6\t4\t5\n",
        "\n",
    ],
)
def test_read_fasta_index_rejects_invalid_structure(tmp_path: Path, text: str) -> None:
    path = tmp_path / "bad.fa.fai"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(FastaIndexParseError):
        read_fasta_index(_resource(path, ResourceKind.FASTA_INDEX))


def test_read_fasta_index_rejects_non_utf8_text(tmp_path: Path) -> None:
    path = tmp_path / "bad.fa.fai"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(FastaIndexParseError):
        read_fasta_index(_resource(path, ResourceKind.FASTA_INDEX))


def test_read_fasta_index_rejects_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.fa.fai"
    with pytest.raises(FastaIndexUnreadableError):
        read_fasta_index(_resource(path, ResourceKind.FASTA_INDEX))


def test_fasta_index_operations_reject_wrong_resource_kinds(tmp_path: Path) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")

    with pytest.raises(UnsupportedFastaIndexResourceError):
        read_fasta_index(_resource(path, ResourceKind.FASTA))

    with pytest.raises(UnsupportedFastaIndexResourceError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA_INDEX))


def test_compute_expected_fasta_index_rejects_provider_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")

    external_record = SimpleNamespace(name="chr1", length=4, fai=None)
    fake_module = SimpleNamespace(compute_fai=lambda _: [external_record])
    monkeypatch.setattr("refcompat.inspectors.fasta_index.import_module", lambda _: fake_module)

    with pytest.raises(FastaIndexProviderIncompatibleError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


def test_zero_length_missing_fai_metadata_is_computation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\n", encoding="utf-8")

    external_record = SimpleNamespace(name="chr1", length=0, fai=None)
    fake_module = SimpleNamespace(compute_fai=lambda _: [external_record])
    monkeypatch.setattr("refcompat.inspectors.fasta_index.import_module", lambda _: fake_module)

    with pytest.raises(FastaIndexComputationError, match="zero-length FASTA sequence: chr1"):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


def test_upstream_oserror_on_still_readable_fasta_is_computation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")

    def fail_compute(_: object) -> object:
        raise OSError("synthetic compute failure")

    fake_module = SimpleNamespace(compute_fai=fail_compute)
    monkeypatch.setattr("refcompat.inspectors.fasta_index.import_module", lambda _: fake_module)

    with pytest.raises(FastaIndexComputationError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


def test_upstream_oserror_after_fasta_disappears_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")

    def remove_then_fail(_: object) -> object:
        path.unlink()
        raise OSError("synthetic disappearance")

    fake_module = SimpleNamespace(compute_fai=remove_then_fail)
    monkeypatch.setattr("refcompat.inspectors.fasta_index.import_module", lambda _: fake_module)

    with pytest.raises(FastaIndexUnreadableError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


def test_compute_expected_fasta_index_rejects_compressed_fasta(tmp_path: Path) -> None:
    path = tmp_path / "reference.fa.gz"
    path.write_bytes(b"\x1f\x8bnot-a-real-gzip-stream")

    with pytest.raises(UnsupportedFastaIndexRepresentationError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


@pytest.mark.parametrize(
    "records",
    [
        [],
        [
            SimpleNamespace(
                name="",
                length=4,
                fai=SimpleNamespace(offset=2, line_bases=4, line_bytes=5),
            )
        ],
        [
            SimpleNamespace(
                name="chr1",
                length=4,
                fai=SimpleNamespace(offset=6, line_bases=4, line_bytes=5),
            ),
            SimpleNamespace(
                name="chr1",
                length=4,
                fai=SimpleNamespace(offset=17, line_bases=4, line_bytes=5),
            ),
        ],
    ],
)
def test_compute_expected_fasta_index_treats_input_derived_invalid_records_as_computation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, records: list[object]
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")
    fake_module = SimpleNamespace(compute_fai=lambda _: records)
    monkeypatch.setattr("refcompat.inspectors.fasta_index.import_module", lambda _: fake_module)

    with pytest.raises(FastaIndexComputationError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))


def test_compute_expected_fasta_index_rejects_missing_provider_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")
    monkeypatch.setattr(
        "refcompat.inspectors.fasta_index.import_module", lambda _: SimpleNamespace()
    )

    with pytest.raises(FastaIndexProviderIncompatibleError):
        compute_expected_fasta_index(_resource(path, ResourceKind.FASTA))
