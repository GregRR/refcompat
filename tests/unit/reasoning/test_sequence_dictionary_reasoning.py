"""Unit tests for FASTA/sequence-dictionary evidence evaluation."""

from __future__ import annotations

from refcompat.model.evidence import EvidenceStrength
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import ResourceId
from refcompat.model.sequence_dictionary import (
    ExpectedSequenceDictionary,
    SequenceDictionaryData,
    SequenceDictionaryDifferenceKind,
    SequenceDictionaryRecord,
    SequenceDictionarySnapshot,
)
from refcompat.reasoning.sequence_dictionary import evaluate_sequence_dictionary_integrity

_MD5_A = Md5Digest("31fc6ca291a32fb9df82b85e5f077e31")
_MD5_B = Md5Digest("92c6a56c9e9459d8a42b96f7884710bc")


def _expected(*records: SequenceDictionaryRecord) -> ExpectedSequenceDictionary:
    return ExpectedSequenceDictionary(
        fasta_resource_id=ResourceId("reference"),
        data=SequenceDictionaryData(records=tuple(records)),
    )


def _observed(*records: SequenceDictionaryRecord) -> SequenceDictionarySnapshot:
    return SequenceDictionarySnapshot(
        resource_id=ResourceId("dictionary"),
        data=SequenceDictionaryData(records=tuple(records)),
    )


def test_exact_dictionary_verifies_structure_and_content() -> None:
    records = (
        SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A),
        SequenceDictionaryRecord(name="chr2", length=4, md5=_MD5_B),
    )
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(*records), observed=_observed(*records)
    )
    assert result.exact_companion_verified
    assert result.structurally_verified
    assert result.content_verified
    assert not result.has_conflict


def test_missing_m5_is_evidence_gap_not_conflict() -> None:
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A)),
        observed=_observed(SequenceDictionaryRecord(name="chr1", length=4)),
    )
    assert result.structurally_verified
    assert not result.content_verified
    assert not result.exact_companion_verified
    assert not result.has_conflict
    assert result.missing_m5_sequences == ("chr1",)


def test_m5_conflict_is_tier_a_content_contradiction() -> None:
    other = Md5Digest("d41d8cd98f00b204e9800998ecf8427e")
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A)),
        observed=_observed(SequenceDictionaryRecord(name="chr1", length=4, md5=other)),
    )
    difference = result.differences[0]
    assert difference.kind is SequenceDictionaryDifferenceKind.M5_CONFLICT
    assert difference.evidence_strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert result.structurally_verified
    assert not result.content_verified


def test_order_and_length_differences_are_localized() -> None:
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(
            SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A),
            SequenceDictionaryRecord(name="chr2", length=4, md5=_MD5_B),
        ),
        observed=_observed(
            SequenceDictionaryRecord(name="chr2", length=5, md5=_MD5_B),
            SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A),
        ),
    )
    kinds = [difference.kind for difference in result.differences]
    assert kinds.count(SequenceDictionaryDifferenceKind.ORDER) == 2
    assert kinds.count(SequenceDictionaryDifferenceKind.LENGTH) == 1


def test_missing_extra_sequences_do_not_create_spurious_order_findings() -> None:
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(
            SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A),
            SequenceDictionaryRecord(name="chr2", length=4, md5=_MD5_B),
        ),
        observed=_observed(
            SequenceDictionaryRecord(name="chr2", length=4, md5=_MD5_B),
            SequenceDictionaryRecord(
                name="chr3",
                length=4,
                md5=Md5Digest("d41d8cd98f00b204e9800998ecf8427e"),
            ),
        ),
    )
    kinds = [difference.kind for difference in result.differences]
    assert SequenceDictionaryDifferenceKind.MISSING_SEQUENCE in kinds
    assert SequenceDictionaryDifferenceKind.EXTRA_SEQUENCE in kinds
    assert SequenceDictionaryDifferenceKind.ORDER not in kinds


def test_declared_alias_does_not_satisfy_exact_primary_name() -> None:
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A)),
        observed=_observed(
            SequenceDictionaryRecord(name="1", length=4, md5=_MD5_A, alternate_names=("chr1",))
        ),
    )
    kinds = {difference.kind for difference in result.differences}
    assert SequenceDictionaryDifferenceKind.MISSING_SEQUENCE in kinds
    assert SequenceDictionaryDifferenceKind.EXTRA_SEQUENCE in kinds
    assert not result.exact_companion_verified
    assert [
        (match.expected_name, match.observed_name) for match in result.renamed_identity_matches
    ] == [("chr1", "1")]


def test_cross_name_m5_length_disagreement_is_retained_as_inconsistency() -> None:
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A)),
        observed=_observed(SequenceDictionaryRecord(name="chrOne", length=999, md5=_MD5_A)),
    )

    kinds = {difference.kind for difference in result.differences}
    assert SequenceDictionaryDifferenceKind.MISSING_SEQUENCE in kinds
    assert SequenceDictionaryDifferenceKind.EXTRA_SEQUENCE in kinds
    assert result.renamed_identity_matches == ()
    assert len(result.cross_name_m5_length_inconsistencies) == 1
    inconsistency = result.cross_name_m5_length_inconsistencies[0]
    assert inconsistency.expected_name == "chr1"
    assert inconsistency.observed_name == "chrOne"
    assert inconsistency.md5 == _MD5_A
    assert inconsistency.expected_length == 4
    assert inconsistency.observed_length == 999
    assert result.has_conflict
    assert not result.exact_companion_verified


def test_ambiguous_repeated_m5_is_not_promoted_to_cross_name_identity() -> None:
    result = evaluate_sequence_dictionary_integrity(
        expected=_expected(
            SequenceDictionaryRecord(name="a", length=4, md5=_MD5_A),
            SequenceDictionaryRecord(name="b", length=4, md5=_MD5_A),
        ),
        observed=_observed(
            SequenceDictionaryRecord(name="x", length=4, md5=_MD5_A),
            SequenceDictionaryRecord(name="y", length=4, md5=_MD5_A),
        ),
    )
    assert result.renamed_identity_matches == ()
