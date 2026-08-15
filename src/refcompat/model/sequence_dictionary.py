"""SAM/Picard sequence-dictionary values and integrity results.

A sequence dictionary is a SAM header composed primarily of ordered ``@SQ``
records. RefCompat models exact dictionary structure separately from biological
sequence identity: a declared alias can describe the same sequence while still
failing an exact FASTA/``.dict`` companion-artifact relationship.

References:
- SAM v1 specification: https://samtools.github.io/hts-specs/SAMv1.pdf
- samtools dict: https://www.htslib.org/doc/samtools-dict.html
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import ResourceId

_MAX_SAM_REFERENCE_LENGTH = (1 << 31) - 1
_SAM_REFERENCE_NAME_RE = re.compile(
    r"^[0-9A-Za-z!#$%&+./:;?@^_|~-][0-9A-Za-z!#$%&*+./:;=?@^_|~-]*$"
)


class MoleculeTopology(StrEnum):
    """SAM ``@SQ TP`` molecule topology."""

    LINEAR = "linear"
    CIRCULAR = "circular"


@dataclass(frozen=True, slots=True)
class SequenceDictionaryRecord:
    """One ordered SAM ``@SQ`` sequence-dictionary record."""

    name: str
    length: int
    md5: Md5Digest | None = None
    alternate_names: tuple[str, ...] = ()
    assembly: str | None = None
    species: str | None = None
    uri: str | None = None
    topology: MoleculeTopology | None = None
    alternate_locus: str | None = None

    def __post_init__(self) -> None:
        _validate_reference_name(self.name, field="SN")
        if not 1 <= self.length <= _MAX_SAM_REFERENCE_LENGTH:
            raise ValueError("SAM dictionary sequence length must be in [1, 2^31-1]")

        if len(set(self.alternate_names)) != len(self.alternate_names):
            raise ValueError("SAM dictionary AN values must be unique within a record")
        for alternate_name in self.alternate_names:
            _validate_reference_name(alternate_name, field="AN")

        for tag, value in (
            ("AS", self.assembly),
            ("SP", self.species),
            ("UR", self.uri),
            ("AH", self.alternate_locus),
        ):
            if value is not None and not value:
                raise ValueError(f"SAM dictionary {tag} value must not be empty")


@dataclass(frozen=True, slots=True)
class SequenceDictionaryData:
    """Ordered ``@SQ`` records extracted from one sequence dictionary."""

    records: tuple[SequenceDictionaryRecord, ...]
    sam_version: str | None = None

    def __post_init__(self) -> None:
        if not self.records:
            raise ValueError("sequence dictionary must contain at least one @SQ record")
        if self.sam_version is not None and not self.sam_version:
            raise ValueError("SAM version must not be empty")

        all_names: list[str] = []
        for record in self.records:
            all_names.append(record.name)
            all_names.extend(record.alternate_names)
        if len(set(all_names)) != len(all_names):
            raise ValueError("SAM dictionary SN and AN names must be globally distinct")


@dataclass(frozen=True, slots=True)
class SequenceDictionarySnapshot:
    """Sequence dictionary parsed from one supplied ``.dict`` resource."""

    resource_id: ResourceId
    data: SequenceDictionaryData

    @property
    def records(self) -> tuple[SequenceDictionaryRecord, ...]:
        return self.data.records


@dataclass(frozen=True, slots=True)
class ExpectedSequenceDictionary:
    """Expected dictionary records derived from one complete FASTA snapshot."""

    fasta_resource_id: ResourceId
    data: SequenceDictionaryData

    def __post_init__(self) -> None:
        if any(record.md5 is None for record in self.data.records):
            raise ValueError("expected FASTA dictionary records require M5 identities")

    @property
    def records(self) -> tuple[SequenceDictionaryRecord, ...]:
        return self.data.records


class SequenceDictionaryDifferenceKind(StrEnum):
    """Contradictions found in exact FASTA/sequence-dictionary comparison."""

    RECORD_COUNT = "record_count"
    MISSING_SEQUENCE = "missing_sequence"
    EXTRA_SEQUENCE = "extra_sequence"
    ORDER = "order"
    LENGTH = "length"
    M5_CONFLICT = "m5_conflict"


@dataclass(frozen=True, slots=True)
class SequenceDictionaryDifference:
    """One localized contradiction in an exact sequence-dictionary check."""

    kind: SequenceDictionaryDifferenceKind
    sequence_name: str | None = None
    expected_ordinal: int | None = None
    observed_ordinal: int | None = None
    expected_value: str | int | None = None
    observed_value: str | int | None = None

    @property
    def evidence_strength(self) -> EvidenceStrength:
        """M5 is content evidence; other dictionary fields are structural evidence."""

        if self.kind is SequenceDictionaryDifferenceKind.M5_CONFLICT:
            return EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
        return EvidenceStrength.TIER_B_DIRECT_STRUCTURAL

    @property
    def evidence_polarity(self) -> EvidencePolarity:
        return EvidencePolarity.CONTRADICTS


@dataclass(frozen=True, slots=True)
class SequenceDictionaryContentIdentityMatch:
    """Unique M5-backed sequence identity observed under different primary names.

    This is Tier-A evidence that the two named records carry the same sequence
    content under SAM M5 semantics. It does not satisfy exact derived-artifact
    correspondence because the primary ``SN`` values still differ.
    """

    expected_name: str
    observed_name: str
    md5: Md5Digest

    def __post_init__(self) -> None:
        if self.expected_name == self.observed_name:
            raise ValueError("renamed identity match requires different primary names")

    @property
    def evidence_strength(self) -> EvidenceStrength:
        return EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT

    @property
    def evidence_polarity(self) -> EvidencePolarity:
        return EvidencePolarity.SUPPORTS


@dataclass(frozen=True, slots=True)
class SequenceDictionaryCrossNameM5LengthInconsistency:
    """Unique cross-name M5 agreement paired with conflicting declared lengths.

    RefCompat retains this mixed observation instead of silently dropping the
    shared M5 or promoting the records to an uncomplicated content-identity
    match. The inconsistency does not identify which declared field is wrong.
    """

    expected_name: str
    observed_name: str
    md5: Md5Digest
    expected_length: int
    observed_length: int

    def __post_init__(self) -> None:
        if self.expected_name == self.observed_name:
            raise ValueError("cross-name M5/LN inconsistency requires different primary names")
        if self.expected_length == self.observed_length:
            raise ValueError("M5/LN inconsistency requires different declared lengths")


@dataclass(frozen=True, slots=True)
class SequenceDictionaryIntegrityResult:
    """Evidence for one explicitly paired FASTA and sequence dictionary."""

    fasta_resource_id: ResourceId
    dictionary_resource_id: ResourceId
    differences: tuple[SequenceDictionaryDifference, ...] = ()
    missing_m5_sequences: tuple[str, ...] = ()
    renamed_identity_matches: tuple[SequenceDictionaryContentIdentityMatch, ...] = ()
    cross_name_m5_length_inconsistencies: tuple[
        SequenceDictionaryCrossNameM5LengthInconsistency, ...
    ] = ()

    @property
    def structurally_verified(self) -> bool:
        """Whether names, membership, order, and lengths match exactly."""

        structural_kinds = {
            SequenceDictionaryDifferenceKind.RECORD_COUNT,
            SequenceDictionaryDifferenceKind.MISSING_SEQUENCE,
            SequenceDictionaryDifferenceKind.EXTRA_SEQUENCE,
            SequenceDictionaryDifferenceKind.ORDER,
            SequenceDictionaryDifferenceKind.LENGTH,
        }
        return not any(difference.kind in structural_kinds for difference in self.differences)

    @property
    def content_verified(self) -> bool:
        """Whether every exact-name record has an observed matching M5."""

        return (
            self.structurally_verified
            and not self.missing_m5_sequences
            and not any(
                difference.kind is SequenceDictionaryDifferenceKind.M5_CONFLICT
                for difference in self.differences
            )
        )

    @property
    def exact_companion_verified(self) -> bool:
        """Whether exact structure and M5 content identity are both verified."""

        return self.structurally_verified and self.content_verified

    @property
    def has_conflict(self) -> bool:
        """Whether any structural, content, or retained M5/LN conflict is present."""

        return bool(self.differences or self.cross_name_m5_length_inconsistencies)


def _validate_reference_name(value: str, *, field: str) -> None:
    if not value or _SAM_REFERENCE_NAME_RE.fullmatch(value) is None:
        raise ValueError(f"SAM dictionary {field} value is not a valid reference name")
