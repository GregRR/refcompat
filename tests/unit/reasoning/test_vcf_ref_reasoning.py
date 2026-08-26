"""Unit tests for exhaustive pure VCF REF-to-FASTA comparison."""

from __future__ import annotations

import pytest

from refcompat.model.contracts import CapabilityId
from refcompat.model.identity import Md5Digest
from refcompat.model.reference_context import (
    SequenceBinding,
    SequenceBindingId,
    SequenceBindingMethod,
)
from refcompat.model.resources import ResourceId
from refcompat.model.vcf_ref import VcfRefCheckState, VcfRefRecord, VcfRefValidationResult
from refcompat.reasoning.vcf_ref import VcfRefEvaluationError, evaluate_vcf_ref_records

_VCF = ResourceId("variants")
_FASTA = ResourceId("reference")


class _Reference:
    def __init__(self, sequences: dict[str, str]) -> None:
        self.resource_id = _FASTA
        self._sequences = sequences
        self.fetches: list[tuple[str, int, int]] = []

    def sequence_length(self, sequence_name: str) -> int | None:
        sequence = self._sequences.get(sequence_name)
        return None if sequence is None else len(sequence)

    def fetch(self, sequence_name: str, start: int, end: int) -> str:
        self.fetches.append((sequence_name, start, end))
        return self._sequences[sequence_name][start:end]


def _evaluate(
    records: tuple[VcfRefRecord, ...], reference: _Reference | None = None
) -> VcfRefValidationResult:
    reader = reference or _Reference({"chr1": "ACGTACGT", "chr2": "TTTT"})
    return evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=records,
        reference=reader,
    )


def test_exact_and_multibase_ref_matches_use_explicit_vcf_coordinates() -> None:
    reference = _Reference({"chr1": "ACGTACGT"})
    result = _evaluate(
        (
            VcfRefRecord(_VCF, 0, "chr1", 1, "A"),
            VcfRefRecord(_VCF, 1, "chr1", 4, "TA"),
        ),
        reference,
    )

    assert result.record_count == 2
    assert result.match_count == 2
    assert result.problem_records == ()
    assert reference.fetches == [("chr1", 0, 1), ("chr1", 3, 5)]


def test_mismatch_is_retained_even_beside_many_matches() -> None:
    records = (
        *(VcfRefRecord(_VCF, index, "chr1", 1, "A") for index in range(20)),
        VcfRefRecord(_VCF, 20, "chr1", 2, "T"),
    )
    result = _evaluate(records)

    assert result.match_count == 20
    assert result.mismatch_count == 1
    assert len(result.problem_records) == 1
    mismatch = result.problem_records[0]
    assert mismatch.state is VcfRefCheckState.MISMATCH
    assert mismatch.record.ordinal == 20
    assert mismatch.fasta_bases == "C"


def test_multiple_independent_mismatches_remain_traceable() -> None:
    result = _evaluate(
        (
            VcfRefRecord(_VCF, 0, "chr1", 2, "T"),
            VcfRefRecord(_VCF, 1, "chr1", 3, "A"),
        )
    )

    assert result.mismatch_count == 2
    assert [(check.record.ordinal, check.fasta_bases) for check in result.problem_records] == [
        (0, "C"),
        (1, "G"),
    ]


def test_ref_span_ending_exactly_at_sequence_length_is_valid() -> None:
    reference = _Reference({"chr1": "ACGTACGT"})
    result = _evaluate((VcfRefRecord(_VCF, 0, "chr1", 7, "GT"),), reference)

    assert result.match_count == 1
    assert result.out_of_bounds_count == 0
    assert reference.fetches == [("chr1", 6, 8)]


def test_lowercase_fasta_and_ref_compare_case_insensitively() -> None:
    result = _evaluate(
        (VcfRefRecord(_VCF, 0, "chr1", 1, "acgt"),),
        _Reference({"chr1": "acgt"}),
    )

    assert result.match_count == 1
    assert result.problem_records == ()


