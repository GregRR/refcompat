"""Pure exhaustive GTF/GFF3 coordinate-bounds reasoning.

The evaluator consumes RefCompat-owned annotation observations plus the explicit
FASTA reference context. It resolves names exactly in this slice and never
infers aliases. GFF3 seqids carrying observed circular evidence are held
unresolved when ordinary bounds fail until the dedicated circular semantics
slice can establish whether the standard exception actually applies.
"""

from __future__ import annotations

from collections.abc import Iterable

from refcompat.model.annotation import AnnotationContextSnapshot, AnnotationFeatureRecord
from refcompat.model.annotation_bounds import (
    AnnotationCoordinateCheck,
    AnnotationCoordinateCheckState,
    AnnotationCoordinateSequenceSummary,
    AnnotationCoordinateValidationResult,
)
from refcompat.model.identity import SnapshotSequence
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ResourceKind


class AnnotationCoordinateEvaluationError(Exception):
    """Exhaustive annotation coordinate evaluation cannot produce a valid result."""


def evaluate_annotation_coordinates(
    snapshot: AnnotationContextSnapshot,
    features: Iterable[AnnotationFeatureRecord],
    reference_context: ReferenceContext,
) -> AnnotationCoordinateValidationResult:
    """Exhaustively validate ordinary annotation coordinates against the FASTA anchor.

    This slice uses exact seqid resolution only. A missing exact name remains
    ``UNRESOLVED_SEQUENCE`` rather than proving biological absence. Ordinary
    resolved intervals beyond the selected anchor sequence are hard conflicts.
    GFF3 sequences with any observed ``Is_circular=true`` feature are held
    unresolved when an interval exceeds ordinary bounds; Slice 7 will decide
    whether the standard circular-origin exception is actually established.
    """

    if snapshot.resource_id == reference_context.anchor_resource_id:
        raise ValueError("annotation coordinate subject cannot be the FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("annotation resource must be inside the reference-context scope")

    anchor_by_name = {sequence.local_name: sequence for sequence in reference_context.sequences}
    potential_circular_names: set[str] = (
        {
            usage.sequence_name
            for usage in snapshot.sequence_usage
            if usage.circular_feature_count > 0
        }
        if snapshot.resource_kind is ResourceKind.GFF3
        else set()
    )

    state_counts = {state: 0 for state in AnnotationCoordinateCheckState}
    sequence_counts: dict[str, dict[AnnotationCoordinateCheckState, int]] = {}
    stream_usage: dict[str, list[int]] = {}
    problem_checks: list[AnnotationCoordinateCheck] = []
    retained_problem_keys: set[tuple[str, AnnotationCoordinateCheckState]] = set()
    feature_count = 0

    for expected_ordinal, feature in enumerate(features):
        if feature.resource_id != snapshot.resource_id:
            raise AnnotationCoordinateEvaluationError(
                "annotation feature belongs to a different annotation resource"
            )
        if feature.ordinal != expected_ordinal:
            raise AnnotationCoordinateEvaluationError(
                "annotation features must be exhaustive, contiguous, and zero-based in file order"
            )

        check = _evaluate_feature(
            feature,
            anchor_by_name=anchor_by_name,
            potential_circular_names=potential_circular_names,
        )
        feature_count += 1
        state_counts[check.state] += 1
        by_state = sequence_counts.setdefault(
            feature.sequence_name,
            {state: 0 for state in AnnotationCoordinateCheckState},
        )
        by_state[check.state] += 1
        observed = stream_usage.get(feature.sequence_name)
        if observed is None:
            stream_usage[feature.sequence_name] = [
                1,
                feature.start,
                feature.end,
                1 if feature.is_circular else 0,
            ]
        else:
            observed[0] += 1
            observed[1] = min(observed[1], feature.start)
            observed[2] = max(observed[2], feature.end)
            observed[3] += 1 if feature.is_circular else 0
        if check.state is not AnnotationCoordinateCheckState.REPRESENTABLE:
            problem_key = (feature.sequence_name, check.state)
            if problem_key not in retained_problem_keys:
                retained_problem_keys.add(problem_key)
                problem_checks.append(check)

    if feature_count != snapshot.feature_count:
        raise AnnotationCoordinateEvaluationError(
            "annotation feature stream must match the inspected snapshot feature count"
        )
    expected_usage = {
        usage.sequence_name: [
            usage.feature_count,
            usage.minimum_start,
            usage.maximum_end,
            usage.circular_feature_count,
        ]
        for usage in snapshot.sequence_usage
    }
    if stream_usage != expected_usage:
        raise AnnotationCoordinateEvaluationError(
            "annotation feature stream must match inspected seqid/bounds/circular usage"
        )

    sequence_summaries = tuple(
        AnnotationCoordinateSequenceSummary(
            sequence_name=sequence_name,
            feature_count=sum(counts.values()),
            representable_count=counts[AnnotationCoordinateCheckState.REPRESENTABLE],
            out_of_bounds_count=counts[AnnotationCoordinateCheckState.OUT_OF_BOUNDS],
            unresolved_sequence_count=counts[AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE],
            circular_bounds_unresolved_count=counts[
                AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED
            ],
        )
        for sequence_name, counts in sequence_counts.items()
    )

    return AnnotationCoordinateValidationResult(
        annotation_resource_id=snapshot.resource_id,
        fasta_resource_id=reference_context.anchor_resource_id,
        feature_count=feature_count,
        representable_count=state_counts[AnnotationCoordinateCheckState.REPRESENTABLE],
        out_of_bounds_count=state_counts[AnnotationCoordinateCheckState.OUT_OF_BOUNDS],
        unresolved_sequence_count=state_counts[AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE],
        circular_bounds_unresolved_count=state_counts[
            AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED
        ],
        sequence_summaries=sequence_summaries,
        problem_checks=tuple(problem_checks),
    )


def _evaluate_feature(
    feature: AnnotationFeatureRecord,
    *,
    anchor_by_name: dict[str, SnapshotSequence],
    potential_circular_names: set[str],
) -> AnnotationCoordinateCheck:
    anchor_sequence = anchor_by_name.get(feature.sequence_name)
    if anchor_sequence is None:
        return AnnotationCoordinateCheck(
            feature,
            AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
        )

    # ReferenceContext guarantees selected FASTA sequence lengths are known.
    sequence_name = anchor_sequence.local_name
    sequence_length = anchor_sequence.length
    if sequence_length is None:
        raise AnnotationCoordinateEvaluationError(
            "reference context exposed unknown sequence length"
        )

    if feature.end <= sequence_length:
        state = AnnotationCoordinateCheckState.REPRESENTABLE
    elif feature.sequence_name in potential_circular_names:
        state = AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED
    else:
        state = AnnotationCoordinateCheckState.OUT_OF_BOUNDS

    return AnnotationCoordinateCheck(
        feature,
        state,
        anchor_sequence_name=sequence_name,
        anchor_sequence_length=sequence_length,
    )
