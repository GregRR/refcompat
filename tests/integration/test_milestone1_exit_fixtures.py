"""Milestone 1 exit fixtures for identity and derived-artifact evidence."""

from __future__ import annotations

from pathlib import Path

from refcompat.identity import Ga4ghRefgetIdentityProvider
from refcompat.inspectors.fasta_index import compute_expected_fasta_index, read_fasta_index
from refcompat.inspectors.sequence_dictionary import (
    expected_sequence_dictionary_from_snapshot,
    read_sequence_dictionary,
)
from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.fasta_index import FastaIndexDifferenceKind
from refcompat.model.identity import Md5Digest, SequenceCollectionSnapshot
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.sequence_dictionary import SequenceDictionaryDifferenceKind
from refcompat.reasoning.fasta_index import evaluate_fasta_index_integrity
from refcompat.reasoning.sequence_dictionary import evaluate_sequence_dictionary_integrity

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "milestone1"


def _resource(name: str, kind: ResourceKind) -> Resource:
    return Resource(
        id=ResourceId(name),
        kind=kind,
        artifact=ArtifactIdentity(_FIXTURES / name),
    )


def _snapshot(name: str) -> SequenceCollectionSnapshot:
    return Ga4ghRefgetIdentityProvider().inspect_fasta(_resource(name, ResourceKind.FASTA))


def test_identity_fixture_is_deterministic_and_resource_traceable() -> None:
    first = _snapshot("content_v1.fa")
    second = _snapshot("content_v1.fa")

    assert first == second
    assert first.resource_id == ResourceId("content_v1.fa")
    observed_sequences = [
        (sequence.local_name, sequence.length, sequence.md5) for sequence in first.sequences
    ]
    assert observed_sequences == [
        ("chr1", 4, Md5Digest("f1f8f4bf413b16ad135722aa4591043e")),
        ("chr2", 4, Md5Digest("ecccb7340fe2a704f233bbf07df6c0f3")),
    ]


def test_same_names_and_lengths_do_not_establish_same_sequence_content() -> None:
    version_one = _snapshot("content_v1.fa")
    version_two = _snapshot("content_v2.fa")

    assert [sequence.local_name for sequence in version_one.sequences] == [
        sequence.local_name for sequence in version_two.sequences
    ]
    assert [sequence.length for sequence in version_one.sequences] == [
        sequence.length for sequence in version_two.sequences
    ]
    assert version_one.sequences[0].md5 != version_two.sequences[0].md5
    assert version_one.sequences[0].refget_id != version_two.sequences[0].refget_id
    assert version_one.collection_digest != version_two.collection_digest


def test_fai_is_blind_to_same_length_content_only_change() -> None:
    """Guard the structural-only boundary of FASTA index evidence."""
    changed_fasta = _resource("content_v2.fa", ResourceKind.FASTA)
    original_index = _resource("content_v1.fa.fai", ResourceKind.FASTA_INDEX)

    result = evaluate_fasta_index_integrity(
        expected=compute_expected_fasta_index(changed_fasta),
        observed=read_fasta_index(original_index),
    )

    assert result.verified
    assert result.differences == ()


def test_stale_by_construction_fai_reports_only_localized_structural_evidence() -> None:
    original_fasta = _resource("content_v1.fa", ResourceKind.FASTA)
    changed_fasta = _resource("length_changed_v2.fa", ResourceKind.FASTA)
    original_index = _resource("content_v1.fa.fai", ResourceKind.FASTA_INDEX)
    observed = read_fasta_index(original_index)

    original_result = evaluate_fasta_index_integrity(
        expected=compute_expected_fasta_index(original_fasta),
        observed=observed,
    )
    assert original_result.verified

    changed_result = evaluate_fasta_index_integrity(
        expected=compute_expected_fasta_index(changed_fasta),
        observed=observed,
    )

    assert changed_result.fasta_resource_id == ResourceId("length_changed_v2.fa")
    assert changed_result.index_resource_id == ResourceId("content_v1.fa.fai")
    assert changed_result.evidence_strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert changed_result.evidence_polarity is EvidencePolarity.CONTRADICTS
    assert {
        (
            difference.kind,
            difference.sequence_name,
            difference.expected_value,
            difference.observed_value,
        )
        for difference in changed_result.differences
    } == {
        (FastaIndexDifferenceKind.LENGTH, "chr1", 5, 4),
        (FastaIndexDifferenceKind.LINE_BASES, "chr1", 5, 4),
        (FastaIndexDifferenceKind.LINE_BYTES, "chr1", 6, 5),
        (FastaIndexDifferenceKind.OFFSET, "chr2", 18, 17),
    }


