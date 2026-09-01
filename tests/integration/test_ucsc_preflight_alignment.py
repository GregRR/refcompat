"""Representative BAM/CRAM paths through the UCSC preflight profile."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentContentRelationship,
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    AlignmentMembershipRelationship,
    AlignmentNameResolutionMethod,
    AlignmentNamingRelationship,
    AlignmentOrderRelationship,
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConstraintState,
    CramOfflineReferenceAction,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ReferenceContext,
    RefgetSequenceId,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceBindingMethod,
    SequenceCollectionSnapshot,
    SequenceDictionaryRecord,
    SnapshotSequence,
)
from refcompat.profiles import (
    UCSC_PREFLIGHT_PROFILE_ID,
    UcscDatabaseId,
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
    project_ucsc_preflight,
)
from refcompat.reasoning import (
    aggregate_bundle_verdict,
    build_alignment_contract,
    build_reference_context,
    classify_alignment_dictionary_relationship,
    plan_cram_offline_reference,
    reason_bundle,
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
_WRONG_MD5 = Md5Digest("31fc6ca291a32fb9df82b85e5f077e31")


def _request(kind: ResourceKind, anchor_path: Path = Path("reference.fa")) -> EvaluationRequest:
    suffix = "bam" if kind is ResourceKind.BAM else "cram"
    return EvaluationRequest(
        resources=(
            Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=anchor_path)),
            Resource(_ALIGNMENT, kind, ArtifactIdentity(path=Path(f"reads.{suffix}"))),
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


def _provider_snapshot(
    alias_names: tuple[str, ...] = ("1",),
) -> UcscProviderSnapshot:
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
        aliases=tuple(
            UcscSequenceAlias(alias, "chr1", (_ALIAS_SOURCE,), authority="ensembl")
            for alias in alias_names
        ),
        catalog_completeness=UcscProviderCompleteness.COMPLETE,
        alias_completeness=UcscProviderCompleteness.COMPLETE,
        identity_completeness=UcscProviderCompleteness.COMPLETE,
        sources=(
            _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
            _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
            _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
        ),
    )


def _alignment_snapshot(
    kind: ResourceKind,
    *,
    names: tuple[str, ...] = ("1",),
    md5: Md5Digest | None = None,
) -> AlignmentHeaderSnapshot:
    return AlignmentHeaderSnapshot(
        _ALIGNMENT,
        kind,
        AlignmentHeaderData(
            sequences=tuple(SequenceDictionaryRecord(name, 4, md5=md5) for name in names)
        ),
    )


def _reason_alignment(
    kind: ResourceKind,
    anchor_path: Path = Path("reference.fa"),
) -> tuple[
    EvaluationRequest,
    ReferenceContext,
    AlignmentHeaderSnapshot,
    UcscPreflightProjection,
    BundleReasoningResult,
]:
    request = _request(kind, anchor_path)
    anchor_snapshot = _anchor_snapshot()
    context = build_reference_context(request, anchor_snapshot)
    alignment_snapshot = _alignment_snapshot(kind)
    core_contract = build_alignment_contract(alignment_snapshot, context)
    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(),
        context,
        (ResourceContract(_FASTA), core_contract),
    )
    bundle = reason_bundle(
        request,
        anchor_snapshot,
        preflight.contracts,
        supplemental_capabilities=preflight.binding_capabilities,
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )
    return request, context, alignment_snapshot, preflight, bundle


def test_ucsc_alias_binding_drives_existing_bam_dictionary_reasoning() -> None:
    _request_value, context, snapshot, preflight, bundle = _reason_alignment(ResourceKind.BAM)

    assert len(preflight.supplemental_sequence_bindings) == 1
    binding = preflight.supplemental_sequence_bindings[0]
    assert binding.method is SequenceBindingMethod.AUTHORITATIVE_NAME
    assert binding.local_sequence_name == "1"
    assert binding.anchor_sequence_name == "chr1"
    assert all(evaluation.state is ConstraintState.SATISFIED for evaluation in bundle.evaluations)
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE

    relationship = classify_alignment_dictionary_relationship(
        snapshot,
        context,
        bundle_result=bundle,
    )
    assert relationship.membership is AlignmentMembershipRelationship.EXACT
    assert relationship.naming is AlignmentNamingRelationship.VERIFIED_DIFFERENCE
    assert relationship.order is AlignmentOrderRelationship.CONSISTENT
    assert relationship.content is AlignmentContentRelationship.UNRESOLVED
    assert not relationship.verified_naming_only_difference
    assert len(relationship.resolutions) == 1
    resolution = relationship.resolutions[0]
    assert resolution.method is AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING
    assert resolution.sequence_binding_id == binding.id


def test_ucsc_compatible_cram_alias_still_defers_reference_dependent_decoding(
    tmp_path: Path,
) -> None:
    anchor_path = tmp_path / "reference.fa"
    anchor_path.write_text(">chr1\nACGT\n", encoding="utf-8")
    request, context, snapshot, _preflight, bundle = _reason_alignment(
        ResourceKind.CRAM,
        anchor_path,
    )

    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE

    plan = plan_cram_offline_reference(
        snapshot,
        context,
        request,
        bundle_result=bundle,
    )
    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING
    assert plan.reference_path is None
    assert plan.anchor_path_readable
    assert plan.relationship.membership is AlignmentMembershipRelationship.EXACT
    assert plan.relationship.naming is AlignmentNamingRelationship.VERIFIED_DIFFERENCE
    assert plan.relationship.content is AlignmentContentRelationship.UNRESOLVED
    assert plan.relationship.resolutions[0].method is (
        AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING
    )


def test_ucsc_alias_does_not_override_bam_m5_conflict() -> None:
    request = _request(ResourceKind.BAM)
    anchor_snapshot = _anchor_snapshot()
    context = build_reference_context(request, anchor_snapshot)
    alignment_snapshot = _alignment_snapshot(ResourceKind.BAM, md5=_WRONG_MD5)
    core_contract = build_alignment_contract(alignment_snapshot, context)
    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(),
        context,
        (ResourceContract(_FASTA), core_contract),
    )
    bundle = reason_bundle(
        request,
        anchor_snapshot,
        preflight.contracts,
        supplemental_capabilities=preflight.binding_capabilities,
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )

    assert len(preflight.supplemental_sequence_bindings) == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE
    assert any(evaluation.state is ConstraintState.UNSATISFIED for evaluation in bundle.evaluations)

    relationship = classify_alignment_dictionary_relationship(
        alignment_snapshot,
        context,
        bundle_result=bundle,
    )
    assert relationship.naming is AlignmentNamingRelationship.VERIFIED_DIFFERENCE
    assert relationship.content is AlignmentContentRelationship.M5_CONFLICT
    assert relationship.identity_conflict_sequence_names == ("1",)


def test_cram_plan_rejects_profile_bundle_from_different_request(tmp_path: Path) -> None:
    first_anchor = tmp_path / "first.fa"
    first_anchor.write_text(">chr1\nACGT\n", encoding="utf-8")
    _request_value, context, snapshot, _preflight, bundle = _reason_alignment(
        ResourceKind.CRAM,
        first_anchor,
    )
    second_anchor = tmp_path / "second.fa"
    second_anchor.write_text(">chr1\nACGT\n", encoding="utf-8")
    other_request = _request(ResourceKind.CRAM, second_anchor)

    with pytest.raises(ValueError, match="bundle/request mismatch"):
        plan_cram_offline_reference(
            snapshot,
            context,
            other_request,
            bundle_result=bundle,
        )


def test_multiple_ucsc_aliases_to_one_anchor_keep_dictionary_nonbijective() -> None:
    request = _request(ResourceKind.BAM)
    anchor_snapshot = _anchor_snapshot()
    context = build_reference_context(request, anchor_snapshot)
    alignment_snapshot = _alignment_snapshot(
        ResourceKind.BAM,
        names=("1", "chrOne"),
    )
    core_contract = build_alignment_contract(alignment_snapshot, context)
    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(("1", "chrOne")),
        context,
        (ResourceContract(_FASTA), core_contract),
    )
    bundle = reason_bundle(
        request,
        anchor_snapshot,
        preflight.contracts,
        supplemental_capabilities=preflight.binding_capabilities,
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )

    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE
    relationship = classify_alignment_dictionary_relationship(
        alignment_snapshot,
        context,
        bundle_result=bundle,
    )
    assert relationship.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert relationship.naming is AlignmentNamingRelationship.UNRESOLVED
    assert relationship.order is AlignmentOrderRelationship.UNRESOLVED
    assert relationship.duplicate_anchor_target_names == ("chr1",)
    assert tuple(resolution.method for resolution in relationship.resolutions) == (
        AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING,
        AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING,
    )
