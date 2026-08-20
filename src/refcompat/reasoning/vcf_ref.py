"""Pure exhaustive VCF REF-to-FASTA comparison reasoning.

The evaluator consumes RefCompat-owned VCF record observations and a tiny
reference-sequence protocol. It never imports pysam or other format-parser
objects. Exact-name resolution is intentionally the only name-resolution mode
in this slice; verified SequenceBinding integration remains separate work.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from refcompat.model.resources import ResourceId
from refcompat.model.vcf_ref import (
    VcfRefCheckState,
    VcfRefRecord,
    VcfRefRecordCheck,
    VcfRefSequenceSummary,
    VcfRefValidationResult,
)


class VcfRefEvaluationError(Exception):
    """Direct VCF REF evaluation cannot produce a scientifically valid result."""


class ReferenceSequenceReader(Protocol):
    """Minimum FASTA access needed by the pure REF evaluator."""

    @property
    def resource_id(self) -> ResourceId: ...

    def sequence_length(self, sequence_name: str) -> int | None: ...

    def fetch(self, sequence_name: str, start: int, end: int) -> str: ...


_IUPAC_FASTA_TO_VCF = {
    "A": "A",
    "B": "C",
    "C": "C",
    "D": "A",
    "G": "G",
    "H": "A",
    "K": "G",
    "M": "A",
    "N": "N",
    "R": "A",
    "S": "C",
    "T": "T",
    "V": "A",
    "W": "A",
    "Y": "C",
}


def evaluate_vcf_ref_records(
    *,
    vcf_resource_id: ResourceId,
    fasta_resource_id: ResourceId,
    records: Iterable[VcfRefRecord],
    reference: ReferenceSequenceReader,
) -> VcfRefValidationResult:
    """Exhaustively classify every supplied VCF record against the FASTA anchor.

    VCF POS is converted explicitly from one-based to zero-based half-open
    coordinates. A sequence name not present exactly in the FASTA remains
    ``UNRESOLVED_SEQUENCE``; string resemblance is never treated as an alias.
    ``OUT_OF_BOUNDS`` means no ordinary FASTA interval can be compared and does
    not by itself assert that the VCF record is syntactically invalid (VCF 4.5
    permits telomere sentinel POS values 0 and N+1).
    """

    if not vcf_resource_id:
        raise ValueError("VCF resource ID must not be empty")
    if not fasta_resource_id:
        raise ValueError("FASTA resource ID must not be empty")
    if reference.resource_id != fasta_resource_id:
        raise ValueError("reference reader must belong to the supplied FASTA resource")

    aggregate = {
        VcfRefCheckState.MATCH: 0,
        VcfRefCheckState.MISMATCH: 0,
        VcfRefCheckState.OUT_OF_BOUNDS: 0,
        VcfRefCheckState.UNRESOLVED_SEQUENCE: 0,
    }
    sequence_counts: dict[str, dict[VcfRefCheckState, int]] = {}
    problem_records: list[VcfRefRecordCheck] = []
    record_count = 0

    for expected_ordinal, record in enumerate(records):
        if record.resource_id != vcf_resource_id:
            raise VcfRefEvaluationError("VCF REF record belongs to a different VCF resource")
        if record.ordinal != expected_ordinal:
            raise VcfRefEvaluationError(
                "VCF REF records must be exhaustive, contiguous, and zero-based in file order"
            )
        check = _evaluate_record(record, reference)
        record_count += 1
        aggregate[check.state] += 1
        by_state = sequence_counts.setdefault(
            record.sequence_name,
            {
                VcfRefCheckState.MATCH: 0,
                VcfRefCheckState.MISMATCH: 0,
                VcfRefCheckState.OUT_OF_BOUNDS: 0,
                VcfRefCheckState.UNRESOLVED_SEQUENCE: 0,
            },
        )
        by_state[check.state] += 1
        if check.state is not VcfRefCheckState.MATCH:
            problem_records.append(check)

    sequence_summaries = tuple(
        VcfRefSequenceSummary(
            sequence_name=sequence_name,
            record_count=sum(counts.values()),
            match_count=counts[VcfRefCheckState.MATCH],
            mismatch_count=counts[VcfRefCheckState.MISMATCH],
            out_of_bounds_count=counts[VcfRefCheckState.OUT_OF_BOUNDS],
            unresolved_sequence_count=counts[VcfRefCheckState.UNRESOLVED_SEQUENCE],
        )
        for sequence_name, counts in sequence_counts.items()
    )

    return VcfRefValidationResult(
        vcf_resource_id=vcf_resource_id,
        fasta_resource_id=fasta_resource_id,
        record_count=record_count,
        match_count=aggregate[VcfRefCheckState.MATCH],
        mismatch_count=aggregate[VcfRefCheckState.MISMATCH],
        out_of_bounds_count=aggregate[VcfRefCheckState.OUT_OF_BOUNDS],
        unresolved_sequence_count=aggregate[VcfRefCheckState.UNRESOLVED_SEQUENCE],
        sequence_summaries=sequence_summaries,
        problem_records=tuple(problem_records),
    )


def _evaluate_record(
    record: VcfRefRecord,
    reference: ReferenceSequenceReader,
) -> VcfRefRecordCheck:
    sequence_length = reference.sequence_length(record.sequence_name)
    if sequence_length is None:
        return VcfRefRecordCheck(record, VcfRefCheckState.UNRESOLVED_SEQUENCE)

    start = record.position - 1
    end = start + len(record.ref)
    if start < 0 or end > sequence_length:
        return VcfRefRecordCheck(
            record,
            VcfRefCheckState.OUT_OF_BOUNDS,
            anchor_sequence_name=record.sequence_name,
        )

    fasta_bases = reference.fetch(record.sequence_name, start, end)
    if len(fasta_bases) != len(record.ref):
        raise VcfRefEvaluationError("reference reader returned a FASTA span of unexpected length")
    normalized_fasta = _normalize_fasta_for_vcf(fasta_bases, record=record)
    if normalized_fasta == record.ref.upper():
        return VcfRefRecordCheck(
            record,
            VcfRefCheckState.MATCH,
            anchor_sequence_name=record.sequence_name,
        )
    return VcfRefRecordCheck(
        record,
        VcfRefCheckState.MISMATCH,
        anchor_sequence_name=record.sequence_name,
        fasta_bases=fasta_bases.upper(),
    )


def _normalize_fasta_for_vcf(bases: str, *, record: VcfRefRecord) -> str:
    normalized: list[str] = []
    for base in bases.upper():
        replacement = _IUPAC_FASTA_TO_VCF.get(base)
        if replacement is None:
            raise VcfRefEvaluationError(
                "FASTA contains an unsupported base for VCF REF comparison "
                f"at record {record.ordinal} ({record.sequence_name}:{record.position})"
            )
        normalized.append(replacement)
    return "".join(normalized)
