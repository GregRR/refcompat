"""Direct VCF REF-to-FASTA validation values.

These immutable values describe exhaustive record-level REF comparison against
an explicitly supplied FASTA anchor. They preserve local conflicts and
unresolved records without converting the direct check into a bundle verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import StrEnum
from refcompat.model.reference_context import SequenceBindingId
from refcompat.model.resources import ResourceId


class VcfRefCheckState(StrEnum):
    """Direct outcome for one VCF record against the FASTA anchor."""

    MATCH = "match"
    MISMATCH = "mismatch"
    OUT_OF_BOUNDS = "out_of_bounds"
    UNRESOLVED_SEQUENCE = "unresolved_sequence"


@dataclass(frozen=True, slots=True)
class VcfRefRecord:
    """Reference-relevant fields copied from one VCF record.

    ``resource_id`` preserves the source VCF identity. ``ordinal`` is zero-based
    file order. ``position`` preserves VCF's native
    one-based POS value, including the specification's telomere sentinel value
    ``0``. REF is preserved as parser-exposed text and validated against the
    VCF A/C/G/T/N alphabet.
    """

    resource_id: ResourceId
    ordinal: int
    sequence_name: str
    position: int
    ref: str

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("VCF REF record resource ID must not be empty")
        if self.ordinal < 0:
            raise ValueError("VCF record ordinal must not be negative")
        if not self.sequence_name:
            raise ValueError("VCF record sequence name must not be empty")
        if self.position < 0:
            raise ValueError("VCF record POS must not be negative")
        if not self.ref:
            raise ValueError("VCF REF must not be empty")
        if any(base not in "ACGTNacgtn" for base in self.ref):
            raise ValueError("VCF REF must contain only A, C, G, T, or N")


@dataclass(frozen=True, slots=True)
class VcfRefRecordCheck:
    """One non-aggregate record outcome against the FASTA anchor.

    Matching records intentionally do not retain fetched FASTA bases so a large
    compatible VCF does not require memory proportional to its record count.
    Mismatches retain the actual fetched FASTA text needed to explain the hard
    local contradiction.
    """

    record: VcfRefRecord
    state: VcfRefCheckState
    anchor_sequence_name: str | None = None
    fasta_bases: str | None = None

    def __post_init__(self) -> None:
        if self.state is VcfRefCheckState.UNRESOLVED_SEQUENCE:
            if self.anchor_sequence_name is not None or self.fasta_bases is not None:
                raise ValueError("unresolved VCF sequence cannot cite anchor bases")
            return

        if not self.anchor_sequence_name:
            raise ValueError("resolved VCF REF check requires an anchor sequence name")

        if self.state is VcfRefCheckState.MISMATCH:
            if not self.fasta_bases:
                raise ValueError("VCF REF mismatch must retain fetched FASTA bases")
            if len(self.fasta_bases) != len(self.record.ref):
                raise ValueError("VCF REF mismatch FASTA span must match REF length")
            return

        if self.fasta_bases is not None:
            raise ValueError("only VCF REF mismatches retain fetched FASTA bases")


@dataclass(frozen=True, slots=True)
class VcfRefSequenceSummary:
    """Exhaustive per-VCF-sequence counts for direct REF checking."""

    sequence_name: str
    record_count: int
    match_count: int = 0
    mismatch_count: int = 0
    out_of_bounds_count: int = 0
    unresolved_sequence_count: int = 0

    def __post_init__(self) -> None:
        if not self.sequence_name:
            raise ValueError("VCF REF summary sequence name must not be empty")
        counts = (
            self.record_count,
            self.match_count,
            self.mismatch_count,
            self.out_of_bounds_count,
            self.unresolved_sequence_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("VCF REF summary counts must not be negative")
        classified = (
            self.match_count
            + self.mismatch_count
            + self.out_of_bounds_count
            + self.unresolved_sequence_count
        )
        if classified != self.record_count:
            raise ValueError("VCF REF summary outcome counts must sum to record count")


@dataclass(frozen=True, slots=True)
class VcfRefValidationResult:
    """Exhaustive direct REF comparison for one VCF and FASTA pair.

    Only non-matching record outcomes are retained individually. Aggregate
    counts still cover every record, so matching VCFs remain memory-efficient
    while each conflict/unresolved record remains directly traceable.
    """

    vcf_resource_id: ResourceId
    fasta_resource_id: ResourceId
    record_count: int
    match_count: int
    mismatch_count: int
    out_of_bounds_count: int
    unresolved_sequence_count: int
    sequence_summaries: tuple[VcfRefSequenceSummary, ...] = ()
    problem_records: tuple[VcfRefRecordCheck, ...] = ()
    sequence_binding_ids: tuple[SequenceBindingId, ...] = ()

    def __post_init__(self) -> None:
        if not self.vcf_resource_id:
            raise ValueError("VCF REF validation VCF resource ID must not be empty")
        if not self.fasta_resource_id:
            raise ValueError("VCF REF validation FASTA resource ID must not be empty")
        counts = (
            self.record_count,
            self.match_count,
            self.mismatch_count,
            self.out_of_bounds_count,
            self.unresolved_sequence_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("VCF REF validation counts must not be negative")
        classified = (
            self.match_count
            + self.mismatch_count
            + self.out_of_bounds_count
            + self.unresolved_sequence_count
        )
        if classified != self.record_count:
            raise ValueError("VCF REF validation outcome counts must sum to record count")

        names = tuple(summary.sequence_name for summary in self.sequence_summaries)
        if len(set(names)) != len(names):
            raise ValueError("VCF REF sequence summaries must have unique names")
        if sum(summary.record_count for summary in self.sequence_summaries) != self.record_count:
            raise ValueError("VCF REF sequence summary counts must cover every record")
        if sum(summary.match_count for summary in self.sequence_summaries) != self.match_count:
            raise ValueError("VCF REF sequence match counts must match aggregate count")
        if (
            sum(summary.mismatch_count for summary in self.sequence_summaries)
            != self.mismatch_count
        ):
            raise ValueError("VCF REF sequence mismatch counts must match aggregate count")
        if (
            sum(summary.out_of_bounds_count for summary in self.sequence_summaries)
            != self.out_of_bounds_count
        ):
            raise ValueError("VCF REF sequence bounds counts must match aggregate count")
        if (
            sum(summary.unresolved_sequence_count for summary in self.sequence_summaries)
            != self.unresolved_sequence_count
        ):
            raise ValueError("VCF REF sequence unresolved counts must match aggregate count")

        expected_problem_count = (
            self.mismatch_count + self.out_of_bounds_count + self.unresolved_sequence_count
        )
        if len(self.problem_records) != expected_problem_count:
            raise ValueError("VCF REF problem records must cover every non-match outcome")
        if any(check.state is VcfRefCheckState.MATCH for check in self.problem_records):
            raise ValueError("VCF REF problem records cannot contain MATCH outcomes")
        if any(check.record.resource_id != self.vcf_resource_id for check in self.problem_records):
            raise ValueError("VCF REF problem record belongs to a different VCF resource")
        problem_state_counts = {
            state: sum(check.state is state for check in self.problem_records)
            for state in (
                VcfRefCheckState.MISMATCH,
                VcfRefCheckState.OUT_OF_BOUNDS,
                VcfRefCheckState.UNRESOLVED_SEQUENCE,
            )
        }
        if problem_state_counts[VcfRefCheckState.MISMATCH] != self.mismatch_count:
            raise ValueError("VCF REF mismatch records must match aggregate count")
        if problem_state_counts[VcfRefCheckState.OUT_OF_BOUNDS] != self.out_of_bounds_count:
            raise ValueError("VCF REF bounds records must match aggregate count")
        if (
            problem_state_counts[VcfRefCheckState.UNRESOLVED_SEQUENCE]
            != self.unresolved_sequence_count
        ):
            raise ValueError("VCF REF unresolved records must match aggregate count")
        ordinals = tuple(check.record.ordinal for check in self.problem_records)
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("VCF REF problem record ordinals must be unique")
        if ordinals != tuple(sorted(ordinals)):
            raise ValueError("VCF REF problem records must retain file order")
        if any(ordinal >= self.record_count for ordinal in ordinals):
            raise ValueError("VCF REF problem record ordinal exceeds record count")

        if any(not binding_id for binding_id in self.sequence_binding_ids):
            raise ValueError("VCF REF sequence-binding IDs must not be empty")
        if len(set(self.sequence_binding_ids)) != len(self.sequence_binding_ids):
            raise ValueError("VCF REF sequence-binding IDs must be unique")
        if self.sequence_binding_ids != tuple(sorted(self.sequence_binding_ids, key=str)):
            raise ValueError("VCF REF sequence-binding IDs must use deterministic order")

        summary_names = set(names)
        if any(check.record.sequence_name not in summary_names for check in self.problem_records):
            raise ValueError("VCF REF problem record must belong to a sequence summary")
