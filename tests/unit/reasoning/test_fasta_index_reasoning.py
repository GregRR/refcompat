from refcompat.model.fasta_index import (
    ComputedFastaIndex,
    FastaIndexData,
    FastaIndexDifferenceKind,
    FastaIndexRecord,
    FastaIndexSnapshot,
)
from refcompat.model.resources import ResourceId
from refcompat.reasoning.fasta_index import evaluate_fasta_index_integrity


def _data(*records: FastaIndexRecord) -> FastaIndexData:
    return FastaIndexData(records)


def _expected(data: FastaIndexData) -> ComputedFastaIndex:
    return ComputedFastaIndex(ResourceId("reference.fa"), data)


def _observed(data: FastaIndexData) -> FastaIndexSnapshot:
    return FastaIndexSnapshot(ResourceId("reference.fa.fai"), data)


def test_exact_fasta_index_is_verified() -> None:
    records = _data(
        FastaIndexRecord("chr1", 8, 6, 4, 5),
        FastaIndexRecord("chr2", 4, 22, 4, 5),
    )
    result = evaluate_fasta_index_integrity(
        expected=_expected(records),
        observed=_observed(records),
    )
    assert result.verified
    assert result.differences == ()
    assert result.fasta_resource_id == ResourceId("reference.fa")
    assert result.index_resource_id == ResourceId("reference.fa.fai")


def test_fasta_index_comparison_localizes_all_structural_difference_kinds() -> None:
    expected = _data(
        FastaIndexRecord("chr1", 8, 6, 4, 5),
        FastaIndexRecord("chr2", 4, 22, 4, 5),
    )
    observed = _data(
        FastaIndexRecord("chr2", 5, 99, 5, 7),
        FastaIndexRecord("chr3", 4, 120, 4, 5),
    )

    result = evaluate_fasta_index_integrity(
        expected=_expected(expected),
        observed=_observed(observed),
    )

    kinds = {difference.kind for difference in result.differences}
    assert kinds == {
        FastaIndexDifferenceKind.MISSING_SEQUENCE,
        FastaIndexDifferenceKind.EXTRA_SEQUENCE,
        FastaIndexDifferenceKind.LENGTH,
        FastaIndexDifferenceKind.OFFSET,
        FastaIndexDifferenceKind.LINE_BASES,
        FastaIndexDifferenceKind.LINE_BYTES,
    }


def test_fasta_index_comparison_reports_count_and_missing_sequence_without_false_order() -> None:
    expected = _data(
        FastaIndexRecord("chr1", 8, 6, 4, 5),
        FastaIndexRecord("chr2", 4, 22, 4, 5),
    )
    observed = _data(FastaIndexRecord("chr2", 4, 22, 4, 5))

    result = evaluate_fasta_index_integrity(
        expected=_expected(expected),
        observed=_observed(observed),
    )

    kinds = [difference.kind for difference in result.differences]
    assert FastaIndexDifferenceKind.RECORD_COUNT in kinds
    assert FastaIndexDifferenceKind.MISSING_SEQUENCE in kinds
    assert FastaIndexDifferenceKind.ORDER not in kinds


def test_fasta_index_comparison_reports_pure_order_difference() -> None:
    expected = _data(
        FastaIndexRecord("chr1", 8, 6, 4, 5),
        FastaIndexRecord("chr2", 4, 22, 4, 5),
    )
    observed = _data(
        FastaIndexRecord("chr2", 4, 22, 4, 5),
        FastaIndexRecord("chr1", 8, 6, 4, 5),
    )

    result = evaluate_fasta_index_integrity(
        expected=_expected(expected),
        observed=_observed(observed),
    )

    kinds = [difference.kind for difference in result.differences]
    assert kinds == [FastaIndexDifferenceKind.ORDER, FastaIndexDifferenceKind.ORDER]
