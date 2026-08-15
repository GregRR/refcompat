"""Exact FASTA/sequence-dictionary comparison with separate M5 evidence.

The evaluator reports observable structure and sequence-content evidence. It
does not infer that a mismatching dictionary is stale, does not treat declared
aliases as exact primary-name correspondence, and does not allow metadata such
as ``AS`` or ``UR`` to override content contradictions.
"""

from __future__ import annotations

from collections import Counter

from refcompat.model.sequence_dictionary import (
    ExpectedSequenceDictionary,
    SequenceDictionaryContentIdentityMatch,
    SequenceDictionaryCrossNameM5LengthInconsistency,
    SequenceDictionaryDifference,
    SequenceDictionaryDifferenceKind,
    SequenceDictionaryIntegrityResult,
    SequenceDictionaryRecord,
    SequenceDictionarySnapshot,
)


def evaluate_sequence_dictionary_integrity(
    *,
    expected: ExpectedSequenceDictionary,
    observed: SequenceDictionarySnapshot,
) -> SequenceDictionaryIntegrityResult:
    """Compare one supplied ``.dict`` with records expected from its FASTA anchor."""

    differences: list[SequenceDictionaryDifference] = []
    missing_m5_sequences: list[str] = []

    if len(expected.records) != len(observed.records):
        differences.append(
            SequenceDictionaryDifference(
                kind=SequenceDictionaryDifferenceKind.RECORD_COUNT,
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
                SequenceDictionaryDifference(
                    kind=SequenceDictionaryDifferenceKind.MISSING_SEQUENCE,
                    sequence_name=record.name,
                    expected_ordinal=expected_ordinal,
                )
            )

    for observed_ordinal, record in enumerate(observed.records):
        if record.name not in expected_names:
            differences.append(
                SequenceDictionaryDifference(
                    kind=SequenceDictionaryDifferenceKind.EXTRA_SEQUENCE,
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
                SequenceDictionaryDifference(
                    kind=SequenceDictionaryDifferenceKind.ORDER,
                    sequence_name=expected_record.name,
                    expected_ordinal=expected_ordinal,
                    observed_ordinal=observed_ordinal,
                )
            )

        if expected_record.length != observed_record.length:
            differences.append(
                SequenceDictionaryDifference(
                    kind=SequenceDictionaryDifferenceKind.LENGTH,
                    sequence_name=expected_record.name,
                    expected_value=expected_record.length,
                    observed_value=observed_record.length,
                )
            )

        if observed_record.md5 is None:
            missing_m5_sequences.append(expected_record.name)
        elif expected_record.md5 != observed_record.md5:
            differences.append(
                SequenceDictionaryDifference(
                    kind=SequenceDictionaryDifferenceKind.M5_CONFLICT,
                    sequence_name=expected_record.name,
                    expected_value=expected_record.md5.value if expected_record.md5 else None,
                    observed_value=observed_record.md5.value,
                )
            )

    renamed_identity_matches, cross_name_m5_length_inconsistencies = _cross_name_m5_relationships(
        expected.records,
        observed.records,
        missing_expected_names=expected_names - observed_names,
        extra_observed_names=observed_names - expected_names,
    )

    return SequenceDictionaryIntegrityResult(
        fasta_resource_id=expected.fasta_resource_id,
        dictionary_resource_id=observed.resource_id,
        differences=tuple(differences),
        missing_m5_sequences=tuple(missing_m5_sequences),
        renamed_identity_matches=renamed_identity_matches,
        cross_name_m5_length_inconsistencies=cross_name_m5_length_inconsistencies,
    )


def _cross_name_m5_relationships(
    expected_records: tuple[SequenceDictionaryRecord, ...],
    observed_records: tuple[SequenceDictionaryRecord, ...],
    *,
    missing_expected_names: set[str],
    extra_observed_names: set[str],
) -> tuple[
    tuple[SequenceDictionaryContentIdentityMatch, ...],
    tuple[SequenceDictionaryCrossNameM5LengthInconsistency, ...],
]:
    """Return unambiguous cross-name M5 relationships without losing conflicts.

    Repeated sequence content is common enough that an M5 digest can occur under
    more than one name. RefCompat therefore considers a cross-name relationship
    only when the digest occurs exactly once on both the missing-expected and
    extra-observed sides. Equal lengths produce a content-identity match;
    differing lengths are retained separately as an M5/LN inconsistency rather
    than being silently discarded or promoted to clean identity support.
    """

    expected_candidates = [
        (record.md5, record)
        for record in expected_records
        if record.name in missing_expected_names and record.md5 is not None
    ]
    observed_candidates = [
        (record.md5, record)
        for record in observed_records
        if record.name in extra_observed_names and record.md5 is not None
    ]

    expected_counts = Counter(md5 for md5, _record in expected_candidates)
    observed_counts = Counter(md5 for md5, _record in observed_candidates)
    observed_by_md5 = {
        md5: record for md5, record in observed_candidates if observed_counts[md5] == 1
    }

    matches: list[SequenceDictionaryContentIdentityMatch] = []
    length_inconsistencies: list[SequenceDictionaryCrossNameM5LengthInconsistency] = []
    for md5, expected_record in expected_candidates:
        if expected_counts[md5] != 1 or observed_counts[md5] != 1:
            continue
        observed_record = observed_by_md5[md5]
        if expected_record.length != observed_record.length:
            length_inconsistencies.append(
                SequenceDictionaryCrossNameM5LengthInconsistency(
                    expected_name=expected_record.name,
                    observed_name=observed_record.name,
                    md5=md5,
                    expected_length=expected_record.length,
                    observed_length=observed_record.length,
                )
            )
            continue
        matches.append(
            SequenceDictionaryContentIdentityMatch(
                expected_name=expected_record.name,
                observed_name=observed_record.name,
                md5=md5,
            )
        )
    return tuple(matches), tuple(length_inconsistencies)
