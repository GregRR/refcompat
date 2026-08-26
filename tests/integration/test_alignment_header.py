"""Integration tests for real pysam BAM/CRAM header observation extraction."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from refcompat.inspectors.alignment import inspect_alignment_header
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


class _AlignmentWriter(Protocol):
    def close(self) -> object: ...


class _PysamAlignmentModule(Protocol):
    def AlignmentFile(self, filename: str, mode: str, **kwargs: object) -> _AlignmentWriter: ...

    def faidx(self, filename: str) -> object: ...


def _pysam() -> _PysamAlignmentModule:
    return cast(_PysamAlignmentModule, import_module("pysam"))


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def _header(reference_uri: str) -> dict[str, object]:
    return {
        "HD": {"VN": "1.6", "SO": "coordinate"},
        "SQ": [
            {
                "SN": "chr1",
                "LN": 4,
                "M5": "f1f8f4bf413b16ad135722aa4591043e",
                "AN": "1",
                "AS": "synthetic",
                "UR": reference_uri,
                "SP": "synthetic species",
                "TP": "linear",
            }
        ],
        "PG": [{"ID": "fixture", "PN": "fixture-writer", "VN": "1"}],
    }


def _assert_snapshot(path: Path, kind: ResourceKind) -> None:
    snapshot = inspect_alignment_header(_resource(path, kind))

    assert snapshot.resource_kind is kind
    assert snapshot.header.sam_version == "1.6"
    assert snapshot.header.sort_order == "coordinate"
    assert snapshot.declared_sequence_names == ("chr1",)
    sequence = snapshot.header.sequences[0]
    assert sequence.length == 4
    assert sequence.md5 == Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
    assert sequence.alternate_names == ("1",)
    assert sequence.assembly == "synthetic"
    assert sequence.species == "synthetic species"
    assert snapshot.header.programs[0].id == "fixture"


def test_real_pysam_reads_bam_header(tmp_path: Path) -> None:
    path = tmp_path / "reads.bam"
    module = _pysam()
    writer = module.AlignmentFile(
        str(path),
        "wb",
        header=_header("file:///refs/synthetic.fa"),
    )
    writer.close()

    _assert_snapshot(path, ResourceKind.BAM)


def test_real_pysam_reads_cram_header_without_reference_content_available(tmp_path: Path) -> None:
    reference = tmp_path / "reference.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    module = _pysam()
    module.faidx(str(reference))

    path = tmp_path / "reads.cram"
    writer = module.AlignmentFile(
        str(path),
        "wc",
        header=_header(reference.as_uri()),
        reference_filename=str(reference),
    )
    writer.close()

    reference.unlink()
    fai = Path(f"{reference}.fai")
    if fai.exists():
        fai.unlink()

    _assert_snapshot(path, ResourceKind.CRAM)


def test_real_pysam_reads_extension_tags_without_validating_them_as_standard_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "extension-tags.bam"
    module = _pysam()
    text = (
        "\n".join(
            (
                "@HD\tVN:1.6\tzz:header-extension",
                "@SQ\tSN:chr1\tLN:4\tzz:sequence-extension",
                "@PG\tID:fixture\tCL:align --flag value\tVN:2\tDS:description"
                "\tzz:program-extension",
            )
        )
        + "\n"
    )
    writer = module.AlignmentFile(str(path), "wb", text=text)
    writer.close()

    snapshot = inspect_alignment_header(_resource(path, ResourceKind.BAM))

    assert snapshot.declared_sequence_names == ("chr1",)
    assert snapshot.header.sequences[0].length == 4
    program = snapshot.header.programs[0]
    assert program.command_line == "align --flag value"
    assert program.version == "2"
    assert program.description == "description"