def test_stale_by_construction_dictionary_reports_m5_conflict_not_cause() -> None:
    original_snapshot = _snapshot("content_v1.fa")
    changed_snapshot = _snapshot("content_v2.fa")
    dictionary = read_sequence_dictionary(
        _resource("content_v1.dict", ResourceKind.SEQUENCE_DICTIONARY)
    )

    original_result = evaluate_sequence_dictionary_integrity(
        expected=expected_sequence_dictionary_from_snapshot(original_snapshot),
        observed=dictionary,
    )
    assert original_result.exact_companion_verified

    changed_result = evaluate_sequence_dictionary_integrity(
        expected=expected_sequence_dictionary_from_snapshot(changed_snapshot),
        observed=dictionary,
    )

    assert changed_result.fasta_resource_id == ResourceId("content_v2.fa")
    assert changed_result.dictionary_resource_id == ResourceId("content_v1.dict")
    assert changed_result.structurally_verified
    assert not changed_result.content_verified
    observed_differences = [
        (
            difference.kind,
            difference.sequence_name,
            difference.expected_value,
            difference.observed_value,
        )
        for difference in changed_result.differences
    ]
    assert observed_differences == [
        (
            SequenceDictionaryDifferenceKind.M5_CONFLICT,
            "chr1",
            "ca773511c152b8191d2757f5a45ffafd",
            "f1f8f4bf413b16ad135722aa4591043e",
        )
    ]
    assert (
        changed_result.differences[0].evidence_strength
        is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    )
    assert changed_result.differences[0].evidence_polarity is EvidencePolarity.CONTRADICTS


def test_alias_only_dictionary_preserves_identity_evidence_without_exact_match() -> None:
    snapshot = _snapshot("content_v1.fa")
    observed = read_sequence_dictionary(
        _resource("alias_only.dict", ResourceKind.SEQUENCE_DICTIONARY)
    )
    result = evaluate_sequence_dictionary_integrity(
        expected=expected_sequence_dictionary_from_snapshot(snapshot),
        observed=observed,
    )

    assert not result.exact_companion_verified
    observed_matches = [
        (match.expected_name, match.observed_name) for match in result.renamed_identity_matches
    ]
    assert observed_matches == [("chr1", "1"), ("chr2", "2")]
    assert [match.md5 for match in result.renamed_identity_matches] == [
        Md5Digest("f1f8f4bf413b16ad135722aa4591043e"),
        Md5Digest("ecccb7340fe2a704f233bbf07df6c0f3"),
    ]
    assert all(
        match.evidence_strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
        and match.evidence_polarity is EvidencePolarity.SUPPORTS
        for match in result.renamed_identity_matches
    )
    assert {difference.kind for difference in result.differences} == {
        SequenceDictionaryDifferenceKind.MISSING_SEQUENCE,
        SequenceDictionaryDifferenceKind.EXTRA_SEQUENCE,
    }


def test_order_difference_is_structural_even_when_m5_values_match() -> None:
    snapshot = _snapshot("content_v1.fa")
    observed = read_sequence_dictionary(
        _resource("order_difference.dict", ResourceKind.SEQUENCE_DICTIONARY)
    )
    result = evaluate_sequence_dictionary_integrity(
        expected=expected_sequence_dictionary_from_snapshot(snapshot),
        observed=observed,
    )

    assert not result.structurally_verified
    assert [
        (
            difference.kind,
            difference.sequence_name,
            difference.expected_ordinal,
            difference.observed_ordinal,
        )
        for difference in result.differences
    ] == [
        (SequenceDictionaryDifferenceKind.ORDER, "chr1", 0, 1),
        (SequenceDictionaryDifferenceKind.ORDER, "chr2", 1, 0),
    ]
    assert all(
        difference.evidence_strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
        and difference.evidence_polarity is EvidencePolarity.CONTRADICTS
        for difference in result.differences
    )
