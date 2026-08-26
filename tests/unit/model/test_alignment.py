"""Unit tests for BAM/CRAM header observation values."""

from __future__ import annotations

import pytest

from refcompat.model.alignment import (
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    AlignmentProgramRecord,
)
from refcompat.model.resources import ResourceId, ResourceKind
from refcompat.model.sequence_dictionary import SequenceDictionaryRecord


def test_alignment_header_preserves_sequence_order_and_allows_no_sequences() -> None:
    empty = AlignmentHeaderData(sam_version="1.6")
    populated = AlignmentHeaderData(
        sequences=(
            SequenceDictionaryRecord(name="chr2", length=20),
            SequenceDictionaryRecord(name="chr1", length=10),
        )
    )

    assert empty.sequences == ()
    assert tuple(record.name for record in populated.sequences) == ("chr2", "chr1")


def test_alignment_header_rejects_cross_record_sn_an_collisions() -> None:
    with pytest.raises(ValueError, match="SN and AN"):
        AlignmentHeaderData(
            sequences=(
                SequenceDictionaryRecord(name="chr1", length=10, alternate_names=("1",)),
                SequenceDictionaryRecord(name="1", length=10),
            )
        )


def test_alignment_header_rejects_duplicate_program_ids() -> None:
    program = AlignmentProgramRecord(id="aligner")

    with pytest.raises(ValueError, match="@PG IDs"):
        AlignmentHeaderData(programs=(program, program))


def test_alignment_snapshot_requires_bam_or_cram_kind() -> None:
    header = AlignmentHeaderData()

    for kind in (ResourceKind.BAM, ResourceKind.CRAM):
        snapshot = AlignmentHeaderSnapshot(ResourceId("reads"), kind, header)
        assert snapshot.resource_kind is kind

    with pytest.raises(ValueError, match="BAM or CRAM"):
        AlignmentHeaderSnapshot(ResourceId("variants"), ResourceKind.VCF, header)
