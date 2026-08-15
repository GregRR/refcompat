"""Unit tests for provisional Milestone 1 diagnostic rendering."""

from __future__ import annotations

import json

from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.fasta_index import (
    FastaIndexDifference,
    FastaIndexDifferenceKind,
    FastaIndexIntegrityResult,
)
from refcompat.model.identity import (
    CollectionCompleteness,
    IdentityProviderInfo,
    Md5Digest,
    RefgetSequenceId,
    SeqColAttributeDigest,
    SeqColDigest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.resources import ResourceId
from refcompat.model.sequence_dictionary import (
    SequenceDictionaryContentIdentityMatch,
    SequenceDictionaryCrossNameM5LengthInconsistency,
    SequenceDictionaryDifference,
    SequenceDictionaryDifferenceKind,
    SequenceDictionaryIntegrityResult,
)
from refcompat.reporting import (
    fasta_index_integrity_payload,
    render_fasta_index_integrity,
    render_json,
    render_sequence_collection_snapshot,
    render_sequence_dictionary_integrity,
    sequence_collection_snapshot_payload,
    sequence_dictionary_integrity_payload,
)

_MD5_A = Md5Digest("31fc6ca291a32fb9df82b85e5f077e31")
_MD5_B = Md5Digest("92c6a56c9e9459d8a42b96f7884710bc")


def test_sequence_snapshot_payload_preserves_identity_and_provider_facts() -> None:
    snapshot = SequenceCollectionSnapshot(
        resource_id=ResourceId("reference.fa"),
        completeness=CollectionCompleteness.COMPLETE,
        collection_digest=SeqColDigest("a" * 32),
        names_digest=SeqColAttributeDigest("b" * 32),
        lengths_digest=SeqColAttributeDigest("c" * 32),
        sequences_digest=SeqColAttributeDigest("d" * 32),
        sequences=(
            SnapshotSequence(
                local_name="chr1",
                length=4,
                ordinal=0,
                refget_id=RefgetSequenceId("SQ." + "e" * 32),
                md5=_MD5_A,
            ),
        ),
        provider=IdentityProviderInfo(name="refget", version="0.12.0"),
    )

    payload = sequence_collection_snapshot_payload(snapshot)

    assert payload["type"] == "sequence_collection_snapshot"
    assert payload["resource_id"] == "reference.fa"
    assert payload["collection_digest"] == "a" * 32
    assert payload["provider"] == {"name": "refget", "version": "0.12.0"}
    assert payload["sequences"] == [
        {
            "name": "chr1",
            "length": 4,
            "ordinal": 0,
            "refget_id": "SQ." + "e" * 32,
            "md5": _MD5_A.value,
        }
    ]
    assert "verdict" not in payload


def test_human_snapshot_report_is_explicit_about_unavailable_values() -> None:
    snapshot = SequenceCollectionSnapshot(
        resource_id=ResourceId("partial"),
        completeness=CollectionCompleteness.PARTIAL,
        sequences=(SnapshotSequence(local_name="chr1"),),
    )

    rendered = render_sequence_collection_snapshot(snapshot)

    assert "completeness: partial" in rendered
    assert "SeqCol digest: unavailable" in rendered
    assert "identity provider: unavailable" in rendered
    assert "length=unavailable" in rendered


def test_fasta_index_diagnostic_preserves_structural_evidence() -> None:
    result = FastaIndexIntegrityResult(
        fasta_resource_id=ResourceId("reference.fa"),
        index_resource_id=ResourceId("reference.fa.fai"),
        differences=(
            FastaIndexDifference(
                kind=FastaIndexDifferenceKind.LENGTH,
                sequence_name="chr1",
                expected_value=4,
                observed_value=5,
            ),
        ),
    )

    payload = fasta_index_integrity_payload(result)
    rendered = render_fasta_index_integrity(result)

    assert payload["verified"] is False
    assert payload["evidence_strength"] == EvidenceStrength.TIER_B_DIRECT_STRUCTURAL.value
    assert payload["evidence_polarity"] == EvidencePolarity.CONTRADICTS.value
    assert "exact structural match: no" in rendered
    assert "- length: sequence=chr1; expected=4; observed=5" in rendered
    assert "compatible" not in rendered.lower()


def test_dictionary_diagnostic_keeps_conflicts_gaps_and_identity_separate() -> None:
    result = SequenceDictionaryIntegrityResult(
        fasta_resource_id=ResourceId("reference.fa"),
        dictionary_resource_id=ResourceId("reference.dict"),
        differences=(
            SequenceDictionaryDifference(
                kind=SequenceDictionaryDifferenceKind.M5_CONFLICT,
                sequence_name="chr2",
                expected_value=_MD5_A.value,
                observed_value=_MD5_B.value,
            ),
        ),
        missing_m5_sequences=("chr3",),
        renamed_identity_matches=(
            SequenceDictionaryContentIdentityMatch(
                expected_name="chr1",
                observed_name="1",
                md5=_MD5_A,
            ),
        ),
        cross_name_m5_length_inconsistencies=(
            SequenceDictionaryCrossNameM5LengthInconsistency(
                expected_name="chr4",
                observed_name="4",
                md5=_MD5_B,
                expected_length=4,
                observed_length=5,
            ),
        ),
    )

    payload = sequence_dictionary_integrity_payload(result)
    rendered = render_sequence_dictionary_integrity(result)

    differences = payload["differences"]
    assert isinstance(differences, list)
    assert differences[0]["evidence_strength"] == EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT.value
    assert payload["missing_m5_sequences"] == ["chr3"]
    matches = payload["renamed_identity_matches"]
    assert isinstance(matches, list)
    assert matches[0]["evidence_polarity"] == EvidencePolarity.SUPPORTS.value
    inconsistencies = payload["cross_name_m5_length_inconsistencies"]
    assert isinstance(inconsistencies, list)
    assert "evidence_strength" not in inconsistencies[0]
    assert "evidence_polarity" not in inconsistencies[0]
    assert "M5 evidence gaps:" in rendered
    assert "chr3: M5 unavailable" in rendered
    assert "cross-name M5/LN inconsistencies:" in rendered
    assert "expected LN=4; observed LN=5" in rendered
    assert "verdict" not in payload


def test_render_json_is_deterministic_pretty_json_with_trailing_newline() -> None:
    payload: dict[str, object] = {"type": "test", "value": 1}

    first = render_json(payload)
    second = render_json(payload)

    assert first == second
    assert first.endswith("\n")
    assert json.loads(first) == payload
