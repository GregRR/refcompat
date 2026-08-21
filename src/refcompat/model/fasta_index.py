"""FASTA index (``.fai``) structural values and comparison results.

The FAI format describes byte-level random-access geometry for a particular
FASTA representation. These values therefore model an exact derived artifact,
not biological sequence equivalence: a verified alias cannot make an index for
``1`` the correct companion index for a FASTA record named ``chr1``.

References:
- HTSlib faidx(5): https://www.htslib.org/doc/faidx.html
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import StrEnum
from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.resources import ResourceId


@dataclass(frozen=True, slots=True)
class FastaIndexRecord:
    """One five-column FASTA ``.fai`` record."""

    name: str
    length: int
    offset: int
    line_bases: int
    line_bytes: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("FAI sequence name must not be empty")
        if any(character.isspace() for character in self.name):
            raise ValueError("FAI sequence name must not contain whitespace")
        if self.length < 0:
            raise ValueError("FAI sequence length must not be negative")
        if self.offset < 0:
            raise ValueError("FAI byte offset must not be negative")
        if self.line_bases < 0:
            raise ValueError("FAI line-bases value must not be negative")
        if self.line_bytes < 0:
            raise ValueError("FAI line-bytes value must not be negative")
        if self.length > 0 and self.line_bases == 0:
            raise ValueError("non-empty FAI sequence must have a positive line-bases value")
        if self.length > 0 and self.line_bases > self.length:
            raise ValueError("FAI line-bases value must not exceed sequence length")
        if self.line_bytes < self.line_bases:
            raise ValueError("FAI line-bytes value must be at least the line-bases value")
        if self.length > self.line_bases and self.line_bytes == self.line_bases:
            raise ValueError("multi-line FAI sequence must include line-terminator bytes")


@dataclass(frozen=True, slots=True)
class FastaIndexData:
    """Ordered FAI records extracted from or computed for one FASTA representation."""

    records: tuple[FastaIndexRecord, ...]

    def __post_init__(self) -> None:
        if not self.records:
            raise ValueError("FAI data must contain at least one sequence record")
        names = tuple(record.name for record in self.records)
        if len(set(names)) != len(names):
            raise ValueError("FAI sequence names must be unique")


@dataclass(frozen=True, slots=True)
class FastaIndexSnapshot:
    """FAI data parsed from one supplied FASTA-index resource."""

    resource_id: ResourceId
    data: FastaIndexData

    @property
    def records(self) -> tuple[FastaIndexRecord, ...]:
        return self.data.records


@dataclass(frozen=True, slots=True)
class ComputedFastaIndex:
    """Expected FAI geometry computed from one supplied FASTA resource."""

    fasta_resource_id: ResourceId
    data: FastaIndexData

    @property
    def records(self) -> tuple[FastaIndexRecord, ...]:
        return self.data.records


class FastaIndexDifferenceKind(StrEnum):
    """Exact structural differences between expected and observed FAI data."""

    RECORD_COUNT = "record_count"
    MISSING_SEQUENCE = "missing_sequence"
    EXTRA_SEQUENCE = "extra_sequence"
    ORDER = "order"
    LENGTH = "length"
    OFFSET = "offset"
    LINE_BASES = "line_bases"
    LINE_BYTES = "line_bytes"


@dataclass(frozen=True, slots=True)
class FastaIndexDifference:
    """One localized difference in an exact FASTA/index comparison."""

    kind: FastaIndexDifferenceKind
    sequence_name: str | None = None
    expected_ordinal: int | None = None
    observed_ordinal: int | None = None
    expected_value: str | int | None = None
    observed_value: str | int | None = None


@dataclass(frozen=True, slots=True)
class FastaIndexIntegrityResult:
    """Tier-B structural result for one explicitly paired FASTA and ``.fai``."""

    fasta_resource_id: ResourceId
    index_resource_id: ResourceId
    differences: tuple[FastaIndexDifference, ...] = ()

    @property
    def verified(self) -> bool:
        """Whether the observed index exactly matches computed FASTA geometry."""

        return not self.differences

    @property
    def evidence_strength(self) -> EvidenceStrength:
        """FAI correspondence is direct structural evidence, not sequence-content identity."""

        return EvidenceStrength.TIER_B_DIRECT_STRUCTURAL

    @property
    def evidence_polarity(self) -> EvidencePolarity:
        """Whether the structural evidence supports or contradicts exact correspondence."""

        if self.verified:
            return EvidencePolarity.SUPPORTS
        return EvidencePolarity.CONTRADICTS
