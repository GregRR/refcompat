"""Exact structural comparison of a FASTA and its supplied ``.fai``.

This module evaluates the derived-artifact relationship without guessing why a
mismatch occurred. In particular, a structural mismatch is not labeled
``stale`` unless later provenance evidence establishes that interpretation.
"""

from __future__ import annotations

from refcompat.model.fasta_index import (
    ComputedFastaIndex,
    FastaIndexDifference,
    FastaIndexDifferenceKind,
    FastaIndexIntegrityResult,
    FastaIndexSnapshot,
)


def evaluate_fasta_index_integrity(
    *,
    expected: ComputedFastaIndex,
    observed: FastaIndexSnapshot,
) -> FastaIndexIntegrityResult:
    """Compare supplied FAI data with geometry computed from its FASTA anchor."""

    differences: list[FastaIndexDifference] = []

    if len(expected.records) != len(observed.records):
        differences.append(
            FastaIndexDifference(
                kind=FastaIndexDifferenceKind.RECORD_COUNT,
                expected_value=len(expected.records),
                observed_value=len(observed.records),
            )
        )

    expected_by_name = {
        record.name: (ordinal, record) for ordinal, record in enumerate(expected.records)
    }
    observed_by_name = {
        record.name: (ordinal, record) for ordinal, record in enumerate(observed.records)
    }

    expected_names = set(expected_by_name)
    observed_names = set(observed_by_name)

    for expected_ordinal, record in enumerate(expected.records):
        if record.name not in observed_names:
            differences.append(
                FastaIndexDifference(
                    kind=FastaIndexDifferenceKind.MISSING_SEQUENCE,
                    sequence_name=record.name,
                    expected_ordinal=expected_ordinal,
                )
            )

    for observed_ordinal, record in enumerate(observed.records):
        if record.name not in expected_names:
            differences.append(
                FastaIndexDifference(
                    kind=FastaIndexDifferenceKind.EXTRA_SEQUENCE,
                    sequence_name=record.name,
                    observed_ordinal=observed_ordinal,
                )
            )

    names_are_identical = expected_names == observed_names

    for expected_ordinal, expected_record in enumerate(expected.records):
        observed_entry = observed_by_name.get(expected_record.name)
        if observed_entry is None:
            continue
        observed_ordinal, observed_record = observed_entry

        if names_are_identical and expected_ordinal != observed_ordinal:
            differences.append(
                FastaIndexDifference(
                    kind=FastaIndexDifferenceKind.ORDER,
                    sequence_name=expected_record.name,
                    expected_ordinal=expected_ordinal,
                    observed_ordinal=observed_ordinal,
                )
            )

        _compare_integer_field(
            differences,
            FastaIndexDifferenceKind.LENGTH,
            expected_record.name,
            expected_record.length,
            observed_record.length,
        )
        _compare_integer_field(
            differences,
            FastaIndexDifferenceKind.OFFSET,
            expected_record.name,
            expected_record.offset,
            observed_record.offset,
        )
        _compare_integer_field(
            differences,
            FastaIndexDifferenceKind.LINE_BASES,
            expected_record.name,
            expected_record.line_bases,
            observed_record.line_bases,
        )
        _compare_integer_field(
            differences,
            FastaIndexDifferenceKind.LINE_BYTES,
            expected_record.name,
            expected_record.line_bytes,
            observed_record.line_bytes,
        )

    return FastaIndexIntegrityResult(
        fasta_resource_id=expected.fasta_resource_id,
        index_resource_id=observed.resource_id,
        differences=tuple(differences),
    )


def _compare_integer_field(
    differences: list[FastaIndexDifference],
    kind: FastaIndexDifferenceKind,
    sequence_name: str,
    expected: int,
    observed: int,
) -> None:
    if expected == observed:
        return
    differences.append(
        FastaIndexDifference(
            kind=kind,
            sequence_name=sequence_name,
            expected_value=expected,
            observed_value=observed,
        )
    )
