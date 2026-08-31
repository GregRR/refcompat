"""Tests for projecting UCSC preflight into generic RefCompat reasoning."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CapabilityId,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ProfileId,
    ReferenceContext,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceBindingMethod,
    SequenceBindingRequirement,
    SequenceBindingValidationState,
    SequenceCollectionSnapshot,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequencePresenceRequirement,
    SnapshotSequence,
)
from refcompat.profiles import (
    UCSC_PREFLIGHT_PROFILE_ID,
    UcscDatabaseId,
    UcscNameResolutionReason,
    UcscPreflightProjection,
    UcscPreflightTarget,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
    UcscTargetResolutionState,
    project_ucsc_preflight,
)
from refcompat.reasoning import (
    aggregate_bundle_verdict,
    build_reference_context,
    reason_bundle,
)

_REFERENCE = ResourceId("reference")
_PEER = ResourceId("peer")
_DB = UcscDatabaseId("testDb")
_CONTEXT = UcscProviderContextId("testDb@fixture-v1")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_A = RefgetSequenceId("SQ." + "A" * 32)
_B = RefgetSequenceId("SQ." + "B" * 32)
_C = RefgetSequenceId("SQ." + "C" * 32)


def _source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
    *,
    context_id: UcscProviderContextId = _CONTEXT,
) -> UcscProviderSource:
    return UcscProviderSource(
        source_id,
        _DB,
        context_id,
        f"fixture://{source_id}",
        _ACQUIRED_AT,
        (dimension,),
    )


def _provider_sequence(
    name: str,
    length: int,
    identity: RefgetSequenceId | None,
) -> UcscSequence:
    return UcscSequence(
        canonical_name=name,
        length=length,
        catalog_source_ids=(_CATALOG_SOURCE,),
        refget_id=identity,
        identity_source_ids=(_IDENTITY_SOURCE,) if identity is not None else (),
    )


def _provider_snapshot(
    *,
    sequences: tuple[UcscSequence, ...],
    aliases: tuple[UcscSequenceAlias, ...] = (),
    alias_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    identity_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    context_id: UcscProviderContextId = _CONTEXT,
) -> UcscProviderSnapshot:
    return UcscProviderSnapshot(
        database_id=_DB,
        context_id=context_id,
        sequences=sequences,
        aliases=aliases,
        catalog_completeness=UcscProviderCompleteness.COMPLETE,
        alias_completeness=alias_completeness,
        identity_completeness=identity_completeness,
        sources=(
            _source(
                _CATALOG_SOURCE,
                UcscProviderDimension.SEQUENCE_CATALOG,
                context_id=context_id,
            ),
            _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES, context_id=context_id),
            _source(
                _IDENTITY_SOURCE,
                UcscProviderDimension.CONTENT_IDENTITY,
                context_id=context_id,
            ),
        ),
    )


def _request(
    *,
    local_name: str,
    active_profiles: tuple[ProfileId, ...] = (UCSC_PREFLIGHT_PROFILE_ID,),
    anchor_names: tuple[str, ...] | None = None,
) -> EvaluationRequest:
    del local_name
    return EvaluationRequest(
        resources=(
            Resource(_REFERENCE, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
            Resource(_PEER, ResourceKind.VCF, ArtifactIdentity(path=Path("peer.vcf"))),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope((_REFERENCE, _PEER), anchor_names),
        active_profiles=active_profiles,
    )


def _anchor_snapshot(
    sequences: tuple[SnapshotSequence, ...],
) -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )


def _contract(
    local_name: str,
    *,
    identity: RefgetSequenceId | None = None,
) -> ResourceContract:
    capabilities = (
        (
            SequenceIdentityCapability(
                CapabilityId(f"peer-identity:{local_name}"),
                _PEER,
                local_name,
                identity,
                provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
            ),
        )
        if identity is not None
        else ()
    )
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
        capabilities=capabilities,
    )


def _project(
    *,
    local_name: str,
    provider_snapshot: UcscProviderSnapshot,
    anchor_snapshot: SequenceCollectionSnapshot,
    peer_identity: RefgetSequenceId | None = None,
    anchor_names: tuple[str, ...] | None = None,
) -> tuple[EvaluationRequest, ReferenceContext, UcscPreflightProjection]:
    request = _request(local_name=local_name, anchor_names=anchor_names)
    context = build_reference_context(request, anchor_snapshot)
    projection = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        provider_snapshot,
        context,
        (ResourceContract(_REFERENCE), _contract(local_name, identity=peer_identity)),
    )
    return request, context, projection


def _reason(
    request: EvaluationRequest,
    anchor_snapshot: SequenceCollectionSnapshot,
    projection: UcscPreflightProjection,
) -> BundleReasoningResult:
    return reason_bundle(
        request,
        anchor_snapshot,
        projection.contracts,
        supplemental_capabilities=projection.binding_capabilities,
        supplemental_sequence_bindings=projection.supplemental_sequence_bindings,
    )


def test_canonical_target_requires_content_bridge_even_when_names_match() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    provider = _provider_snapshot(
        sequences=(_provider_sequence("chr1", 10, None),),
        identity_completeness=UcscProviderCompleteness.UNKNOWN,
    )
    request, _context, projection = _project(
        local_name="chr1",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
    )

    trace = projection.sequence_projections[0]
    assert isinstance(trace.requirement, SequenceBindingRequirement)
    assert trace.sequence_binding is None
    assert trace.validation_capability is None
    result = _reason(request, anchor, projection)
    states = {
        constraint.requirement.id: evaluation.state
        for constraint, evaluation in zip(result.constraints, result.evaluations, strict=True)
    }
    assert states[trace.requirement.id] is ConstraintState.UNRESOLVED
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INDETERMINATE


def test_complete_authoritative_alias_and_content_bridge_create_binding() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    provider = _provider_snapshot(
        sequences=(_provider_sequence("chr1", 10, _A),),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="ensembl"),),
    )
    request, _context, projection = _project(
        local_name="1",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
    )

    trace = projection.sequence_projections[0]
    assert trace.sequence_binding is not None
    assert trace.sequence_binding.method is SequenceBindingMethod.AUTHORITATIVE_NAME
    assert trace.sequence_binding.anchor_sequence_name == "chr1"
    assert trace.validation_capability is not None
    assert trace.validation_capability.state is SequenceBindingValidationState.BOUND
    assert projection.supplemental_sequence_bindings == (trace.sequence_binding,)

    result = _reason(request, anchor, projection)
    binding_evaluation = next(
        evaluation
        for constraint, evaluation in zip(result.constraints, result.evaluations, strict=True)
        if constraint.requirement.id == trace.requirement.id
    )
    assert binding_evaluation.state is ConstraintState.SATISFIED
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.COMPATIBLE


def test_incomplete_alias_evidence_cannot_manufacture_profile_binding() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    provider = _provider_snapshot(
        sequences=(_provider_sequence("chr1", 10, _A),),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,)),),
        alias_completeness=UcscProviderCompleteness.PARTIAL,
    )
    request, _context, projection = _project(
        local_name="1",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.ALIAS_EVIDENCE_INCOMPLETE
    assert trace.sequence_binding is None
    assert trace.validation_capability is None
    result = _reason(request, anchor, projection)
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INDETERMINATE


def test_exhaustively_absent_ucsc_target_is_incompatible() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    provider = _provider_snapshot(
        sequences=(_provider_sequence("chrMissing", 10, _C),),
    )
    request, _context, projection = _project(
        local_name="chrMissing",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
    )

    trace = projection.sequence_projections[0]
    assert trace.target_resolution is not None
    assert trace.target_resolution.state is UcscTargetResolutionState.PROVEN_ABSENT
    assert trace.validation_capability is not None
    assert trace.validation_capability.state is SequenceBindingValidationState.PROVEN_ABSENT
    result = _reason(request, anchor, projection)
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_absent_ucsc_target_remains_incompatible_with_other_peer_identity_binding() -> None:
    anchor = _anchor_snapshot(
        (
            SnapshotSequence("chr1", 10, 0, _A),
            SnapshotSequence("chr2", 10, 1, _B),
        )
    )
    provider = _provider_snapshot(
        sequences=(_provider_sequence("chrMissing", 10, _C),),
    )
    request, _context, projection = _project(
        local_name="chrMissing",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
        peer_identity=_B,
    )

    trace = projection.sequence_projections[0]
    assert trace.target_resolution is not None
    assert trace.target_resolution.state is UcscTargetResolutionState.PROVEN_ABSENT
    assert trace.validation_capability is not None
    assert trace.validation_capability.state is SequenceBindingValidationState.PROVEN_ABSENT
    assert projection.sequence_bindings[0].anchor_sequence_name == "chr2"
    result = _reason(request, anchor, projection)
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_matching_content_binding_is_reused_instead_of_replaced() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    provider = _provider_snapshot(
        sequences=(_provider_sequence("chr1", 10, _A),),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,)),),
    )
    _request_value, _context, projection = _project(
        local_name="1",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
        peer_identity=_A,
    )

    trace = projection.sequence_projections[0]
    assert trace.sequence_binding is not None
    assert trace.sequence_binding.method is SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
    assert projection.supplemental_sequence_bindings == ()
    assert trace.validation_capability is not None


def test_conflicting_existing_identity_binding_is_incompatible() -> None:
    anchor = _anchor_snapshot(
        (
            SnapshotSequence("chr1", 10, 0, _A),
            SnapshotSequence("chr2", 10, 1, _B),
        )
    )
    provider = _provider_snapshot(
        sequences=(
            _provider_sequence("chr1", 10, _A),
            _provider_sequence("chr2", 10, _B),
        ),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,)),),
    )
    request, _context, projection = _project(
        local_name="1",
        provider_snapshot=provider,
        anchor_snapshot=anchor,
        peer_identity=_B,
    )

    trace = projection.sequence_projections[0]
    assert trace.target_resolution is not None
    assert trace.target_resolution.state is UcscTargetResolutionState.BOUND
    assert trace.sequence_binding is not None
    assert trace.sequence_binding.anchor_sequence_name == "chr2"
    assert trace.validation_capability is not None
    assert trace.validation_capability.state is SequenceBindingValidationState.CONTENT_CONFLICT
    assert trace.validation_capability.anchor_sequence_name == "chr1"
    assert projection.sequence_bindings[0].anchor_sequence_name == "chr2"
    result = _reason(request, anchor, projection)
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_conflicting_peer_identity_blocks_authoritative_name_binding() -> None:
    anchor = _anchor_snapshot(
        (
            SnapshotSequence("chr1", 10, 0, _A),
            SnapshotSequence("chr2", 10, 1, _B),
        )
    )
    provider = _provider_snapshot(
        sequences=(
            _provider_sequence("chr1", 10, _A),
            _provider_sequence("chr2", 10, _B),
        ),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,)),),
    )
    request = _request(local_name="1")
    context = build_reference_context(request, anchor)
    peer = ResourceContract(
        _PEER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId("presence:1"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                "1",
            ),
        ),
        capabilities=(
            SequenceIdentityCapability(
                CapabilityId("peer-identity:a"),
                _PEER,
                "1",
                _A,
                provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
            ),
            SequenceIdentityCapability(
                CapabilityId("peer-identity:b"),
                _PEER,
                "1",
                _B,
                provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
            ),
        ),
    )

    projection = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        provider,
        context,
        (ResourceContract(_REFERENCE), peer),
    )

    trace = projection.sequence_projections[0]
    assert trace.target_resolution is not None
    assert trace.target_resolution.state is UcscTargetResolutionState.BOUND
    assert trace.sequence_binding is None
    assert trace.validation_capability is None
    result = _reason(request, anchor, projection)
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INDETERMINATE


def test_incomplete_peer_identity_match_to_other_anchor_blocks_authoritative_binding() -> None:
    other_md5 = Md5Digest("2" * 32)
    anchor = _anchor_snapshot(
        (
            SnapshotSequence("chr1", 10, 0, _A),
            SnapshotSequence("chr2", 10, 1, _B, md5=other_md5),
        )
    )
    provider = _provider_snapshot(
        sequences=(
            _provider_sequence("chr1", 10, _A),
            _provider_sequence("chr2", 10, _B),
        ),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,)),),
    )
    request = _request(local_name="1")
    context = build_reference_context(request, anchor)
    peer = ResourceContract(
        _PEER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId("presence:1"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                "1",
            ),
        ),
        capabilities=(
            SequenceIdentityCapability(
                CapabilityId("peer-md5"),
                _PEER,
                "1",
                other_md5,
                provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
            ),
        ),
    )

    projection = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        provider,
        context,
        (ResourceContract(_REFERENCE), peer),
    )

    trace = projection.sequence_projections[0]
    assert trace.target_resolution is not None
    assert trace.target_resolution.state is UcscTargetResolutionState.BOUND
    assert trace.sequence_binding is None
    assert trace.validation_capability is None
    result = _reason(request, anchor, projection)
    assert aggregate_bundle_verdict(result).verdict is CompatibilityVerdict.INDETERMINATE


def test_absence_validation_id_includes_provider_context() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    first = _provider_snapshot(
        sequences=(_provider_sequence("chrMissing", 10, _C),),
        context_id=UcscProviderContextId("testDb@first"),
    )
    second = _provider_snapshot(
        sequences=(_provider_sequence("chrMissing", 10, _C),),
        context_id=UcscProviderContextId("testDb@second"),
    )

    first_projection = _project(
        local_name="chrMissing",
        provider_snapshot=first,
        anchor_snapshot=anchor,
    )[2]
    second_projection = _project(
        local_name="chrMissing",
        provider_snapshot=second,
        anchor_snapshot=anchor,
    )[2]

    assert (
        first_projection.binding_capabilities[0].id != second_projection.binding_capabilities[0].id
    )


def test_profile_projection_rejects_missing_or_extra_active_profile() -> None:
    anchor = _anchor_snapshot((SnapshotSequence("chr1", 10, 0, _A),))
    provider = _provider_snapshot(sequences=(_provider_sequence("chr1", 10, _A),))
    contract = _contract("chr1")

    missing_request = _request(local_name="chr1", active_profiles=())
    missing_context = build_reference_context(missing_request, anchor)
    with pytest.raises(ValueError, match="requires the ucsc-preflight profile"):
        project_ucsc_preflight(
            missing_request,
            UcscPreflightTarget(_DB),
            provider,
            missing_context,
            (ResourceContract(_REFERENCE), contract),
        )

    extra_request = _request(
        local_name="chr1",
        active_profiles=(UCSC_PREFLIGHT_PROFILE_ID, ProfileId("other")),
    )
    extra_context = build_reference_context(extra_request, anchor)
    with pytest.raises(ValueError, match="cannot silently ignore"):
        project_ucsc_preflight(
            extra_request,
            UcscPreflightTarget(_DB),
            provider,
            extra_context,
            (ResourceContract(_REFERENCE), contract),
        )
