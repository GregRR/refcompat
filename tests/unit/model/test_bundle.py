"""Model invariants for whole-bundle supplemental capabilities."""

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CapabilityId,
    CollectionCompleteness,
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
from refcompat.reasoning import reason_bundle

_REFERENCE = ResourceId("reference")
_VCF = ResourceId("variants")


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _bundle() -> BundleReasoningResult:
    request = EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_VCF, ResourceKind.VCF),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope((_REFERENCE, _VCF)),
    )
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 100, 0),),
    )
    contract = ResourceContract(
        _VCF,
        requirements=(
            ReferenceBaseRequirement(
                RequirementId("reference-bases"),
                _VCF,
                _REFERENCE,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                1,
            ),
        ),
    )
    capability = ReferenceBaseValidationCapability(
        CapabilityId("direct-ref"),
        _REFERENCE,
        _VCF,
        1,
        1,
        0,
        0,
    )
    return reason_bundle(
        request,
        snapshot,
        (ResourceContract(_REFERENCE), contract),
        supplemental_capabilities=(capability,),
    )


def test_bundle_rejects_constraint_candidate_missing_from_declared_sources() -> None:
    bundle = _bundle()
    with pytest.raises(ValueError, match="only anchor or supplemental capabilities"):
        replace(bundle, supplemental_capabilities=())


def test_bundle_rejects_unused_supplemental_capability() -> None:
    bundle = _bundle()
    extra = replace(bundle.supplemental_capabilities[0], id=CapabilityId("extra"))
    with pytest.raises(ValueError, match="must be used by a constraint"):
        replace(bundle, supplemental_capabilities=(*bundle.supplemental_capabilities, extra))


def test_bundle_model_rejects_duplicate_supplemental_capability_ids() -> None:
    bundle = _bundle()
    duplicate = replace(bundle.supplemental_capabilities[0])
    with pytest.raises(ValueError, match="IDs must be unique"):
        replace(bundle, supplemental_capabilities=(*bundle.supplemental_capabilities, duplicate))


def test_bundle_rejects_supplemental_capability_id_colliding_with_anchor_capability() -> None:
    bundle = _bundle()
    anchor_id = bundle.reference_context.anchor_capabilities[0].id
    collided = replace(bundle.supplemental_capabilities[0], id=anchor_id)
    constraint = replace(bundle.constraints[0], candidate_capabilities=(collided,))
    evaluation = replace(
        bundle.evaluations[0],
        relevant_capability_ids=(anchor_id,),
    )
    with pytest.raises(ValueError, match="must not overlap"):
        replace(
            bundle,
            constraints=(constraint,),
            evaluations=(evaluation,),
            supplemental_capabilities=(collided,),
        )
