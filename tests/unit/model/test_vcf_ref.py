"""Unit tests for direct VCF REF-to-FASTA result models."""

from __future__ import annotations

import pytest

from refcompat.model.resources import ResourceId
from refcompat.model.vcf_ref import (
    VcfRefCheckState,
    VcfRefRecord,
    VcfRefRecordCheck,
    VcfRefSequenceSummary,
    VcfRefValidationResult,
)


def _record(ordinal: int = 0) -> VcfRefRecord:
    return VcfRefRecord(ResourceId("vcf"), ordinal, "chr1", 1, "A")


def test_vcf_ref_record_preserves_telomere_zero_and_rejects_invalid_ref() -> None:
    assert VcfRefRecord(ResourceId("vcf"), 0, "chr1", 0, "acgtn").position == 0

    with pytest.raises(ValueError, match="only A, C, G, T, or N"):
        VcfRefRecord(ResourceId("vcf"), 0, "chr1", 1, "R")


def test_mismatch_requires_same_length_fasta_bases() -> None:
    with pytest.raises(ValueError, match="must retain fetched FASTA bases"):
        VcfRefRecordCheck(
            _record(),
            VcfRefCheckState.MISMATCH,
            anchor_sequence_name="chr1",
        )
    with pytest.raises(ValueError, match="span must match REF length"):
        VcfRefRecordCheck(
            _record(),
            VcfRefCheckState.MISMATCH,
            anchor_sequence_name="chr1",
            fasta_bases="AA",
        )


def test_unresolved_check_cannot_claim_anchor_trace() -> None:
    with pytest.raises(ValueError, match="cannot cite anchor bases"):
        VcfRefRecordCheck(
            _record(),
            VcfRefCheckState.UNRESOLVED_SEQUENCE,
            anchor_sequence_name="chr1",
        )


def test_sequence_summary_counts_must_partition_records() -> None:
    with pytest.raises(ValueError, match="must sum to record count"):
        VcfRefSequenceSummary("chr1", record_count=2, match_count=1)


def test_validation_result_requires_exact_problem_record_coverage() -> None:
    summary = VcfRefSequenceSummary("chr1", record_count=1, mismatch_count=1)
    with pytest.raises(ValueError, match="cover every non-match outcome"):
        VcfRefValidationResult(
            ResourceId("vcf"),
            ResourceId("fasta"),
            record_count=1,
            match_count=0,
            mismatch_count=1,
            out_of_bounds_count=0,
            unresolved_sequence_count=0,
            sequence_summaries=(summary,),
        )


def test_validation_result_rejects_match_inside_problem_records() -> None:
    check = VcfRefRecordCheck(
        _record(),
        VcfRefCheckState.MATCH,
        anchor_sequence_name="chr1",
    )
    with pytest.raises(ValueError, match="cannot contain MATCH"):
        VcfRefValidationResult(
            ResourceId("vcf"),
            ResourceId("fasta"),
            record_count=1,
            match_count=0,
            mismatch_count=1,
            out_of_bounds_count=0,
            unresolved_sequence_count=0,
            sequence_summaries=(VcfRefSequenceSummary("chr1", record_count=1, mismatch_count=1),),
            problem_records=(check,),
        )


def test_validation_result_rejects_crosswired_problem_record_resource() -> None:
    summary = VcfRefSequenceSummary("chr1", record_count=1, mismatch_count=1)
    check = VcfRefRecordCheck(
        VcfRefRecord(ResourceId("other"), 0, "chr1", 1, "A"),
        VcfRefCheckState.MISMATCH,
        anchor_sequence_name="chr1",
        fasta_bases="C",
    )
    with pytest.raises(ValueError, match="different VCF resource"):
        VcfRefValidationResult(
            ResourceId("vcf"),
            ResourceId("fasta"),
            record_count=1,
            match_count=0,
            mismatch_count=1,
            out_of_bounds_count=0,
            unresolved_sequence_count=0,
            sequence_summaries=(summary,),
            problem_records=(check,),
        )
