"""Tests for VCF REF conflict-pattern value invariants."""

import pytest

from refcompat.model.resources import ResourceId
from refcompat.model.vcf_ref_pattern import (
    VcfRefConflictPattern,
    VcfRefConflictPatternSummary,
)

_VCF = ResourceId("variants")
_FASTA = ResourceId("anchor")


def _summary(
    pattern: VcfRefConflictPattern,
    *,
    record_count: int = 2,
    directly_compared_count: int = 2,
    mismatch_count: int = 2,
    unresolved_count: int = 0,
    compared: tuple[str, ...] = ("chr1",),
    affected: tuple[str, ...] = ("chr1",),
) -> VcfRefConflictPatternSummary:
    return VcfRefConflictPatternSummary(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        pattern=pattern,
        record_count=record_count,
        directly_compared_count=directly_compared_count,
        mismatch_count=mismatch_count,
        unresolved_count=unresolved_count,
        compared_sequence_names=compared,
        affected_sequence_names=affected,
    )


def test_pattern_summary_requires_complete_record_partition() -> None:
    with pytest.raises(ValueError, match="cover every record"):
        _summary(
            VcfRefConflictPattern.LOCALIZED,
            record_count=3,
            directly_compared_count=2,
        )


def test_pattern_summary_requires_sorted_unique_sequence_names() -> None:
    with pytest.raises(ValueError, match="unique and sorted"):
        _summary(
            VcfRefConflictPattern.SYSTEMATIC,
            compared=("chr2", "chr1"),
            affected=("chr1", "chr2"),
        )


def test_unclassified_pattern_requires_incomplete_direct_comparison() -> None:
    with pytest.raises(ValueError, match="requires incomplete comparison"):
        _summary(VcfRefConflictPattern.UNCLASSIFIED)


def test_systematic_pattern_requires_scope_wide_multi_sequence_conflicts() -> None:
    with pytest.raises(ValueError, match="multi-sequence scope"):
        _summary(VcfRefConflictPattern.SYSTEMATIC)


def test_systematic_pattern_requires_every_compared_record_to_mismatch() -> None:
    with pytest.raises(ValueError, match="every compared record"):
        _summary(
            VcfRefConflictPattern.SYSTEMATIC,
            record_count=4,
            directly_compared_count=4,
            mismatch_count=2,
            compared=("chr1", "chr2"),
            affected=("chr1", "chr2"),
        )


def test_distributed_pattern_requires_some_direct_match() -> None:
    with pytest.raises(ValueError, match="must be SYSTEMATIC"):
        _summary(
            VcfRefConflictPattern.DISTRIBUTED,
            compared=("chr1", "chr2"),
            affected=("chr1", "chr2"),
        )


def test_localized_pattern_rejects_scope_wide_multi_sequence_shape() -> None:
    with pytest.raises(ValueError, match="DISTRIBUTED or SYSTEMATIC"):
        _summary(
            VcfRefConflictPattern.LOCALIZED,
            compared=("chr1", "chr2"),
            affected=("chr1", "chr2"),
        )
