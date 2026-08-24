"""Tests for threshold-free VCF REF conflict-pattern interpretation."""

from refcompat.model.resources import ResourceId
from refcompat.model.vcf_ref import (
    VcfRefCheckState,
    VcfRefRecord,
    VcfRefRecordCheck,
    VcfRefSequenceSummary,
    VcfRefValidationResult,
)
from refcompat.model.vcf_ref_pattern import VcfRefConflictPattern
from refcompat.reasoning.vcf_ref_pattern import classify_vcf_ref_conflicts

_VCF = ResourceId("variants")
_FASTA = ResourceId("anchor")


def _mismatch(ordinal: int, sequence_name: str) -> VcfRefRecordCheck:
    return VcfRefRecordCheck(
        VcfRefRecord(_VCF, ordinal, sequence_name, ordinal + 1, "T"),
        VcfRefCheckState.MISMATCH,
        anchor_sequence_name=sequence_name,
        fasta_bases="A",
    )


def _unresolved(ordinal: int, sequence_name: str) -> VcfRefRecordCheck:
    return VcfRefRecordCheck(
        VcfRefRecord(_VCF, ordinal, sequence_name, ordinal + 1, "A"),
        VcfRefCheckState.UNRESOLVED_SEQUENCE,
    )


def _out_of_bounds(ordinal: int, sequence_name: str) -> VcfRefRecordCheck:
    return VcfRefRecordCheck(
        VcfRefRecord(_VCF, ordinal, sequence_name, ordinal + 1, "A"),
        VcfRefCheckState.OUT_OF_BOUNDS,
        anchor_sequence_name=sequence_name,
    )


def _validation(
    *summaries: VcfRefSequenceSummary,
    problems: tuple[VcfRefRecordCheck, ...] = (),
) -> VcfRefValidationResult:
    return VcfRefValidationResult(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        record_count=sum(summary.record_count for summary in summaries),
        match_count=sum(summary.match_count for summary in summaries),
        mismatch_count=sum(summary.mismatch_count for summary in summaries),
        out_of_bounds_count=sum(summary.out_of_bounds_count for summary in summaries),
        unresolved_sequence_count=sum(summary.unresolved_sequence_count for summary in summaries),
        sequence_summaries=summaries,
        problem_records=problems,
    )


def test_complete_validation_without_mismatch_has_no_conflict_pattern() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(VcfRefSequenceSummary("chr1", 5, match_count=5))
    )
    assert result.pattern is VcfRefConflictPattern.NONE
    assert result.mismatch_count == 0
    assert result.compared_sequence_names == ("chr1",)
    assert result.affected_sequence_names == ()


def test_one_mismatch_among_one_million_records_is_isolated() -> None:
    mismatch = _mismatch(999_999, "chr1")
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 1_000_000, match_count=999_999, mismatch_count=1),
            problems=(mismatch,),
        )
    )
    assert result.pattern is VcfRefConflictPattern.ISOLATED
    assert result.mismatch_count == 1
    assert result.directly_compared_count == 1_000_000


def test_multiple_conflicts_on_one_sequence_are_localized() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 4, match_count=2, mismatch_count=2),
            VcfRefSequenceSummary("chr2", 3, match_count=3),
            problems=(_mismatch(0, "chr1"), _mismatch(1, "chr1")),
        )
    )
    assert result.pattern is VcfRefConflictPattern.LOCALIZED
    assert result.affected_sequence_names == ("chr1",)
    assert result.compared_sequence_names == ("chr1", "chr2")


def test_conflicts_on_strict_subset_of_sequences_are_localized() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 2, match_count=1, mismatch_count=1),
            VcfRefSequenceSummary("chr2", 2, match_count=1, mismatch_count=1),
            VcfRefSequenceSummary("chr3", 2, match_count=2),
            problems=(_mismatch(0, "chr1"), _mismatch(1, "chr2")),
        )
    )
    assert result.pattern is VcfRefConflictPattern.LOCALIZED
    assert result.affected_sequence_names == ("chr1", "chr2")


def test_sparse_conflicts_across_every_sequence_are_distributed_not_systematic() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 100, match_count=99, mismatch_count=1),
            VcfRefSequenceSummary("chr2", 100, match_count=99, mismatch_count=1),
            problems=(_mismatch(0, "chr1"), _mismatch(1, "chr2")),
        )
    )
    assert result.pattern is VcfRefConflictPattern.DISTRIBUTED
    assert result.mismatch_count == 2
    assert result.affected_sequence_names == ("chr1", "chr2")


def test_every_compared_record_mismatching_across_sequences_is_systematic() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 2, mismatch_count=2),
            VcfRefSequenceSummary("chr2", 2, mismatch_count=2),
            problems=(
                _mismatch(0, "chr1"),
                _mismatch(1, "chr1"),
                _mismatch(2, "chr2"),
                _mismatch(3, "chr2"),
            ),
        )
    )
    assert result.pattern is VcfRefConflictPattern.SYSTEMATIC
    assert result.mismatch_count == result.directly_compared_count == 4


def test_single_sequence_scope_with_multiple_conflicts_is_localized() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 3, match_count=1, mismatch_count=2),
            problems=(_mismatch(0, "chr1"), _mismatch(1, "chr1")),
        )
    )
    assert result.pattern is VcfRefConflictPattern.LOCALIZED


def test_unresolved_sequence_prevents_pattern_claim_even_with_proven_mismatch() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 1, mismatch_count=1),
            VcfRefSequenceSummary("missing", 1, unresolved_sequence_count=1),
            problems=(_mismatch(0, "chr1"), _unresolved(1, "missing")),
        )
    )
    assert result.pattern is VcfRefConflictPattern.UNCLASSIFIED
    assert result.mismatch_count == 1
    assert result.unresolved_count == 1
    assert result.affected_sequence_names == ("chr1",)


def test_out_of_bounds_record_prevents_pattern_claim() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr1", 2, match_count=1, out_of_bounds_count=1),
            problems=(_out_of_bounds(1, "chr1"),),
        )
    )
    assert result.pattern is VcfRefConflictPattern.UNCLASSIFIED
    assert result.mismatch_count == 0
    assert result.unresolved_count == 1


def test_pattern_sequence_lists_are_deterministic_not_summary_order_dependent() -> None:
    result = classify_vcf_ref_conflicts(
        _validation(
            VcfRefSequenceSummary("chr2", 1, mismatch_count=1),
            VcfRefSequenceSummary("chr1", 1, mismatch_count=1),
            problems=(_mismatch(0, "chr2"), _mismatch(1, "chr1")),
        )
    )
    assert result.pattern is VcfRefConflictPattern.SYSTEMATIC
    assert result.compared_sequence_names == ("chr1", "chr2")
    assert result.affected_sequence_names == ("chr1", "chr2")
