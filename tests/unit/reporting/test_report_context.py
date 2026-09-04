"""Report-owned alignment and provider/provenance context tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    AlignmentNameResolutionMethod,
    AnalysisStatus,
    ArtifactIdentity,
    CollectionCompleteness,
    CompatibilityReport,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ObservationId,
    ObservationKind,
    ProfileContextKind,
    ProfileNameResolutionMethod,
    ProfileNameResolutionReason,
    ProfileNameResolutionState,
    ProfileTargetResolutionReason,
    ProfileTargetResolutionState,
    ProviderCompletenessState,
    ProviderEvidenceDimension,
    RefgetSequenceId,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    ResourceObservation,
    SequenceBindingMethod,
    SequenceCollectionSnapshot,
    SequenceDictionaryRecord,
    SequenceIdentityCapability,
    SnapshotSequence,
    SourceLocation,
)
from refcompat.model import (
    __all__ as model_exports,
)
from refcompat.profiles import (
    UCSC_PREFLIGHT_PROFILE_ID,
    UcscDatabaseId,
    UcscPreflightTarget,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
    project_ucsc_preflight,
)
from refcompat.reasoning import (
    aggregate_bundle_verdict,
    build_alignment_contract,
    build_reference_context,
    classify_alignment_dictionary_relationship,
    extract_conflict_cores,
    reason_bundle,
)
from refcompat.reporting import (
    compatibility_report_payload,
    project_ucsc_preflight_report_context,
    render_compatibility_report_human,
    render_compatibility_report_json,
)

_FASTA = ResourceId("reference")
_ALIGNMENT = ResourceId("reads")
_DB = UcscDatabaseId("testDb")
_CONTEXT = UcscProviderContextId("testDb@fixture-v1")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
_REFGET = RefgetSequenceId("SQ." + "A" * 32)
_MD5 = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_CONTEXT_FIXTURE = (
    Path(__file__).parents[2]
    / "fixtures"
    / "milestone7"
    / "stable-ucsc-alignment-report-1.1.0.json"
)


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
            Resource(_ALIGNMENT, ResourceKind.BAM, ArtifactIdentity(path=Path("reads.bam"))),
        ),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _ALIGNMENT)),
        active_profiles=(UCSC_PREFLIGHT_PROFILE_ID,),
    )


def _anchor_snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, _REFGET, _MD5),),
    )


def _source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
) -> UcscProviderSource:
    return UcscProviderSource(
        source_id,
        _DB,
        _CONTEXT,
        f"fixture://{source_id}",
        _ACQUIRED_AT,
        (dimension,),
    )


def _provider_snapshot() -> UcscProviderSnapshot:
    return UcscProviderSnapshot(
        database_id=_DB,
        context_id=_CONTEXT,
        sequences=(
            UcscSequence(
                canonical_name="chr1",
                length=4,
                catalog_source_ids=(_CATALOG_SOURCE,),
                refget_id=_REFGET,
                identity_source_ids=(_IDENTITY_SOURCE,),
            ),
        ),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="ensembl"),),
        catalog_completeness=UcscProviderCompleteness.COMPLETE,
        alias_completeness=UcscProviderCompleteness.COMPLETE,
        identity_completeness=UcscProviderCompleteness.COMPLETE,
        sources=(
            _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
            _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
            _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
        ),
    )


def _contextual_report() -> CompatibilityReport:
    request = _request()
    anchor = _anchor_snapshot()
    reference_context = build_reference_context(request, anchor)
    alignment = AlignmentHeaderSnapshot(
        _ALIGNMENT,
        ResourceKind.BAM,
        AlignmentHeaderData(sequences=(SequenceDictionaryRecord("1", 4),)),
    )
    core_contract = build_alignment_contract(alignment, reference_context)
    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(),
        reference_context,
        (ResourceContract(_FASTA), core_contract),
    )
    bundle = reason_bundle(
        request,
        anchor,
        preflight.contracts,
        supplemental_capabilities=preflight.binding_capabilities,
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )
    verdict = aggregate_bundle_verdict(bundle)
    relationship = classify_alignment_dictionary_relationship(
        alignment,
        reference_context,
        bundle_result=bundle,
    )
    return CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=request,
        analysis_status=AnalysisStatus.COMPLETE,
        bundle=bundle,
        verdict=verdict,
        conflict_cores=extract_conflict_cores(bundle, verdict),
        observations=(
            ResourceObservation(
                ObservationId("obs:alignment-dictionary"),
                _ALIGNMENT,
                ObservationKind("alignment.header.sequence_dictionary"),
                True,
                SourceLocation(locator="SAM @SQ dictionary"),
            ),
        ),
        alignment_relationships=(relationship,),
        profile_contexts=(project_ucsc_preflight_report_context(preflight),),
    )


def test_report_context_types_are_public_model_exports() -> None:
    expected = {
        "ProfileContextKind",
        "ProfileNameResolutionMethod",
        "ProfileNameResolutionReason",
        "ProfileNameResolutionState",
        "ProfileProvenanceContext",
        "ProfileSequenceTrace",
        "ProfileTargetResolutionReason",
        "ProfileTargetResolutionState",
        "ProviderCompletenessState",
        "ProviderContextId",
        "ProviderDimensionCompleteness",
        "ProviderEvidenceDimension",
        "ProviderSourceId",
        "ProviderSourceProvenance",
    }

    assert expected.issubset(model_exports)


def test_ucsc_projection_keeps_report_owned_provider_trace() -> None:
    report = _contextual_report()
    context = report.profile_contexts[0]

    assert context.kind is ProfileContextKind.UCSC_PREFLIGHT
    assert str(context.profile_id) == "ucsc-preflight"
    assert context.provider == "ucsc"
    assert context.target == "testDb"
    assert str(context.provider_context_id) == "testDb@fixture-v1"
    assert {item.dimension: item.state for item in context.completeness} == {
        ProviderEvidenceDimension.SEQUENCE_CATALOG: ProviderCompletenessState.COMPLETE,
        ProviderEvidenceDimension.ALIASES: ProviderCompletenessState.COMPLETE,
        ProviderEvidenceDimension.CONTENT_IDENTITY: ProviderCompletenessState.COMPLETE,
    }
    assert {str(source.id) for source in context.sources} == {"catalog", "aliases", "identity"}

    trace = context.sequence_traces[0]
    assert trace.name_resolution_state is ProfileNameResolutionState.RESOLVED
    assert trace.name_resolution_method is ProfileNameResolutionMethod.AUTHORITATIVE_ALIAS
    assert trace.provider_target_name == "chr1"
    assert trace.target_resolution_state is ProfileTargetResolutionState.BOUND
    assert trace.target_anchor_sequence_name == "chr1"
    assert {str(value) for value in trace.name_provider_source_ids} == {"catalog", "aliases"}
    assert {str(value) for value in trace.target_provider_source_ids} == {"catalog", "identity"}
    assert report.bundle is not None
    assert trace.sequence_binding_id == report.bundle.sequence_bindings[0].id
    assert report.bundle.sequence_bindings[0].method is SequenceBindingMethod.AUTHORITATIVE_NAME


def test_report_rejects_crosswired_alignment_relationship_binding() -> None:
    report = _contextual_report()
    relationship = report.alignment_relationships[0]
    resolution = relationship.resolutions[0]
    malformed = replace(
        relationship,
        resolutions=(replace(resolution, anchor_sequence_name="other"),),
    )

    with pytest.raises(ValueError, match="relationship sequence binding is cross-wired"):
        replace(report, alignment_relationships=(malformed,))


def test_report_rejects_profile_context_for_inactive_profile() -> None:
    report = _contextual_report()
    assert report.bundle is not None
    request = replace(report.request, active_profiles=())
    bundle = replace(report.bundle, request=request)

    with pytest.raises(ValueError, match="profile context must be active"):
        replace(report, request=request, bundle=bundle)


def test_alignment_relationship_retains_authoritative_binding_method() -> None:
    relationship = _contextual_report().alignment_relationships[0]

    assert relationship.resolutions[0].method is (
        AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING
    )


def test_contextual_report_payload_exposes_relationship_and_provenance() -> None:
    payload = compatibility_report_payload(_contextual_report())
    scientific = payload["scientific_result"]
    assert isinstance(scientific, dict)

    observations = scientific["observations"]
    relationships = scientific["alignment_relationships"]
    contexts = scientific["profile_contexts"]
    assert isinstance(observations, list) and observations[0]["id"] == "obs:alignment-dictionary"
    assert isinstance(relationships, list)
    assert relationships[0]["naming"] == "verified_difference"
    assert relationships[0]["resolutions"][0]["method"] == "authoritative_name_binding"
    assert isinstance(contexts, list)
    assert contexts[0]["type"] == "ucsc_preflight"
    assert contexts[0]["sequence_traces"][0]["name_resolution_method"] == "authoritative_alias"


def test_contextual_known_answer_pins_stable_bytes() -> None:
    assert render_compatibility_report_json(_contextual_report()) == _CONTEXT_FIXTURE.read_bytes()


def test_unavailable_provider_projects_unresolved_report_context() -> None:
    request = _request()
    anchor = _anchor_snapshot()
    reference_context = build_reference_context(request, anchor)
    alignment = AlignmentHeaderSnapshot(
        _ALIGNMENT,
        ResourceKind.BAM,
        AlignmentHeaderData(sequences=(SequenceDictionaryRecord("1", 4),)),
    )
    core_contract = build_alignment_contract(alignment, reference_context)
    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        None,
        reference_context,
        (ResourceContract(_FASTA), core_contract),
    )

    context = project_ucsc_preflight_report_context(preflight)

    assert context.provider_context_id is None
    assert context.completeness == ()
    assert context.sources == ()
    assert len(context.sequence_traces) == 1
    trace = context.sequence_traces[0]
    assert trace.name_resolution_state is ProfileNameResolutionState.UNRESOLVED
    assert trace.name_resolution_reason is ProfileNameResolutionReason.PROVIDER_EVIDENCE_UNAVAILABLE
    assert trace.provider_target_name is None
    assert trace.target_resolution_state is None
    assert trace.name_provider_source_ids == ()
    assert trace.target_provider_source_ids == ()


def test_available_provider_context_requires_complete_dimension_inventory() -> None:
    context = _contextual_report().profile_contexts[0]

    with pytest.raises(ValueError, match="all provider completeness dimensions"):
        replace(context, completeness=context.completeness[:-1])


def test_bound_profile_trace_requires_content_bound_reason() -> None:
    trace = _contextual_report().profile_contexts[0].sequence_traces[0]

    with pytest.raises(ValueError, match="content-bound reason"):
        replace(
            trace,
            target_resolution_reason=ProfileTargetResolutionReason.CONTENT_IDENTITY_UNRESOLVED,
        )


def test_report_rejects_profile_validation_state_crosswire() -> None:
    report = _contextual_report()
    context = report.profile_contexts[0]
    trace = context.sequence_traces[0]
    malformed_trace = replace(
        trace,
        target_resolution_state=ProfileTargetResolutionState.PROVEN_ABSENT,
        target_resolution_reason=ProfileTargetResolutionReason.EXHAUSTIVE_CONTENT_ABSENCE,
        target_binding_id=None,
        target_anchor_sequence_name=None,
        target_anchor_capability_ids=(),
        sequence_binding_id=None,
    )

    with pytest.raises(ValueError, match="requires proven-absent validation"):
        replace(
            report,
            profile_contexts=(replace(context, sequence_traces=(malformed_trace,)),),
        )


def test_report_rejects_crosswired_profile_anchor_capability() -> None:
    report = _contextual_report()
    assert report.bundle is not None
    context = report.profile_contexts[0]
    trace = context.sequence_traces[0]
    non_identity = next(
        capability
        for capability in report.bundle.reference_context.anchor_capabilities
        if not isinstance(capability, SequenceIdentityCapability)
    )
    malformed_trace = replace(trace, target_anchor_capability_ids=(non_identity.id,))

    with pytest.raises(ValueError, match="anchor capability is cross-wired"):
        replace(
            report,
            profile_contexts=(replace(context, sequence_traces=(malformed_trace,)),),
        )


def test_human_report_surfaces_alignment_and_provider_context() -> None:
    rendered = render_compatibility_report_human(_contextual_report())

    assert "Alignment dictionary relationships" in rendered
    assert "reads -> reference" in rendered
    assert "authoritative_name_binding" in rendered
    assert "Profile/provider provenance" in rendered
    assert "ucsc-preflight" in rendered
    assert "sequence_catalog=complete" in rendered
    assert "provider target: chr1" in rendered
    assert "target resolution: bound/content_bound" in rendered
