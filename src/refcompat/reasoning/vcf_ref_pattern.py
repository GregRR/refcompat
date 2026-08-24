"""Threshold-free VCF REF conflict-pattern interpretation."""

from __future__ import annotations

from refcompat.model.vcf_ref import VcfRefValidationResult
from refcompat.model.vcf_ref_pattern import (
    VcfRefConflictPattern,
    VcfRefConflictPatternSummary,
)


def classify_vcf_ref_conflicts(
    validation: VcfRefValidationResult,
) -> VcfRefConflictPatternSummary:
    """Classify the distribution of proven REF mismatches without scoring.

    Classification is intentionally conservative. Any unresolved-sequence or
    out-of-bounds record makes the distribution ``UNCLASSIFIED`` because the
    complete mismatch pattern is not observable. Proven mismatches remain hard
    contradictions elsewhere regardless of this descriptive pattern state.

    For complete direct validation, the threshold-free rules are:

    - no mismatch -> ``NONE``;
    - exactly one mismatch -> ``ISOLATED``;
    - multiple mismatches confined to one sequence or a strict subset of the
      directly compared sequence scope -> ``LOCALIZED``;
    - multiple mismatches affecting every sequence in a multi-sequence scope,
      with at least one direct match -> ``DISTRIBUTED``;
    - every directly comparable record mismatches across a multi-sequence scope
      -> ``SYSTEMATIC``.

    ``SYSTEMATIC`` therefore requires exhaustive observed disagreement rather
    than a mismatch-rate threshold or inferred biological cause.
    """

    unresolved_count = validation.out_of_bounds_count + validation.unresolved_sequence_count
    compared_sequence_names = tuple(
        sorted(
            summary.sequence_name
            for summary in validation.sequence_summaries
            if summary.match_count + summary.mismatch_count > 0
        )
    )
    affected_sequence_names = tuple(
        sorted(
            summary.sequence_name
            for summary in validation.sequence_summaries
            if summary.mismatch_count > 0
        )
    )

    if unresolved_count:
        pattern = VcfRefConflictPattern.UNCLASSIFIED
    elif validation.mismatch_count == 0:
        pattern = VcfRefConflictPattern.NONE
    elif validation.mismatch_count == 1:
        pattern = VcfRefConflictPattern.ISOLATED
    elif len(affected_sequence_names) >= 2 and set(affected_sequence_names) == set(
        compared_sequence_names
    ):
        if validation.match_count == 0:
            pattern = VcfRefConflictPattern.SYSTEMATIC
        else:
            pattern = VcfRefConflictPattern.DISTRIBUTED
    else:
        pattern = VcfRefConflictPattern.LOCALIZED

    return VcfRefConflictPatternSummary(
        vcf_resource_id=validation.vcf_resource_id,
        fasta_resource_id=validation.fasta_resource_id,
        pattern=pattern,
        record_count=validation.record_count,
        directly_compared_count=validation.match_count + validation.mismatch_count,
        mismatch_count=validation.mismatch_count,
        unresolved_count=unresolved_count,
        compared_sequence_names=compared_sequence_names,
        affected_sequence_names=affected_sequence_names,
    )
