"""Tests for annotation projection into generic contracts and bundle reasoning."""

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationFeatureRecord,
    AnnotationSequenceUsage,
)
from refcompat.model.annotation_contract import AnnotationContractProjection
from refcompat.model.constraints import ConstraintState
from refcompat.model.contracts import (
    CoordinateBoundsRequirement,
    ResourceContract,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.evidence import EvidenceMethod, EvidenceStrength
from refcompat.model.identity import (
    CollectionCompleteness,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.verdict import CompatibilityVerdict
from refcompat.reasoning import aggregate_bundle_verdict, reason_bundle
from refcompat.reasoning.annotation_bounds import evaluate_annotation_coordinates
from refcompat.reasoning.annotation_contract import (
    build_annotation_contract,
    project_annotation_contract,
)
from refcompat.reasoning.reference_context import build_reference_context

_ANNOTATION = ResourceId("annotation")
_FASTA = ResourceId("fasta")


def _request(
    *sequences: tuple[str, int],
) -> tuple[EvaluationRequest, SequenceCollectionSnapshot, ReferenceContext]:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa"))),
        Resource(_ANNOTATION, ResourceKind.GTF, ArtifactIdentity(Path("genes.gtf"))),
    )
    request = EvaluationRequest(resources, _FASTA, EvaluationScope((_FASTA, _ANNOTATION)))
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=tuple(
            SnapshotSequence(name, length, ordinal)
            for ordinal, (name, length) in enumerate(sequences)
        ),
    )
    return request, anchor, build_reference_context(request, anchor)


def _feature(ordinal: int, name: str, start: int, end: int) -> AnnotationFeatureRecord:
    return AnnotationFeatureRecord(
        _ANNOTATION,
        ordinal,
        ordinal + 1,
        name,
        name,
        "gene",
        start,
        end,
    )


def _snapshot(*usage: tuple[str, int, int, int]) -> AnnotationContextSnapshot:
    return AnnotationContextSnapshot(
        _ANNOTATION,
        ResourceKind.GTF,
        feature_count=sum(item[1] for item in usage),
        sequence_usage=tuple(
            AnnotationSequenceUsage(
                sequence_name=name,
                first_raw_sequence_name=name,
                feature_count=count,
                minimum_start=minimum_start,
                maximum_end=maximum_end,
                first_feature_line=index + 1,
            )
            for index, (name, count, minimum_start, maximum_end) in enumerate(usage)
        ),
    )


def _project(
    snapshot: AnnotationContextSnapshot,
    features: tuple[AnnotationFeatureRecord, ...],
    *anchor_sequences: tuple[str, int],
) -> AnnotationContractProjection:
    _request_value, _anchor, context = _request(*anchor_sequences)
    validation = evaluate_annotation_coordinates(snapshot, features, context)
    return project_annotation_contract(snapshot, validation, context)


def test_contract_projects_used_seqids_and_one_coordinate_requirement() -> None:
    _request_value, _anchor, context = _request(("chr1", 100), ("chr2", 100))
    contract = build_annotation_contract(
        _snapshot(("chr1", 2, 1, 20), ("chr2", 1, 5, 5)),
        context,
    )

    presence = tuple(
        item for item in contract.requirements if isinstance(item, SequencePresenceRequirement)
    )
    bounds = tuple(
        item for item in contract.requirements if isinstance(item, CoordinateBoundsRequirement)
    )
    assert tuple(item.sequence_name for item in presence) == ("chr1", "chr2")
    assert len(bounds) == 1
    assert bounds[0].anchor_resource_id == _FASTA
    assert bounds[0].coordinate_count == 3


def test_exact_in_bounds_projection_is_structurally_satisfied() -> None:
    projection = _project(
        _snapshot(("chr1", 2, 1, 100)),
        (_feature(0, "chr1", 1, 20), _feature(1, "chr1", 100, 100)),
        ("chr1", 100),
    )

    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )
    evidence = projection.evidence.evidence[-1]
    assert evidence.method is EvidenceMethod.EXHAUSTIVE_COORDINATE_BOUNDS_VALIDATION
    assert evidence.strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL


def test_sparse_annotation_accepts_fasta_superset() -> None:
    request, anchor, context = _request(("chr1", 100), ("chr2", 100), ("decoy", 50))
    snapshot = _snapshot(("chr1", 1, 1, 10))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "chr1", 1, 10),), context)
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.COMPATIBLE
    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )


def test_unfamiliar_seqid_remains_indeterminate_not_proven_absent() -> None:
    request, anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(("1", 1, 1, 10))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "1", 1, 10),), context)
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.INDETERMINATE
    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
    assert bundle.evidence.evidence == ()


def test_one_ordinary_out_of_bounds_feature_makes_bundle_incompatible() -> None:
    request, anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(("chr1", 2, 1, 101))
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 100), _feature(1, "chr1", 101, 101)),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert bundle.evaluations[-1].state is ConstraintState.UNSATISFIED
    assert bundle.evidence.conclusive_contradictions == ()
    assert (
        bundle.evidence.contradicting_evidence[0].strength
        is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    )


def test_empty_annotation_has_only_not_applicable_coordinate_requirement() -> None:
    projection = _project(_snapshot(), (), ("chr1", 100))

    assert len(projection.contract.requirements) == 1
    assert isinstance(projection.contract.requirements[0], CoordinateBoundsRequirement)
    assert projection.evaluations[0].state is ConstraintState.NOT_APPLICABLE


def test_projection_rejects_crosswired_validation_and_coverage() -> None:
    snapshot = _snapshot(("chr1", 1, 1, 10))
    _request_value, _anchor, context = _request(("chr1", 100), ("chr2", 100))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "chr1", 1, 10),), context)

    with pytest.raises(ValueError, match="same resource"):
        project_annotation_contract(
            snapshot,
            replace(validation, annotation_resource_id=ResourceId("other")),
            context,
        )
    with pytest.raises(ValueError, match="FASTA anchor"):
        project_annotation_contract(
            snapshot,
            replace(validation, fasta_resource_id=ResourceId("other")),
            context,
        )

    bad_summary = replace(validation.sequence_summaries[0], sequence_name="chr2")
    with pytest.raises(ValueError, match="seqid usage"):
        project_annotation_contract(
            snapshot,
            replace(validation, sequence_summaries=(bad_summary,)),
            context,
        )


def test_projection_ids_are_deterministic() -> None:
    snapshot = _snapshot(("chr1", 1, 1, 10))
    _request_value, _anchor, context = _request(("chr1", 100))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "chr1", 1, 10),), context)

    first = project_annotation_contract(snapshot, validation, context)
    second = project_annotation_contract(snapshot, validation, context)

    assert tuple(item.id for item in first.contract.requirements) == tuple(
        item.id for item in second.contract.requirements
    )
    assert first.coordinate_bounds_capability.id == second.coordinate_bounds_capability.id
    assert tuple(item.id for item in first.constraints) == tuple(
        item.id for item in second.constraints
    )
