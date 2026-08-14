import pytest

from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.fasta_index import (
    FastaIndexData,
    FastaIndexDifference,
    FastaIndexDifferenceKind,
    FastaIndexIntegrityResult,
    FastaIndexRecord,
)
from refcompat.model.resources import ResourceId


def test_fasta_index_record_validates_geometry() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        FastaIndexRecord(name="chr 1", length=10, offset=5, line_bases=10, line_bytes=11)

    with pytest.raises(ValueError, match="line-bytes"):
        FastaIndexRecord(name="chr1", length=10, offset=5, line_bases=10, line_bytes=9)

    with pytest.raises(ValueError, match="positive line-bases"):
        FastaIndexRecord(name="chr1", length=10, offset=5, line_bases=0, line_bytes=0)

    with pytest.raises(ValueError, match="must not exceed"):
        FastaIndexRecord(name="chr1", length=10, offset=5, line_bases=11, line_bytes=12)

    with pytest.raises(ValueError, match="line-terminator"):
        FastaIndexRecord(name="chr1", length=20, offset=5, line_bases=10, line_bytes=10)


def test_fasta_index_data_requires_unique_nonempty_records() -> None:
    record = FastaIndexRecord(name="chr1", length=4, offset=6, line_bases=4, line_bytes=5)

    with pytest.raises(ValueError, match="at least one"):
        FastaIndexData(())

    with pytest.raises(ValueError, match="unique"):
        FastaIndexData((record, record))


def test_integrity_result_is_tier_b_and_verified_only_without_differences() -> None:
    verified = FastaIndexIntegrityResult(ResourceId("fasta"), ResourceId("fai"))
    assert verified.verified
    assert verified.evidence_strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert verified.evidence_polarity is EvidencePolarity.SUPPORTS

    mismatch = FastaIndexIntegrityResult(
        ResourceId("fasta"),
        ResourceId("fai"),
        (FastaIndexDifference(FastaIndexDifferenceKind.LENGTH, sequence_name="chr1"),),
    )
    assert not mismatch.verified
    assert mismatch.evidence_polarity is EvidencePolarity.CONTRADICTS
