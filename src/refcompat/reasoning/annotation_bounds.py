"""Pure exhaustive GTF/GFF3 coordinate-bounds reasoning.

The evaluator consumes RefCompat-owned annotation observations plus the explicit
FASTA reference context. It resolves seqids by exact name or explicit verified
sequence binding and never infers aliases. GFF3 circular-origin coordinates use
the standard landmark relationship only when ``Is_circular=true`` is carried by
a feature whose decoded ``ID`` exactly equals the logical column-1 seqid; other
circular-feature observations do not weaken ordinary bounds checks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationFeatureRecord,
    Gff3SequenceRegion,
)
from refcompat.model.annotation_bounds import (
    AnnotationCoordinateCheck,
    AnnotationCoordinateCheckState,
    AnnotationCoordinateSequenceSummary,
    AnnotationCoordinateValidationResult,
    Gff3SequenceRegionCheck,
    Gff3SequenceRegionCheckState,
    Gff3SequenceRegionValidationResult,
)
from refcompat.model.identity import SnapshotSequence
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.model.resources import ResourceKind


class AnnotationCoordinateEvaluationError(Exception):
    """Exhaustive annotation coordinate evaluation cannot produce a valid result."""


@dataclass(frozen=True, slots=True)
class _CircularLandmarkEvidence:
    """Bounded circular-landmark interpretation for one logical GFF3 seqid."""

    candidate_count: int
    landmark_length: int | None
    landmark_line: int | None
    established_against_anchor: bool
    embedded_length_mismatch: bool


def evaluate_annotation_coordinates(
    snapshot: AnnotationContextSnapshot,
    features: Iterable[AnnotationFeatureRecord],
    reference_context: ReferenceContext,
    sequence_bindings: tuple[SequenceBinding, ...] = (),
) -> AnnotationCoordinateValidationResult:
    """Exhaustively validate annotation coordinates against the FASTA anchor.

    Seqids resolve by exact name or explicit verified sequence binding. Names
    with neither remain unresolved rather than proving biological absence.
    Ordinary resolved feature intervals and GFF3 ``##sequence-region``
    declarations beyond the selected anchor are hard structural conflicts.

    The GFF3 circular-origin exception is recognized only when ``Is_circular``
    is carried by a feature whose decoded ``ID`` exactly equals the logical
    column-1 seqid, establishing a landmark candidate rather than merely an
    arbitrary circular child feature. A unique candidate beginning at position
    one supplies the landmark length used by the standard wrap encoding. It is
    accepted against the anchor only when that length equals the resolved FASTA
    sequence length; otherwise a syntactically plausible wrap remains
    unresolved.
    """

    if snapshot.resource_id == reference_context.anchor_resource_id:
        raise ValueError("annotation coordinate subject cannot be the FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("annotation resource must be inside the reference-context scope")

    anchor_by_name = {sequence.local_name: sequence for sequence in reference_context.sequences}
    bindings_by_name = _binding_map(snapshot, reference_context, sequence_bindings)
    region_by_name = {region.sequence_name: region for region in snapshot.sequence_regions}
    if len(region_by_name) != len(snapshot.sequence_regions):
        raise AnnotationCoordinateEvaluationError(
            "GFF3 sequence-region declarations must have unique logical seqids"
        )
    embedded_length_by_name = {
        sequence.sequence_name: sequence.length for sequence in snapshot.embedded_fasta_sequences
    }
    if len(embedded_length_by_name) != len(snapshot.embedded_fasta_sequences):
        raise AnnotationCoordinateEvaluationError(
            "embedded GFF3 FASTA sequences must have unique identifiers"
        )
    for region in snapshot.sequence_regions:
        embedded_length = embedded_length_by_name.get(region.sequence_name)
        if embedded_length is not None and region.end > embedded_length:
            raise AnnotationCoordinateEvaluationError(
                "GFF3 sequence-region exceeds its matching embedded FASTA sequence: "
                f"sequence-region line {region.line_number}"
            )

    circular_landmarks = _build_circular_landmark_evidence(
        snapshot,
        anchor_by_name=anchor_by_name,
        bindings_by_name=bindings_by_name,
        embedded_length_by_name=embedded_length_by_name,
    )
    region_validation = _evaluate_sequence_regions(
        snapshot,
        anchor_by_name=anchor_by_name,
        bindings_by_name=bindings_by_name,
        reference_context=reference_context,
    )

    state_counts = {state: 0 for state in AnnotationCoordinateCheckState}
    sequence_counts: dict[str, dict[AnnotationCoordinateCheckState, int]] = {}
    stream_usage: dict[str, list[int]] = {}
    stream_landmark_first: dict[str, tuple[int, int, int]] = {}
    problem_checks: list[AnnotationCoordinateCheck] = []
    retained_problem_keys: set[tuple[str, AnnotationCoordinateCheckState]] = set()
    region_violation: tuple[AnnotationFeatureRecord, Gff3SequenceRegion] | None = None
    embedded_violation: AnnotationFeatureRecord | None = None
    circular_encoding_violation: AnnotationFeatureRecord | None = None
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

        landmark = circular_landmarks.get(feature.sequence_name)
        declared_region = region_by_name.get(feature.sequence_name)
        outside_declared_region = declared_region is not None and not _contained_in_region(
            feature,
            declared_region,
        )
        embedded_length = embedded_length_by_name.get(feature.sequence_name)
        outside_embedded_sequence = embedded_length is not None and feature.end > embedded_length

        requires_internal_exception = outside_declared_region or outside_embedded_sequence
        circular_state = _circular_wrap_state(
            feature,
            landmark,
            requires_exception=requires_internal_exception,
        )
        if circular_state == _CircularWrapState.INVALID and circular_encoding_violation is None:
            circular_encoding_violation = feature

        circular_exception_possible = circular_state in (
            _CircularWrapState.REPRESENTABLE,
            _CircularWrapState.UNRESOLVED,
        )
        if outside_declared_region and not circular_exception_possible and region_violation is None:
            assert declared_region is not None
            region_violation = (feature, declared_region)
        if (
            outside_embedded_sequence
            and not circular_exception_possible
            and embedded_violation is None
        ):
            embedded_violation = feature

        check = _evaluate_feature(
            feature,
            anchor_by_name=anchor_by_name,
            bindings_by_name=bindings_by_name,
            circular_landmark=landmark,
            circular_state=circular_state,
        )
        feature_count += 1
        state_counts[check.state] += 1
        by_state = sequence_counts.setdefault(
            feature.sequence_name,
            {state: 0 for state in AnnotationCoordinateCheckState},
        )
        by_state[check.state] += 1

        is_landmark_candidate = feature.is_circular and feature.feature_id == feature.sequence_name
        observed = stream_usage.get(feature.sequence_name)
        if observed is None:
            stream_usage[feature.sequence_name] = [
                1,
                feature.start,
                feature.end,
                1 if feature.is_circular else 0,
                1 if is_landmark_candidate else 0,
            ]
        else:
            observed[0] += 1
            observed[1] = min(observed[1], feature.start)
            observed[2] = max(observed[2], feature.end)
            observed[3] += 1 if feature.is_circular else 0
            observed[4] += 1 if is_landmark_candidate else 0
        if is_landmark_candidate and feature.sequence_name not in stream_landmark_first:
            stream_landmark_first[feature.sequence_name] = (
                feature.start,
                feature.end,
                feature.line_number,
            )

        if check.state not in (
            AnnotationCoordinateCheckState.REPRESENTABLE,
            AnnotationCoordinateCheckState.CIRCULAR_REPRESENTABLE,
        ):
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
            usage.circular_landmark_candidate_count,
        ]
        for usage in snapshot.sequence_usage
    }
    expected_landmark_first = {
        usage.sequence_name: (
            usage.first_circular_landmark_start,
            usage.first_circular_landmark_end,
            usage.first_circular_landmark_line,
        )
        for usage in snapshot.sequence_usage
        if usage.circular_landmark_candidate_count > 0
    }
    if stream_usage != expected_usage or stream_landmark_first != expected_landmark_first:
        raise AnnotationCoordinateEvaluationError(
            "annotation feature stream must match inspected seqid/bounds/circular usage "
            "and landmark evidence"
        )
    embedded_landmark_mismatch = next(
        (landmark for landmark in circular_landmarks.values() if landmark.embedded_length_mismatch),
        None,
    )
    if embedded_landmark_mismatch is not None:
        raise AnnotationCoordinateEvaluationError(
            "GFF3 circular landmark length disagrees with its matching embedded FASTA "
            f"sequence: feature line {embedded_landmark_mismatch.landmark_line}"
        )
    if circular_encoding_violation is not None:
        raise AnnotationCoordinateEvaluationError(
            "GFF3 circular-origin feature exceeds the standard single-wrap representation: "
            f"feature line {circular_encoding_violation.line_number}"
        )
    if region_violation is not None:
        feature, declared_region = region_violation
        raise AnnotationCoordinateEvaluationError(
            "GFF3 feature lies outside its declared sequence-region without valid circular "
            f"landmark wrapping: feature line {feature.line_number}, "
            f"sequence-region line {declared_region.line_number}"
        )
    if embedded_violation is not None:
        raise AnnotationCoordinateEvaluationError(
            "GFF3 feature lies outside its matching embedded FASTA sequence without valid "
            f"circular landmark wrapping: feature line {embedded_violation.line_number}"
        )

    sequence_summaries = tuple(
        AnnotationCoordinateSequenceSummary(
            sequence_name=sequence_name,
            feature_count=sum(counts.values()),
            representable_count=counts[AnnotationCoordinateCheckState.REPRESENTABLE],
            circular_representable_count=counts[
                AnnotationCoordinateCheckState.CIRCULAR_REPRESENTABLE
            ],
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
        circular_representable_count=state_counts[
            AnnotationCoordinateCheckState.CIRCULAR_REPRESENTABLE
        ],
        out_of_bounds_count=state_counts[AnnotationCoordinateCheckState.OUT_OF_BOUNDS],
        unresolved_sequence_count=state_counts[AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE],
        circular_bounds_unresolved_count=state_counts[
            AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED
        ],
        sequence_summaries=sequence_summaries,
        problem_checks=tuple(problem_checks),
        sequence_region_validation=region_validation,
        sequence_binding_ids=tuple(sorted((binding.id for binding in sequence_bindings), key=str)),
    )


class _CircularWrapState:
    REPRESENTABLE = "representable"
    UNRESOLVED = "unresolved"
    INVALID = "invalid"


def _build_circular_landmark_evidence(
    snapshot: AnnotationContextSnapshot,
    *,
    anchor_by_name: dict[str, SnapshotSequence],
    bindings_by_name: dict[str, SequenceBinding],
    embedded_length_by_name: dict[str, int],
) -> dict[str, _CircularLandmarkEvidence]:
    if snapshot.resource_kind is not ResourceKind.GFF3:
        return {}

    evidence: dict[str, _CircularLandmarkEvidence] = {}
    for usage in snapshot.sequence_usage:
        if usage.circular_landmark_candidate_count == 0:
            continue
        landmark_length: int | None = None
        landmark_line = usage.first_circular_landmark_line
        embedded_length_mismatch = False
        if (
            usage.circular_landmark_candidate_count == 1
            and usage.first_circular_landmark_start == 1
            and usage.first_circular_landmark_end is not None
        ):
            landmark_length = usage.first_circular_landmark_end
            embedded_length = embedded_length_by_name.get(usage.sequence_name)
            embedded_length_mismatch = (
                embedded_length is not None and embedded_length != landmark_length
            )

        anchor_sequence = _resolved_anchor_sequence(
            usage.sequence_name,
            anchor_by_name=anchor_by_name,
            bindings_by_name=bindings_by_name,
        )
        anchor_length = anchor_sequence.length if anchor_sequence is not None else None
        established = (
            landmark_length is not None
            and not embedded_length_mismatch
            and anchor_length is not None
            and anchor_length == landmark_length
        )
        evidence[usage.sequence_name] = _CircularLandmarkEvidence(
            candidate_count=usage.circular_landmark_candidate_count,
            landmark_length=landmark_length,
            landmark_line=landmark_line,
            established_against_anchor=established,
            embedded_length_mismatch=embedded_length_mismatch,
        )
    return evidence


def _circular_wrap_state(
    feature: AnnotationFeatureRecord,
    landmark: _CircularLandmarkEvidence | None,
    *,
    requires_exception: bool,
) -> str | None:
    if landmark is None:
        return None
    if landmark.landmark_length is None:
        return _CircularWrapState.UNRESOLVED if requires_exception else None

    landmark_length = landmark.landmark_length
    if feature.end <= landmark_length:
        return None
    wrapped_end = feature.end - landmark_length
    if (
        feature.start > landmark_length
        or wrapped_end > landmark_length
        or wrapped_end >= feature.start
    ):
        return _CircularWrapState.INVALID
    return (
        _CircularWrapState.REPRESENTABLE
        if landmark.established_against_anchor
        else _CircularWrapState.UNRESOLVED
    )


def _evaluate_sequence_regions(
    snapshot: AnnotationContextSnapshot,
    *,
    anchor_by_name: dict[str, SnapshotSequence],
    bindings_by_name: dict[str, SequenceBinding],
    reference_context: ReferenceContext,
) -> Gff3SequenceRegionValidationResult | None:
    if snapshot.resource_kind is not ResourceKind.GFF3:
        if snapshot.sequence_regions:
            raise AnnotationCoordinateEvaluationError(
                "non-GFF3 annotation cannot carry sequence-region declarations"
            )
        return None

    checks = tuple(
        _evaluate_sequence_region(
            region,
            anchor_by_name=anchor_by_name,
            bindings_by_name=bindings_by_name,
        )
        for region in snapshot.sequence_regions
    )
    return Gff3SequenceRegionValidationResult(
        annotation_resource_id=snapshot.resource_id,
        fasta_resource_id=reference_context.anchor_resource_id,
        region_count=len(checks),
        representable_count=sum(
            check.state is Gff3SequenceRegionCheckState.REPRESENTABLE for check in checks
        ),
        out_of_bounds_count=sum(
            check.state is Gff3SequenceRegionCheckState.OUT_OF_BOUNDS for check in checks
        ),
        unresolved_sequence_count=sum(
            check.state is Gff3SequenceRegionCheckState.UNRESOLVED_SEQUENCE for check in checks
        ),
        checks=checks,
    )


def _evaluate_sequence_region(
    region: Gff3SequenceRegion,
    *,
    anchor_by_name: dict[str, SnapshotSequence],
    bindings_by_name: dict[str, SequenceBinding],
) -> Gff3SequenceRegionCheck:
    anchor_sequence = _resolved_anchor_sequence(
        region.sequence_name,
        anchor_by_name=anchor_by_name,
        bindings_by_name=bindings_by_name,
    )
    if anchor_sequence is None:
        return Gff3SequenceRegionCheck(
            region,
            Gff3SequenceRegionCheckState.UNRESOLVED_SEQUENCE,
        )

    sequence_length = anchor_sequence.length
    if sequence_length is None:
        raise AnnotationCoordinateEvaluationError(
            "reference context exposed unknown sequence length"
        )
    state = (
        Gff3SequenceRegionCheckState.REPRESENTABLE
        if region.end <= sequence_length
        else Gff3SequenceRegionCheckState.OUT_OF_BOUNDS
    )
    return Gff3SequenceRegionCheck(
        region,
        state,
        anchor_sequence_name=anchor_sequence.local_name,
        anchor_sequence_length=sequence_length,
    )


def _contained_in_region(
    feature: AnnotationFeatureRecord,
    region: Gff3SequenceRegion,
) -> bool:
    return region.start <= feature.start and feature.end <= region.end


def _evaluate_feature(
    feature: AnnotationFeatureRecord,
    *,
    anchor_by_name: dict[str, SnapshotSequence],
    bindings_by_name: dict[str, SequenceBinding],
    circular_landmark: _CircularLandmarkEvidence | None,
    circular_state: str | None,
) -> AnnotationCoordinateCheck:
    anchor_sequence = _resolved_anchor_sequence(
        feature.sequence_name,
        anchor_by_name=anchor_by_name,
        bindings_by_name=bindings_by_name,
    )
    if anchor_sequence is None:
        return AnnotationCoordinateCheck(
            feature,
            AnnotationCoordinateCheckState.UNRESOLVED_SEQUENCE,
        )

    sequence_name = anchor_sequence.local_name
    sequence_length = anchor_sequence.length
    if sequence_length is None:
        raise AnnotationCoordinateEvaluationError(
            "reference context exposed unknown sequence length"
        )

    if circular_state == _CircularWrapState.REPRESENTABLE:
        state = AnnotationCoordinateCheckState.CIRCULAR_REPRESENTABLE
    elif (
        circular_state == _CircularWrapState.UNRESOLVED
        or circular_state == _CircularWrapState.INVALID
    ):
        state = AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED
    elif feature.end <= sequence_length:
        state = AnnotationCoordinateCheckState.REPRESENTABLE
    elif circular_landmark is not None and circular_landmark.landmark_length is None:
        state = AnnotationCoordinateCheckState.CIRCULAR_BOUNDS_UNRESOLVED
    else:
        state = AnnotationCoordinateCheckState.OUT_OF_BOUNDS

    return AnnotationCoordinateCheck(
        feature,
        state,
        anchor_sequence_name=sequence_name,
        anchor_sequence_length=sequence_length,
    )


def _binding_map(
    snapshot: AnnotationContextSnapshot,
    reference_context: ReferenceContext,
    sequence_bindings: tuple[SequenceBinding, ...],
) -> dict[str, SequenceBinding]:
    relevant_names = set(snapshot.used_sequence_names) | {
        region.sequence_name for region in snapshot.sequence_regions
    }
    bindings_by_name: dict[str, SequenceBinding] = {}
    scoped_anchor_names = {sequence.local_name for sequence in reference_context.sequences}
    seen_ids = set()
    for binding in sequence_bindings:
        if binding.id in seen_ids:
            raise ValueError("annotation sequence binding IDs must be unique")
        seen_ids.add(binding.id)
        if binding.resource_id != snapshot.resource_id:
            raise ValueError("annotation sequence binding must belong to the annotation")
        if binding.anchor_resource_id != reference_context.anchor_resource_id:
            raise ValueError("annotation sequence binding must target the selected FASTA anchor")
        if binding.local_sequence_name not in relevant_names:
            raise ValueError("annotation sequence binding local name must be reference-relevant")
        if binding.anchor_sequence_name not in scoped_anchor_names:
            raise ValueError("annotation sequence binding target must be inside anchor scope")
        if binding.local_sequence_name in bindings_by_name:
            raise ValueError("annotation sequence bindings must be unique per local seqid")
        bindings_by_name[binding.local_sequence_name] = binding
    return bindings_by_name


def _resolved_anchor_sequence(
    local_sequence_name: str,
    *,
    anchor_by_name: dict[str, SnapshotSequence],
    bindings_by_name: dict[str, SequenceBinding],
) -> SnapshotSequence | None:
    binding = bindings_by_name.get(local_sequence_name)
    target_name = binding.anchor_sequence_name if binding is not None else local_sequence_name
    return anchor_by_name.get(target_name)
