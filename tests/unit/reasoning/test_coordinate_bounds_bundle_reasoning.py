"""Whole-bundle orchestration for pair-derived coordinate-bounds capabilities."""

from pathlib import Path

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CapabilityId,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConflictCoreKind,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    EvaluationRequest,
    EvaluationScope,
    EvidenceKind,
    EvidenceMethod,
    EvidenceStrength,
    FindingKind,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.reasoning import aggregate_bundle_verdict, extract_conflict_cores, reason_bundle

_REFERENCE = ResourceId("reference")
_ANNOTATION = ResourceId("annotation")
_ORIGIN = RequirementOrigin.CORE_FORMAT
_LEVEL = RequirementLevel.MANDATORY


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_ANNOTATION, ResourceKind.GFF3),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope((_REFERENCE, _ANNOTATION)),
    )


def _snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 100, 0),),
    )


def _contract(coordinate_count: int) -> ResourceContract:
    return ResourceContract(
        _ANNOTATION,
        requirements=(
            CoordinateBoundsRequirement(
                RequirementId("coordinate-bounds"),
                _ANNOTATION,
                _REFERENCE,
                _ORIGIN,
                _LEVEL,
                coordinate_count,
            ),
        ),
    )


def _capability(
    *,
    checked: int,
    representable: int,
    conflicts: int = 0,
    unresolved: int = 0,
) -> CoordinateBoundsValidationCapability:
    return CoordinateBoundsValidationCapability(
        CapabilityId("direct-coordinates"),
        _REFERENCE,
        _ANNOTATION,
        checked,
        representable,
        conflicts,
        unresolved,
    )


def _bundle(capability: CoordinateBoundsValidationCapability) -> BundleReasoningResult:
    return reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), _contract(capability.checked_count)),
        supplemental_capabilities=(capability,),
    )


def test_all_representable_coordinate_validation_reaches_compatible_verdict() -> None:
    bundle = _bundle(_capability(checked=100, representable=100))
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.COMPATIBLE
    assert bundle.interpretation.findings == ()

    evidence = bundle.evidence.evidence[0]
    assert evidence.kind is EvidenceKind.COORDINATE_BOUNDS
    assert evidence.method is EvidenceMethod.EXHAUSTIVE_COORDINATE_BOUNDS_VALIDATION
    assert evidence.strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL


def test_coordinate_conflict_reaches_incompatible_verdict_and_core() -> None:
    bundle = _bundle(_capability(checked=1_000_000, representable=999_999, conflicts=1))
    verdict = aggregate_bundle_verdict(bundle)
    cores = extract_conflict_cores(bundle, verdict)

    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert bundle.interpretation.findings[0].kind is FindingKind.COORDINATE_BOUNDS_CONFLICT
    assert bundle.evidence.conclusive_contradictions == ()
    assert len(cores.cores) == 1
    assert cores.cores[0].kind is ConflictCoreKind.CONTRADICTION
    assert cores.cores[0].resource_ids == (_ANNOTATION, _REFERENCE)
    assert cores.cores[0].evidence_ids == (bundle.evidence.evidence[0].id,)


def test_incomplete_coordinate_validation_reaches_indeterminate_verdict() -> None:
    bundle = _bundle(_capability(checked=100, representable=99, unresolved=1))
    verdict = aggregate_bundle_verdict(bundle)
    cores = extract_conflict_cores(bundle, verdict)

    assert verdict.verdict is CompatibilityVerdict.INDETERMINATE
    assert bundle.evidence.evidence == ()
    assert bundle.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT
    assert len(cores.cores) == 1
    assert cores.cores[0].kind is ConflictCoreKind.UNRESOLVED
    assert cores.cores[0].evidence_ids == ()
    assert cores.cores[0].resource_ids == (_ANNOTATION,)
