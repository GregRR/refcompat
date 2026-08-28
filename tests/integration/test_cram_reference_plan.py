"""Integration coverage for approved explicit CRAM reference plans."""

from __future__ import annotations

from collections.abc import Iterator
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from refcompat.inspectors.alignment import inspect_alignment_header
from refcompat.model import (
    ArtifactIdentity,
    CollectionCompleteness,
    CramOfflineReferenceAction,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    Resource,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.reasoning import build_reference_context, plan_cram_offline_reference

_FASTA = ResourceId("reference")
_CRAM = ResourceId("reads")
_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")


class _WritableAlignedSegment(Protocol):
    query_name: str
    query_sequence: str
    flag: int
    reference_id: int
    reference_start: int
    mapping_quality: int
    cigartuples: list[tuple[int, int]]
    query_qualities: object


class _ReadableAlignedSegment(Protocol):
    query_name: str
    query_sequence: str | None
    reference_id: int
    reference_start: int


class _AlignmentFile(Protocol):
    def write(self, read: _WritableAlignedSegment) -> int: ...

    def fetch(self, *, until_eof: bool) -> Iterator[_ReadableAlignedSegment]: ...

    def close(self) -> object: ...


class _PysamAlignmentModule(Protocol):
    def AlignmentFile(self, filename: str, mode: str, **kwargs: object) -> _AlignmentFile: ...

    def AlignedSegment(self) -> _WritableAlignedSegment: ...

    def faidx(self, filename: str) -> object: ...

    def qualitystring_to_array(self, quality: str) -> object: ...


def _pysam() -> _PysamAlignmentModule:
    return cast(_PysamAlignmentModule, import_module("pysam"))


def _resource(resource_id: ResourceId, path: Path, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path))


def test_approved_explicit_anchor_decodes_mapped_cram(tmp_path: Path) -> None:
    """A planned exact-name anchor is usable even when the writer reference is gone."""

    module = _pysam()
    writer_reference = tmp_path / "writer-reference.fa"
    selected_reference = tmp_path / "selected-reference.fa"
    fasta_text = ">chr1\nACGT\n"
    writer_reference.write_text(fasta_text, encoding="ascii")
    selected_reference.write_text(fasta_text, encoding="ascii")
    module.faidx(str(writer_reference))
    module.faidx(str(selected_reference))

    cram_path = tmp_path / "reads.cram"
    header = {
        "HD": {"VN": "1.6", "SO": "coordinate"},
        "SQ": [
            {
                "SN": "chr1",
                "LN": 4,
                "M5": _MD5_ACGT.value,
                "UR": writer_reference.as_uri(),
            }
        ],
    }
    writer = module.AlignmentFile(
        str(cram_path),
        "wc",
        header=header,
        reference_filename=str(writer_reference),
    )
    try:
        read = module.AlignedSegment()
        read.query_name = "read1"
        read.query_sequence = "ACGT"
        read.flag = 0
        read.reference_id = 0
        read.reference_start = 0
        read.mapping_quality = 60
        read.cigartuples = [(0, 4)]
        read.query_qualities = module.qualitystring_to_array("IIII")
        writer.write(read)
    finally:
        writer.close()

    writer_reference.unlink()
    writer_fai = Path(f"{writer_reference}.fai")
    if writer_fai.exists():
        writer_fai.unlink()

    resources = (
        _resource(_FASTA, selected_reference, ResourceKind.FASTA),
        _resource(_CRAM, cram_path, ResourceKind.CRAM),
    )
    request = EvaluationRequest(
        resources,
        _FASTA,
        EvaluationScope((_FASTA, _CRAM)),
    )
    anchor_snapshot = SequenceCollectionSnapshot(
        resource_id=_FASTA,
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),),
    )
    context = build_reference_context(request, anchor_snapshot)
    cram_snapshot = inspect_alignment_header(resources[1])

    plan = plan_cram_offline_reference(cram_snapshot, context, request)

    assert plan.action is CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR
    assert plan.reference_path == selected_reference

    reader = module.AlignmentFile(
        str(cram_path),
        "rc",
        reference_filename=str(plan.reference_path),
    )
    try:
        records = list(reader.fetch(until_eof=True))
    finally:
        reader.close()

    assert len(records) == 1
    assert records[0].query_name == "read1"
    assert records[0].query_sequence == "ACGT"
    assert records[0].reference_id == 0
    assert records[0].reference_start == 0