def test_zero_record_stream_produces_empty_exhaustive_result() -> None:
    result = _evaluate(())

    assert result.record_count == 0
    assert result.match_count == 0
    assert result.mismatch_count == 0
    assert result.out_of_bounds_count == 0
    assert result.unresolved_sequence_count == 0
    assert result.sequence_summaries == ()
    assert result.problem_records == ()


def test_missing_exact_name_is_unresolved_without_fetch_or_alias_guess() -> None:
    reference = _Reference({"chr1": "ACGT"})
    result = _evaluate((VcfRefRecord(_VCF, 0, "1", 1, "A"),), reference)

    assert result.unresolved_sequence_count == 1
    assert result.problem_records[0].state is VcfRefCheckState.UNRESOLVED_SEQUENCE
    assert result.problem_records[0].anchor_sequence_name is None
    assert reference.fetches == []


@pytest.mark.parametrize("position", [0, 5])
def test_telomere_sentinel_positions_are_directly_out_of_bounds(position: int) -> None:
    reference = _Reference({"chr1": "ACGT"})
    result = _evaluate((VcfRefRecord(_VCF, 0, "chr1", position, "A"),), reference)

    assert result.out_of_bounds_count == 1
    assert result.problem_records[0].state is VcfRefCheckState.OUT_OF_BOUNDS
    assert reference.fetches == []


def test_multibase_ref_span_past_sequence_end_is_out_of_bounds() -> None:
    result = _evaluate((VcfRefRecord(_VCF, 0, "chr1", 8, "TA"),))

    assert result.out_of_bounds_count == 1
    assert result.problem_records[0].state is VcfRefCheckState.OUT_OF_BOUNDS


def test_fasta_iupac_bases_follow_vcf_alphabetical_reduction_rule() -> None:
    reference = _Reference({"chr1": "RYSWKMBDHVN"})
    expected = "ACCAGACAAAN"
    records = tuple(
        VcfRefRecord(_VCF, index, "chr1", index + 1, ref) for index, ref in enumerate(expected)
    )
    result = _evaluate(records, reference)

    assert result.match_count == len(expected)
    assert result.problem_records == ()


def test_unsupported_fasta_base_fails_instead_of_fabricating_mismatch() -> None:
    with pytest.raises(VcfRefEvaluationError, match="unsupported base"):
        _evaluate((VcfRefRecord(_VCF, 0, "chr1", 1, "A"),), _Reference({"chr1": "Z"}))


def test_sequence_summaries_preserve_first_observed_order_and_all_states() -> None:
    result = _evaluate(
        (
            VcfRefRecord(_VCF, 0, "chr2", 1, "T"),
            VcfRefRecord(_VCF, 1, "chr1", 1, "A"),
            VcfRefRecord(_VCF, 2, "chr2", 1, "A"),
            VcfRefRecord(_VCF, 3, "missing", 1, "A"),
        )
    )

    assert [summary.sequence_name for summary in result.sequence_summaries] == [
        "chr2",
        "chr1",
        "missing",
    ]
    chr2 = result.sequence_summaries[0]
    assert (chr2.record_count, chr2.match_count, chr2.mismatch_count) == (2, 1, 1)


def test_noncontiguous_record_ordinals_reject_nonexhaustive_stream() -> None:
    with pytest.raises(VcfRefEvaluationError, match="exhaustive, contiguous"):
        _evaluate((VcfRefRecord(_VCF, 1, "chr1", 1, "A"),))


def test_vcf_records_must_belong_to_requested_vcf_resource() -> None:
    record = VcfRefRecord(ResourceId("other"), 0, "chr1", 1, "A")
    with pytest.raises(VcfRefEvaluationError, match="different VCF resource"):
        _evaluate((record,))


def test_reference_reader_must_belong_to_requested_fasta() -> None:
    reference = _Reference({"chr1": "A"})
    reference.resource_id = ResourceId("other")
    with pytest.raises(ValueError, match="must belong"):
        _evaluate((), reference)


