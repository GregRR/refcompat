"""Explicit projections into report-owned relationship/provenance DTOs."""

from __future__ import annotations

from refcompat.model.contracts import CapabilityId, SequenceIdentityValue
from refcompat.model.report_context import (
    ProfileContextKind,
    ProfileNameResolutionMethod,
    ProfileNameResolutionReason,
    ProfileNameResolutionState,
    ProfileProvenanceContext,
    ProfileSequenceTrace,
    ProfileTargetResolutionReason,
    ProfileTargetResolutionState,
    ProviderCompletenessState,
    ProviderContextId,
    ProviderDimensionCompleteness,
    ProviderEvidenceDimension,
    ProviderSourceId,
    ProviderSourceProvenance,
)
from refcompat.profiles.ucsc import UcscTargetResolutionState
from refcompat.profiles.ucsc_preflight import (
    UCSC_PREFLIGHT_PROFILE_ID,
    UcscPreflightProjection,
    UcscPreflightSequenceProjection,
)


def project_ucsc_preflight_report_context(
    projection: UcscPreflightProjection,
) -> ProfileProvenanceContext:
    """Project an already-derived UCSC preflight trace without re-reasoning it."""

    snapshot = projection.provider_snapshot
    if snapshot is None:
        return ProfileProvenanceContext(
            kind=ProfileContextKind.UCSC_PREFLIGHT,
            profile_id=UCSC_PREFLIGHT_PROFILE_ID,
            provider="ucsc",
            target=str(projection.target.database_id),
            provider_context_id=None,
            sequence_traces=tuple(
                _sequence_trace(item) for item in projection.sequence_projections
            ),
        )

    context_id = ProviderContextId(str(snapshot.context_id))
    return ProfileProvenanceContext(
        kind=ProfileContextKind.UCSC_PREFLIGHT,
        profile_id=UCSC_PREFLIGHT_PROFILE_ID,
        provider="ucsc",
        target=str(projection.target.database_id),
        provider_context_id=context_id,
        completeness=(
            ProviderDimensionCompleteness(
                ProviderEvidenceDimension.SEQUENCE_CATALOG,
                ProviderCompletenessState(snapshot.catalog_completeness.value),
            ),
            ProviderDimensionCompleteness(
                ProviderEvidenceDimension.ALIASES,
                ProviderCompletenessState(snapshot.alias_completeness.value),
            ),
            ProviderDimensionCompleteness(
                ProviderEvidenceDimension.CONTENT_IDENTITY,
                ProviderCompletenessState(snapshot.identity_completeness.value),
            ),
        ),
        sources=tuple(
            ProviderSourceProvenance(
                id=ProviderSourceId(str(source.id)),
                context_id=context_id,
                locator=source.locator,
                acquired_at=source.acquired_at,
                dimensions=tuple(
                    ProviderEvidenceDimension(dimension.value) for dimension in source.dimensions
                ),
            )
            for source in snapshot.sources
        ),
        sequence_traces=tuple(_sequence_trace(item) for item in projection.sequence_projections),
    )


def _sequence_trace(projection: UcscPreflightSequenceProjection) -> ProfileSequenceTrace:
    target = projection.target_resolution
    target_binding = target.binding if target is not None else None

    target_state: ProfileTargetResolutionState | None = None
    target_reason: ProfileTargetResolutionReason | None = None
    target_identity_values: tuple[SequenceIdentityValue, ...] = ()
    target_provider_source_ids: tuple[ProviderSourceId, ...] = ()
    target_binding_id: str | None = None
    target_anchor_sequence_name: str | None = None
    target_anchor_capability_ids: tuple[CapabilityId, ...] = ()

    if target is not None:
        target_state = ProfileTargetResolutionState(target.state.value)
        target_reason = ProfileTargetResolutionReason(target.reason.value)
        if target.state is UcscTargetResolutionState.BOUND:
            assert target_binding is not None
            target_identity_values = target_binding.identity_values
            target_provider_source_ids = tuple(
                ProviderSourceId(str(source_id)) for source_id in target_binding.provider_source_ids
            )
            target_binding_id = str(target_binding.id)
            target_anchor_sequence_name = target_binding.anchor_sequence_name
            target_anchor_capability_ids = target_binding.anchor_capability_ids
        else:
            target_identity_values = target.identity_values
            target_provider_source_ids = tuple(
                ProviderSourceId(str(source_id)) for source_id in target.provider_source_ids
            )

    return ProfileSequenceTrace(
        requirement_id=projection.requirement.id,
        resource_id=projection.resource_id,
        local_sequence_name=projection.local_sequence_name,
        name_resolution_state=ProfileNameResolutionState(projection.name_resolution.state.value),
        name_resolution_reason=ProfileNameResolutionReason(projection.name_resolution.reason.value),
        name_resolution_method=(
            ProfileNameResolutionMethod(projection.name_resolution.method.value)
            if projection.name_resolution.method is not None
            else None
        ),
        provider_target_name=projection.name_resolution.canonical_name,
        target_resolution_state=target_state,
        target_resolution_reason=target_reason,
        target_binding_id=target_binding_id,
        target_anchor_sequence_name=target_anchor_sequence_name,
        target_identity_values=target_identity_values,
        target_anchor_capability_ids=target_anchor_capability_ids,
        name_provider_source_ids=tuple(
            ProviderSourceId(str(source_id))
            for source_id in projection.name_resolution.provider_source_ids
        ),
        target_provider_source_ids=target_provider_source_ids,
        sequence_binding_id=(
            projection.sequence_binding.id if projection.sequence_binding is not None else None
        ),
        validation_capability_id=(
            projection.validation_capability.id
            if projection.validation_capability is not None
            else None
        ),
    )
