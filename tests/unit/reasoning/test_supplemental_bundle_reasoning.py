"""Whole-bundle orchestration for pair-derived reference-base capabilities."""

from pathlib import Path

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CapabilityId,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConflictCoreKind,
    EvaluationRequest,
    EvaluationScope,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
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
_VCF = ResourceId("variants")
_ORIGIN = RequirementOrigin.CORE_FORMAT
_LEVEL = RequirementLevel.MANDATORY


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_VCF, ResourceKind.VCF),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope((_REFERENCE, _VCF)),
    )


def _snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 100, 0),),
    )


def _contract(record_count: int) -> ResourceContract:
    return ResourceContract(
        _VCF,
        requirements=(
            ReferenceBaseRequirement(
                RequirementId("reference-bases"),
                _VCF,
                _REFERENCE,
                _ORIGIN,
                _LEVEL,
                record_count,
            ),
        ),
    )


def _capability(
    *,
    checked: int,
    matches: int,
    mismatches: int = 0,
    unresolved: int = 0,
) -> ReferenceBaseValidationCapability:
    return ReferenceBaseValidationCapability(
        CapabilityId("direct-ref"),
        _REFERENCE,
        _VCF,
        checked,
        matches,
        mismatches,
        unresolved,
    )


def _bundle(capability: ReferenceBaseValidationCapability) -> BundleReasoningResult:
    return reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), _contract(capability.checked_count)),
        supplemental_capabilities=(capability,),
    )


def test_all_match_supplemental_validation_reaches_compatible_verdict() -> None:
    bundle = _bundle(_capability(checked=100, matches=100))
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.COMPATIBLE
    assert verdict.satisfied_mandatory_constraint_ids == (bundle.constraints[0].id,)


def test_mismatch_supplemental_validation_reaches_incompatible_verdict_and_core() -> None:
    bundle = _bundle(_capability(checked=1_000_000, matches=999_999, mismatches=1))
    verdict = aggregate_bundle_verdict(bundle)
    cores = extract_conflict_cores(bundle, verdict)

    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert len(cores.cores) == 1
    assert cores.cores[0].kind is ConflictCoreKind.CONTRADICTION
    assert cores.cores[0].resource_ids == (_VCF, _REFERENCE)
    assert cores.cores[0].evidence_ids == (bundle.evidence.conclusive_contradictions[0].id,)


def test_incomplete_supplemental_validation_reaches_indeterminate_verdict() -> None:
    bundle = _bundle(_capability(checked=100, matches=99, unresolved=1))
    verdict = aggregate_bundle_verdict(bundle)
    cores = extract_conflict_cores(bundle, verdict)

    assert verdict.verdict is CompatibilityVerdict.INDETERMINATE
    assert bundle.evidence.evidence == ()
    assert len(cores.cores) == 1
    assert cores.cores[0].kind is ConflictCoreKind.UNRESOLVED
    assert cores.cores[0].evidence_ids == ()
    assert cores.cores[0].resource_ids == (_VCF,)