def _binding(local_name: str = "1", anchor_name: str = "chr1") -> SequenceBinding:
    return SequenceBinding(
        id=SequenceBindingId(f"binding-{local_name}-{anchor_name}"),
        resource_id=_VCF,
        local_sequence_name=local_name,
        anchor_resource_id=_FASTA,
        anchor_sequence_name=anchor_name,
        method=SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
        identity_values=(Md5Digest("f1f8f4bf413b16ad135722aa4591043e"),),
        capability_ids=(CapabilityId("local"), CapabilityId("anchor")),
    )


def test_verified_binding_revalidates_cross_name_record() -> None:
    binding = _binding()
    result = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 1, "A"),),
        reference=_Reference({"chr1": "ACGT"}),
        sequence_bindings=(binding,),
    )

    assert result.match_count == 1
    assert result.unresolved_sequence_count == 0
    assert result.sequence_binding_ids == (binding.id,)


def test_verified_binding_mismatch_retains_actual_anchor_name() -> None:
    binding = _binding()
    result = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 2, "T"),),
        reference=_Reference({"chr1": "ACGT"}),
        sequence_bindings=(binding,),
    )

    mismatch = result.problem_records[0]
    assert mismatch.state is VcfRefCheckState.MISMATCH
    assert mismatch.anchor_sequence_name == "chr1"
    assert mismatch.fasta_bases == "C"


def test_verified_binding_target_missing_from_reader_is_crosswire_error() -> None:
    binding = _binding(anchor_name="chrMissing")
    with pytest.raises(VcfRefEvaluationError, match="binding target is absent"):
        evaluate_vcf_ref_records(
            vcf_resource_id=_VCF,
            fasta_resource_id=_FASTA,
            records=(VcfRefRecord(_VCF, 0, "1", 1, "A"),),
            reference=_Reference({"chr1": "ACGT"}),
            sequence_bindings=(binding,),
        )


def test_binding_resource_and_anchor_are_validated() -> None:
    from dataclasses import replace

    binding = _binding()
    with pytest.raises(ValueError, match="belong to the VCF"):
        evaluate_vcf_ref_records(
            vcf_resource_id=_VCF,
            fasta_resource_id=_FASTA,
            records=(),
            reference=_Reference({"chr1": "ACGT"}),
            sequence_bindings=(replace(binding, resource_id=ResourceId("other")),),
        )
    with pytest.raises(ValueError, match="supplied FASTA anchor"):
        evaluate_vcf_ref_records(
            vcf_resource_id=_VCF,
            fasta_resource_id=_FASTA,
            records=(),
            reference=_Reference({"chr1": "ACGT"}),
            sequence_bindings=(replace(binding, anchor_resource_id=ResourceId("other")),),
        )


def test_sequence_binding_trace_is_canonical_not_record_order_dependent() -> None:
    first = _binding(local_name="z", anchor_name="chr1")
    second = _binding(local_name="a", anchor_name="chr2")
    result = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(
            VcfRefRecord(_VCF, 0, "z", 1, "A"),
            VcfRefRecord(_VCF, 1, "a", 1, "T"),
        ),
        reference=_Reference({"chr1": "ACGT", "chr2": "TTTT"}),
        sequence_bindings=(first, second),
    )

    assert result.sequence_binding_ids == tuple(sorted((first.id, second.id), key=str))


def test_verified_binding_overrides_same_string_fasta_lookup() -> None:
    binding = _binding(local_name="chr1", anchor_name="chr2")
    result = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "chr1", 1, "T"),),
        reference=_Reference({"chr1": "AAAA", "chr2": "TTTT"}),
        sequence_bindings=(binding,),
    )

    assert result.match_count == 1
    assert result.unresolved_sequence_count == 0
    assert result.sequence_binding_ids == (binding.id,)
