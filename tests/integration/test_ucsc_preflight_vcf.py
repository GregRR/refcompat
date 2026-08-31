"""Representative end-to-end VCF path through the UCSC preflight profile."""

from datetime import datetime, timezone
from pathlib import Path

from refcompat.model import (
    ArtifactIdentity,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    RefgetSequenceId,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceBindingMethod,
    SequenceCollectionSnapshot,
    SnapshotSequence,
    VcfChromUsage,
    VcfContextSnapshot,
    VcfHeaderData,
    VcfRefRecord,
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
    build_reference_context,
    build_vcf_contract,
    evaluate_vcf_ref_records,
    project_vcf_contract,
    reason_bundle,
)

_FASTA = ResourceId("reference")
_VCF = ResourceId("variants")
_DB = UcscDatabaseId("testDb")
_CONTEXT = UcscProviderContextId("testDb@fixture-v1")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_REFGET = RefgetSequenceId("SQ." + "A" * 32)


class _Reference:
    resource_id = _FASTA

    def sequence_length(self, sequence_name: str) -> int | None:
        return 4 if sequence_name == "chr1" else None

    def fetch(self, sequence_name: str, start: int, end: int) -> str:
        assert sequence_name == "chr1"
        return "ACGT"[start:end]


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
            Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
        ),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _VCF)),
        active_profiles=(UCSC_PREFLIGHT_PROFILE_ID,),
    )


def _anchor_snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, _REFGET),),
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


def _provider_snapshot(*, with_identity: bool, with_alias: bool) -> UcscProviderSnapshot:
    sequence = UcscSequence(
        canonical_name="chr1",
        length=4,
        catalog_source_ids=(_CATALOG_SOURCE,),
        refget_id=_REFGET if with_identity else None,
        identity_source_ids=(_IDENTITY_SOURCE,) if with_identity else (),
    )
    aliases = (
        (UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="ensembl"),)
        if with_alias
        else ()
    )
    return UcscProviderSnapshot(
        database_id=_DB,
        context_id=_CONTEXT,
        sequences=(sequence,),
        aliases=aliases,
        catalog_completeness=UcscProviderCompleteness.COMPLETE,
        alias_completeness=UcscProviderCompleteness.COMPLETE,
        identity_completeness=(
            UcscProviderCompleteness.COMPLETE if with_identity else UcscProviderCompleteness.UNKNOWN
        ),
        sources=(
            _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
            _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
            _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
        ),
    )


def _vcf_snapshot(local_name: str) -> VcfContextSnapshot:
    return VcfContextSnapshot(
        _VCF,
        VcfHeaderData("VCFv4.5"),
        record_count=1,
        chrom_usage=(VcfChromUsage(local_name, 1),),
    )


def test_ucsc_alias_binding_drives_existing_vcf_ref_and_bundle_reasoning() -> None:
    request = _request()
    anchor_snapshot = _anchor_snapshot()
    context = build_reference_context(request, anchor_snapshot)
    vcf_snapshot = _vcf_snapshot("1")
    core_contract = build_vcf_contract(vcf_snapshot, context)

    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(with_identity=True, with_alias=True),
        context,
        (ResourceContract(_FASTA), core_contract),
    )
    assert len(preflight.supplemental_sequence_bindings) == 1
    binding = preflight.supplemental_sequence_bindings[0]
    assert binding.method is SequenceBindingMethod.AUTHORITATIVE_NAME
    assert binding.local_sequence_name == "1"
    assert binding.anchor_sequence_name == "chr1"

    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 1, "A"),),
        reference=_Reference(),
        sequence_bindings=preflight.sequence_bindings,
    )
    assert validation.match_count == 1
    assert validation.sequence_binding_ids == (binding.id,)

    vcf_projection = project_vcf_contract(
        vcf_snapshot,
        validation,
        context,
        sequence_bindings=preflight.sequence_bindings,
    )
    bundle = reason_bundle(
        request,
        anchor_snapshot,
        preflight.contracts,
        supplemental_capabilities=(
            *preflight.binding_capabilities,
            vcf_projection.reference_base_capability,
        ),
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )

    assert all(evaluation.state is ConstraintState.SATISFIED for evaluation in bundle.evaluations)
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_matching_vcf_ref_cannot_rescue_missing_ucsc_target_identity() -> None:
    request = _request()
    anchor_snapshot = _anchor_snapshot()
    context = build_reference_context(request, anchor_snapshot)
    vcf_snapshot = _vcf_snapshot("chr1")
    core_contract = build_vcf_contract(vcf_snapshot, context)

    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(with_identity=False, with_alias=False),
        context,
        (ResourceContract(_FASTA), core_contract),
    )
    assert preflight.sequence_bindings == ()
    assert preflight.binding_capabilities == ()

    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "chr1", 1, "A"),),
        reference=_Reference(),
    )
    assert validation.match_count == 1

    vcf_projection = project_vcf_contract(vcf_snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor_snapshot,
        preflight.contracts,
        supplemental_capabilities=(vcf_projection.reference_base_capability,),
    )

    core_states = tuple(
        evaluation.state
        for constraint, evaluation in zip(bundle.constraints, bundle.evaluations, strict=True)
        if constraint.requirement.origin.value == "core_format"
    )
    assert core_states and all(state is ConstraintState.SATISFIED for state in core_states)
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INDETERMINATE
