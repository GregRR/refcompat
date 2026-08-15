"""Unit tests for SAM sequence-dictionary domain invariants."""

from __future__ import annotations

import pytest

from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import ResourceId
from refcompat.model.sequence_dictionary import (
    ExpectedSequenceDictionary,
    MoleculeTopology,
    SequenceDictionaryContentIdentityMatch,
    SequenceDictionaryCrossNameM5LengthInconsistency,
    SequenceDictionaryData,
    SequenceDictionaryDifference,
    SequenceDictionaryDifferenceKind,
    SequenceDictionaryRecord,
)


def test_sequence_dictionary_record_preserves_standard_metadata() -> None:
    record = SequenceDictionaryRecord(
        name="chrM",
        length=16569,
        md5=Md5Digest("d41d8cd98f00b204e9800998ecf8427e"),
        alternate_names=("MT", "M", "chrMT"),
        assembly="GRCh38",
        species="Homo sapiens",
        uri="file:reference.fa",
        topology=MoleculeTopology.CIRCULAR,
        alternate_locus="*",
    )

    assert record.alternate_names == ("MT", "M", "chrMT")
    assert record.topology is MoleculeTopology.CIRCULAR


@pytest.mark.parametrize("length", [0, -1, 2**31])
def test_sequence_dictionary_record_rejects_invalid_sam_lengths(length: int) -> None:
    with pytest.raises(ValueError, match="sequence length"):
        SequenceDictionaryRecord(name="chr1", length=length)


def test_sequence_dictionary_data_requires_global_sn_an_uniqueness() -> None:
    with pytest.raises(ValueError, match="globally distinct"):
        SequenceDictionaryData(
            records=(
                SequenceDictionaryRecord(name="chr1", length=10, alternate_names=("1",)),
                SequenceDictionaryRecord(name="1", length=10),
            )
        )


def test_m5_conflict_is_tier_a_contradictory_evidence() -> None:
    difference = SequenceDictionaryDifference(kind=SequenceDictionaryDifferenceKind.M5_CONFLICT)
    assert difference.evidence_strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert difference.evidence_polarity is EvidencePolarity.CONTRADICTS


def test_renamed_identity_match_requires_different_names() -> None:
    with pytest.raises(ValueError, match="different primary names"):
        SequenceDictionaryContentIdentityMatch(
            expected_name="chr1",
            observed_name="chr1",
            md5=Md5Digest("d41d8cd98f00b204e9800998ecf8427e"),
        )


def test_cross_name_m5_length_inconsistency_requires_conflicting_records() -> None:
    md5 = Md5Digest("d41d8cd98f00b204e9800998ecf8427e")
    with pytest.raises(ValueError, match="different primary names"):
        SequenceDictionaryCrossNameM5LengthInconsistency(
            expected_name="chr1",
            observed_name="chr1",
            md5=md5,
            expected_length=4,
            observed_length=5,
        )
    with pytest.raises(ValueError, match="different declared lengths"):
        SequenceDictionaryCrossNameM5LengthInconsistency(
            expected_name="chr1",
            observed_name="1",
            md5=md5,
            expected_length=4,
            observed_length=4,
        )


def test_expected_dictionary_requires_m5_for_every_record() -> None:
    with pytest.raises(ValueError, match="require M5 identities"):
        ExpectedSequenceDictionary(
            fasta_resource_id=ResourceId("reference"),
            data=SequenceDictionaryData(records=(SequenceDictionaryRecord(name="chr1", length=4),)),
        )
