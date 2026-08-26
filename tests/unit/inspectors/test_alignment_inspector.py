"""Unit tests for the pysam-backed BAM/CRAM header observation boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from refcompat.inspectors.alignment import (
    AlignmentParseError,
    AlignmentProviderIncompatibleError,
    AlignmentUnreadableError,
    UnsupportedAlignmentResourceError,
    inspect_alignment_header,
)
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.sequence_dictionary import MoleculeTopology


def _resource(path: Path, kind: ResourceKind = ResourceKind.BAM) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def _header_text() -> str:
    return (
        "\n".join(
            (
                "@HD\tVN:1.6\tSO:coordinate\tGO:none\tSS:coordinate:natural",
                "@SQ\tSN:chr1\tLN:100\tM5:"
                + "a" * 32
                + "\tAN:1,chrOne\tAS:GRCh38\tUR:file:///refs/grch38.fa"
                "\tSP:Homo sapiens\tTP:linear\tAH:*",
                "@SQ\tSN:chr2\tLN:200",
                "@PG\tID:bwa\tPN:bwa\tVN:0.7.17\tCL:bwa mem reference.fa reads.fq",
                "@PG\tID:samtools\tPN:samtools\tPP:bwa\tVN:1.22",
            )
        )
        + "\n"
    )


def _fake_module(
    *,
    header_text: object | None = None,
    references: object = ("chr1", "chr2"),
    lengths: object = (100, 200),
    is_bam: object = True,
    is_cram: object = False,
    closed: list[bool] | None = None,
    calls: list[tuple[str, str, bool]] | None = None,
) -> SimpleNamespace:
    data = _header_text() if header_text is None else header_text

    class FakeAlignmentFile:
        def __init__(self, filename: str, mode: str, *, check_sq: bool) -> None:
            if calls is not None:
                calls.append((filename, mode, check_sq))
            self.text = data
            self.references = references
            self.lengths = lengths
            self.is_bam = is_bam
            self.is_cram = is_cram

        def close(self) -> None:
            if closed is not None:
                closed.append(True)

    return SimpleNamespace(__version__="0.24.0", AlignmentFile=FakeAlignmentFile)


def test_inspect_bam_header_copies_reference_and_program_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    calls: list[tuple[str, str, bool]] = []
    fake_module = _fake_module(calls=calls)
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    snapshot = inspect_alignment_header(_resource(path))

    assert calls == [(str(path), "rb", False)]
    assert snapshot.resource_kind is ResourceKind.BAM
    assert snapshot.header.sam_version == "1.6"
    assert snapshot.header.sort_order == "coordinate"
    assert snapshot.header.group_order == "none"
    assert snapshot.header.subsort == "coordinate:natural"
    assert snapshot.declared_sequence_names == ("chr1", "chr2")
    first = snapshot.header.sequences[0]
    assert first.length == 100
    assert first.md5 == Md5Digest("a" * 32)
    assert first.alternate_names == ("1", "chrOne")
    assert first.assembly == "GRCh38"
    assert first.uri == "file:///refs/grch38.fa"
    assert first.species == "Homo sapiens"
    assert first.topology is MoleculeTopology.LINEAR
    assert first.alternate_locus == "*"
    assert snapshot.header.sequences[1].length == 200
    assert [(program.id, program.previous_id) for program in snapshot.header.programs] == [
        ("bwa", None),
        ("samtools", "bwa"),
    ]


def test_inspect_cram_header_uses_header_only_open_without_reference_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.cram"
    path.write_bytes(b"synthetic")
    calls: list[tuple[str, str, bool]] = []
    fake_module = _fake_module(is_bam=False, is_cram=True, calls=calls)
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    snapshot = inspect_alignment_header(_resource(path, ResourceKind.CRAM))

    assert snapshot.resource_kind is ResourceKind.CRAM
    assert calls == [(str(path), "rc", False)]


def test_inspect_alignment_header_ignores_extension_tags_and_preserves_pg_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    header_text = (
        "\n".join(
            (
                "@HD\tVN:1.6\tzz:header-extension",
                "@SQ\tSN:chr1\tLN:100\tzz:sequence-extension",
                "@PG\tID:aligner\tCL:align --flag value\tVN:2\tDS:description\tzz:program-extension",
            )
        )
        + "\n"
    )
    fake_module = _fake_module(
        header_text=header_text,
        references=("chr1",),
        lengths=(100,),
    )
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    snapshot = inspect_alignment_header(_resource(path))

    assert snapshot.declared_sequence_names == ("chr1",)
    program = snapshot.header.programs[0]
    assert program.id == "aligner"
    assert program.command_line == "align --flag value"
    assert program.version == "2"
    assert program.description == "description"


def test_inspect_alignment_header_uses_binary_reference_dictionary_when_sq_text_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(
        header_text="@HD\tVN:1.6\n",
        references=("chr2", "chr1"),
        lengths=(200, 100),
    )
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    snapshot = inspect_alignment_header(_resource(path))

    assert snapshot.declared_sequence_names == ("chr2", "chr1")
    assert tuple(record.length for record in snapshot.header.sequences) == (200, 100)


def test_inspect_alignment_header_allows_empty_sq_dictionary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unmapped.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(
        header_text="@HD\tVN:1.6\n",
        references=(),
        lengths=(),
    )
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    snapshot = inspect_alignment_header(_resource(path))

    assert snapshot.header.sequences == ()
    assert snapshot.declared_sequence_names == ()


def test_inspect_alignment_header_rejects_text_binary_dictionary_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(
        header_text="@SQ\tSN:chr1\tLN:100\n",
        references=("chr1",),
        lengths=(101,),
    )
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    with pytest.raises(AlignmentProviderIncompatibleError, match="binary reference dictionary"):
        inspect_alignment_header(_resource(path))


def test_inspect_alignment_header_rejects_wrong_resource_kind(tmp_path: Path) -> None:
    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")

    with pytest.raises(UnsupportedAlignmentResourceError):
        inspect_alignment_header(_resource(path, ResourceKind.VCF))


def test_inspect_alignment_header_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AlignmentUnreadableError):
        inspect_alignment_header(_resource(tmp_path / "missing.bam"))


def test_inspect_alignment_header_rejects_resource_format_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(is_bam=False, is_cram=True)
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    with pytest.raises(AlignmentParseError, match="declared as BAM"):
        inspect_alignment_header(_resource(path))


def test_inspect_alignment_header_rejects_ambiguous_provider_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(is_bam=True, is_cram=True)
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    with pytest.raises(AlignmentProviderIncompatibleError, match="ambiguous"):
        inspect_alignment_header(_resource(path))


@pytest.mark.parametrize(
    ("header_text", "message"),
    [
        ("@SQ\tSN:chr1\n", "SQ.LN"),
        ("@SQ\tSN:chr1\tLN:100\tM5:not-an-md5\n", "@SQ record"),
        ("@PG\tPN:bwa\n", "PG.ID"),
        ("@SQ\tSN:chr1\tLN:100\tLN:100\n", "duplicate SAM header tag"),
    ],
)
def test_inspect_alignment_header_rejects_invalid_normalized_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    header_text: str,
    message: str,
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(header_text=header_text)
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    with pytest.raises((AlignmentParseError, AlignmentProviderIncompatibleError), match=message):
        inspect_alignment_header(_resource(path))


def test_inspect_alignment_header_rejects_invalid_raw_header_provider_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(header_text={"HD": {"VN": "1.6"}})
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    with pytest.raises(AlignmentProviderIncompatibleError, match="unparsed alignment header text"):
        inspect_alignment_header(_resource(path))


def test_inspect_alignment_header_closes_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reads.bam"
    path.write_bytes(b"synthetic")
    closed: list[bool] = []
    fake_module = _fake_module(closed=closed)
    monkeypatch.setattr("refcompat.inspectors.alignment.import_module", lambda _: fake_module)

    inspect_alignment_header(_resource(path))

    assert closed == [True]
