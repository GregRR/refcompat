"""Network-independent UCSC provider-snapshot and unavailable-evidence behavior."""

from pathlib import Path

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceIdentityRequirement,
    SequencePresenceRequirement,
    SnapshotSequence,
)
from refcompat.profiles import (
    UCSC_PREFLIGHT_PROFILE_ID,
    UcscDatabaseId,
    UcscNameResolutionReason,
    UcscPreflightProjection,
    UcscPreflightTarget,
    UcscProviderSnapshot,
    load_ucsc_provider_snapshot,
    parse_ucsc_provider_snapshot,
    project_ucsc_preflight,
)
from refcompat.reasoning import aggregate_bundle_verdict, build_reference_context, reason_bundle

_FASTA = ResourceId("reference")
_PEER = ResourceId("peer")
_DB = UcscDatabaseId("testDb")
_REFGET = RefgetSequenceId("SQ." + "A" * 32)
_OTHER_REFGET = RefgetSequenceId("SQ." + "B" * 32)
_FIXTURE = Path("tests/fixtures/milestone6/ucsc-provider-snapshot.json")


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
            Resource(_PEER, ResourceKind.VCF, ArtifactIdentity(path=Path("peer.vcf"))),
        ),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
        active_profiles=(UCSC_PREFLIGHT_PROFILE_ID,),
    )


def _anchor() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, _REFGET),),
    )


def _peer_contract(local_name: str = "1") -> ResourceContract:
    return ResourceContract(
        _PEER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId(f"presence:{local_name}"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                local_name,
            ),
        ),
    )


def _reason(
    provider_snapshot: UcscProviderSnapshot | None,
) -> tuple[UcscPreflightProjection, BundleReasoningResult]:
    request = _request()
    anchor = _anchor()
    context = build_reference_context(request, anchor)
    projection = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        provider_snapshot,
        context,
        (ResourceContract(_FASTA), _peer_contract()),
    )
    bundle = reason_bundle(
        request,
        anchor,
        projection.contracts,
        supplemental_capabilities=projection.binding_capabilities,
        supplemental_sequence_bindings=projection.supplemental_sequence_bindings,
    )
    return projection, bundle


def test_fixed_snapshot_has_same_projection_from_memory_or_offline_file() -> None:
    offline = load_ucsc_provider_snapshot(_FIXTURE)
    materialized = parse_ucsc_provider_snapshot(_FIXTURE.read_text(encoding="utf-8"))

    offline_projection, offline_bundle = _reason(offline)
    materialized_projection, materialized_bundle = _reason(materialized)

    assert offline == materialized
    assert offline_projection == materialized_projection
    assert offline_bundle == materialized_bundle
    assert aggregate_bundle_verdict(offline_bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_unavailable_provider_snapshot_yields_unresolved_profile_requirement() -> None:
    projection, bundle = _reason(None)

    trace = projection.sequence_projections[0]
    assert projection.provider_snapshot is None
    assert projection.binding_capabilities == ()
    assert projection.supplemental_sequence_bindings == ()
    assert trace.name_resolution.reason is UcscNameResolutionReason.PROVIDER_EVIDENCE_UNAVAILABLE
    assert trace.target_resolution is None
    assert trace.sequence_binding is None
    profile_evaluations = tuple(
        evaluation
        for constraint, evaluation in zip(bundle.constraints, bundle.evaluations, strict=True)
        if constraint.requirement.id == trace.requirement.id
    )
    assert len(profile_evaluations) == 1
    assert profile_evaluations[0].state is ConstraintState.UNRESOLVED
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INDETERMINATE


def test_unavailable_provider_does_not_mask_independent_core_conflict() -> None:
    request = _request()
    anchor = _anchor()
    context = build_reference_context(request, anchor)
    peer = ResourceContract(
        _PEER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId("presence:chr1"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                "chr1",
            ),
            SequenceIdentityRequirement(
                RequirementId("identity:chr1"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                "chr1",
                _OTHER_REFGET,
            ),
        ),
    )
    projection = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        None,
        context,
        (ResourceContract(_FASTA), peer),
    )
    bundle = reason_bundle(
        request,
        anchor,
        projection.contracts,
        supplemental_capabilities=projection.binding_capabilities,
        supplemental_sequence_bindings=projection.supplemental_sequence_bindings,
    )

    assert any(evaluation.state is ConstraintState.UNSATISFIED for evaluation in bundle.evaluations)
    assert any(evaluation.state is ConstraintState.UNRESOLVED for evaluation in bundle.evaluations)
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE
