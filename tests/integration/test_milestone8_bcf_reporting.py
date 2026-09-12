"""Milestone 8 scoped, profile, and reporting parity for native BCF."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from refcompat import __version__
from refcompat.inspectors.vcf import VcfParseError, inspect_vcf_context, iter_vcf_ref_records
from refcompat.model import (
    AnalysisIssue,
    AnalysisIssueId,
    AnalysisIssueKind,
    AnalysisStatus,
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityReport,
    CompatibilityVerdict,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ProfileId,
    ProfileProvenanceContext,
    RefgetSequenceId,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SnapshotSequence,
    VcfRefValidationResult,
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
    extract_conflict_cores,
    project_vcf_contract,
    reason_bundle,
)
from refcompat.reporting import (
    REPORT_SCHEMA_VERSION,
    WorkflowExitCode,
    project_ucsc_preflight_report_context,
    render_compatibility_report_human,
    render_compatibility_report_json,
    workflow_exit_code,
)

_FASTA = ResourceId("reference")
_PEER = ResourceId("variants")
_OUTSIDE = ResourceId("outside")
_REFGET = RefgetSequenceId("SQ." + "A" * 32)
_MD5 = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_DB = UcscDatabaseId("testDb")
_PROVIDER_CONTEXT = UcscProviderContextId("testDb@m8-slice4")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 9, 12, 7, 0, tzinfo=timezone.utc)


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...

    def iter_errors(self, instance: object) -> Iterable[object]: ...


class _SchemaValidatorClass(Protocol):
    def __call__(self, schema: object) -> _SchemaValidator: ...


class _JsonSchemaModule(Protocol):
    Draft202012Validator: _SchemaValidatorClass


class _Reference:
    resource_id = _FASTA

    def sequence_length(self, sequence_name: str) -> int | None:
        return 4 if sequence_name == "chr1" else None

    def fetch(self, sequence_name: str, start: int, end: int) -> str:
        if sequence_name != "chr1":
            raise KeyError(sequence_name)
        return "ACGT"[start:end]


def _jsonschema() -> _JsonSchemaModule:
    return cast(_JsonSchemaModule, import_module("jsonschema"))


def _schema(version: str) -> dict[str, Any]:
    resource = files("refcompat.schemas").joinpath(f"compatibility-report-{version}.schema.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _resource(resource_id: ResourceId, kind: ResourceKind, path: Path) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path), display_name=path.name)


def _anchor_snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, _REFGET, _MD5),),
    )


def _write_vcf(
    path: Path,
    *,
    sequence_name: str,
    ref: str,
    position: int = 2,
) -> None:
    path.write_text(
        "\n".join(
            (
                "##fileformat=VCFv4.2",
                f"##contig=<ID={sequence_name},length=4>",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                f"{sequence_name}\t{position}\t.\t{ref}\tA\t.\tPASS\t.",
                "",
            )
        ),
        encoding="ascii",
    )


def _convert_to_bcf(vcf_path: Path, bcf_path: Path) -> None:
    pysam = cast(Any, import_module("pysam"))
    with (
        pysam.VariantFile(str(vcf_path)) as source,
        pysam.VariantFile(str(bcf_path), "wb", header=source.header) as target,
    ):
        for record in source:
            target.write(record)


def _bcf(tmp_path: Path, *, sequence_name: str, ref: str, position: int = 2) -> Resource:
    vcf_path = tmp_path / "source.vcf"
    bcf_path = tmp_path / "variants.bcf"
    _write_vcf(vcf_path, sequence_name=sequence_name, ref=ref, position=position)
    _convert_to_bcf(vcf_path, bcf_path)
    return _resource(_PEER, ResourceKind.BCF, bcf_path)


def _request(
    bcf: Resource,
    *,
    outside: Resource | None = None,
    active_profiles: tuple[ProfileId, ...] = (),
) -> EvaluationRequest:
    anchor = _resource(_FASTA, ResourceKind.FASTA, Path("reference.fa"))
    resources = (anchor, bcf) if outside is None else (anchor, bcf, outside)
    return EvaluationRequest(
        resources=resources,
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
        active_profiles=active_profiles,
    )


def _bundle(
    request: EvaluationRequest,
    bcf: Resource,
) -> tuple[BundleReasoningResult, VcfRefValidationResult]:
    anchor = _anchor_snapshot()
    context = build_reference_context(request, anchor)
    snapshot = inspect_vcf_context(bcf)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_PEER,
        fasta_resource_id=_FASTA,
        records=iter_vcf_ref_records(bcf),
        reference=_Reference(),
    )
    projection = project_vcf_contract(snapshot, validation, context)
    contracts = tuple(
        projection.contract if resource_id == _PEER else ResourceContract(resource_id)
        for resource_id in request.scope.resource_ids
    )
    bundle = reason_bundle(
        request,
        anchor,
        contracts,
        supplemental_capabilities=(projection.reference_base_capability,),
    )
    return bundle, validation


def _provider_source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
) -> UcscProviderSource:
    return UcscProviderSource(
        source_id,
        _DB,
        _PROVIDER_CONTEXT,
        f"fixture://milestone8/{source_id}",
        _ACQUIRED_AT,
        (dimension,),
    )


def _provider_snapshot() -> UcscProviderSnapshot:
    return UcscProviderSnapshot(
        database_id=_DB,
        context_id=_PROVIDER_CONTEXT,
        sequences=(
            UcscSequence(
                canonical_name="chr1",
                length=4,
                catalog_source_ids=(_CATALOG_SOURCE,),
                refget_id=_REFGET,
                identity_source_ids=(_IDENTITY_SOURCE,),
            ),
        ),
        aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="fixture"),),
        catalog_completeness=UcscProviderCompleteness.COMPLETE,
        alias_completeness=UcscProviderCompleteness.COMPLETE,
        identity_completeness=UcscProviderCompleteness.COMPLETE,
        sources=(
            _provider_source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
            _provider_source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
            _provider_source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
        ),
    )


def _profile_bundle(
    request: EvaluationRequest,
    bcf: Resource,
) -> tuple[BundleReasoningResult, ProfileProvenanceContext, VcfRefValidationResult]:
    anchor = _anchor_snapshot()
    context = build_reference_context(request, anchor)
    snapshot = inspect_vcf_context(bcf)
    core_contract = build_vcf_contract(snapshot, context)
    preflight = project_ucsc_preflight(
        request,
        UcscPreflightTarget(_DB),
        _provider_snapshot(),
        context,
        (ResourceContract(_FASTA), core_contract),
    )
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_PEER,
        fasta_resource_id=_FASTA,
        records=iter_vcf_ref_records(bcf),
        reference=_Reference(),
        sequence_bindings=preflight.sequence_bindings,
    )
    projection = project_vcf_contract(
        snapshot,
        validation,
        context,
        sequence_bindings=preflight.sequence_bindings,
    )
    bundle = reason_bundle(
        request,
        anchor,
        preflight.contracts,
        supplemental_capabilities=(
            *preflight.binding_capabilities,
            projection.reference_base_capability,
        ),
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )
    return bundle, project_ucsc_preflight_report_context(preflight), validation


def _report(
    request: EvaluationRequest,
    bundle: BundleReasoningResult,
    *,
    profile_contexts: tuple[ProfileProvenanceContext, ...] = (),
) -> CompatibilityReport:
    verdict = aggregate_bundle_verdict(bundle)
    return CompatibilityReport(
        tool_version=__version__,
        request=request,
        analysis_status=AnalysisStatus.COMPLETE,
        bundle=bundle,
        verdict=verdict,
        conflict_cores=extract_conflict_cores(bundle, verdict),
        profile_contexts=profile_contexts,
    )


def _retained_1_x_projection(payload: dict[str, Any], version: str) -> dict[str, Any]:
    projected = copy.deepcopy(payload)
    report_format = cast(dict[str, Any], projected["report_format"])
    report_format["schema_version"] = version
    if version == "1.0.0" and projected["scientific_result"] is not None:
        result = cast(dict[str, Any], projected["scientific_result"])
        for field in ("observations", "alignment_relationships", "profile_contexts"):
            result.pop(field)
    return projected


def _assert_report_surfaces(
    report: CompatibilityReport,
    *,
    verdict: CompatibilityVerdict | None,
    exit_code: WorkflowExitCode,
    status: AnalysisStatus = AnalysisStatus.COMPLETE,
) -> dict[str, Any]:
    serialized = render_compatibility_report_json(report)
    payload = cast(dict[str, Any], json.loads(serialized))
    validator = _jsonschema().Draft202012Validator(_schema(REPORT_SCHEMA_VERSION))
    validator.validate(payload)

    report_format = cast(dict[str, Any], payload["report_format"])
    analysis = cast(dict[str, Any], payload["analysis"])
    assert report_format["schema_version"] == "2.0.0"
    assert analysis["status"] == status.value
    assert render_compatibility_report_json(report) == serialized
    human = render_compatibility_report_human(report)
    assert workflow_exit_code(report) is exit_code

    bcf_resources = tuple(
        resource for resource in report.request.resources if resource.kind is ResourceKind.BCF
    )
    if bcf_resources:
        request_payload = cast(dict[str, Any], payload["request"])
        resources = cast(list[dict[str, Any]], request_payload["resources"])
        assert any(item["id"] == str(_PEER) and item["kind"] == "bcf" for item in resources)
        assert "(bcf" in human
        for retained_version in ("1.0.0", "1.1.0"):
            retained = _retained_1_x_projection(payload, retained_version)
            retained_validator = _jsonschema().Draft202012Validator(_schema(retained_version))
            assert list(retained_validator.iter_errors(retained))

    scientific = payload["scientific_result"]
    if verdict is None:
        assert scientific is None
        assert "- compatibility verdict: unavailable" in human
    else:
        scientific_result = cast(dict[str, Any], scientific)
        verdict_payload = cast(dict[str, Any], scientific_result["verdict"])
        assert verdict_payload["value"] == verdict.value
        assert f"- compatibility verdict: {verdict.value}" in human
    return payload


def test_scoped_bcf_report_is_conditional_and_coordinate_exact(tmp_path: Path) -> None:
    bcf = _bcf(tmp_path, sequence_name="chr1", ref="C", position=2)
    outside = _resource(_OUTSIDE, ResourceKind.BAM, Path("outside.bam"))
    request = _request(bcf, outside=outside)
    bundle, validation = _bundle(request, bcf)
    report = _report(request, bundle)

    assert validation.match_count == 1
    assert validation.mismatch_count == 0
    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
        exit_code=WorkflowExitCode.SUCCESS,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    conditions = cast(list[dict[str, Any]], scientific["conditions"])
    assert conditions[0]["kind"] == "explicit_resource_scope"
    assert conditions[0]["excluded_resource_ids"] == [str(_OUTSIDE)]


def test_incompatible_bcf_report_preserves_hard_ref_conflict(tmp_path: Path) -> None:
    bcf = _bcf(tmp_path, sequence_name="chr1", ref="T", position=2)
    request = _request(bcf)
    bundle, validation = _bundle(request, bcf)
    report = _report(request, bundle)

    assert validation.mismatch_count == 1
    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.INCOMPATIBLE,
        exit_code=WorkflowExitCode.INCOMPATIBLE,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    assert cast(list[object], scientific["findings"])
    assert cast(list[object], scientific["conflict_cores"])


def test_unresolved_bcf_report_is_complete_indeterminate(tmp_path: Path) -> None:
    bcf = _bcf(tmp_path, sequence_name="chr2", ref="C", position=2)
    request = _request(bcf)
    bundle, validation = _bundle(request, bcf)
    report = _report(request, bundle)

    assert validation.unresolved_sequence_count == 1
    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.INDETERMINATE,
        exit_code=WorkflowExitCode.INDETERMINATE,
    )
    assert report.analysis_status is AnalysisStatus.COMPLETE
    scientific = cast(dict[str, Any], payload["scientific_result"])
    verdict_payload = cast(dict[str, Any], scientific["verdict"])
    states = cast(dict[str, Any], verdict_payload["constraint_states"])
    assert cast(list[object], states["unresolved"])


def test_ucsc_profile_bcf_report_surfaces_authoritative_alias_trace(tmp_path: Path) -> None:
    bcf = _bcf(tmp_path, sequence_name="1", ref="C", position=2)
    request = _request(bcf, active_profiles=(UCSC_PREFLIGHT_PROFILE_ID,))
    bundle, profile_context, validation = _profile_bundle(request, bcf)
    report = _report(request, bundle, profile_contexts=(profile_context,))

    assert validation.match_count == 1
    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.COMPATIBLE,
        exit_code=WorkflowExitCode.SUCCESS,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    contexts = cast(list[dict[str, Any]], scientific["profile_contexts"])
    trace = cast(list[dict[str, Any]], contexts[0]["sequence_traces"])[0]
    assert trace["name_resolution_method"] == "authoritative_alias"
    assert trace["provider_target_name"] == "chr1"
    assert trace["target_resolution_state"] == "bound"


@pytest.mark.parametrize(
    ("declared_kind", "artifact_kind"),
    [
        (ResourceKind.VCF, ResourceKind.BCF),
        (ResourceKind.BCF, ResourceKind.VCF),
    ],
)
def test_variant_encoding_mismatch_reports_invalid_input(
    tmp_path: Path,
    declared_kind: ResourceKind,
    artifact_kind: ResourceKind,
) -> None:
    vcf_path = tmp_path / "variants.vcf"
    bcf_path = tmp_path / "variants.bcf"
    _write_vcf(vcf_path, sequence_name="chr1", ref="C")
    _convert_to_bcf(vcf_path, bcf_path)
    artifact_path = bcf_path if artifact_kind is ResourceKind.BCF else vcf_path
    peer = _resource(_PEER, declared_kind, artifact_path)
    request = _request(peer)

    with pytest.raises(VcfParseError) as exc_info:
        inspect_vcf_context(peer)

    assert f"declared as {declared_kind.value.upper()}" in str(exc_info.value)
    assert f"identified {artifact_kind.value.upper()}" in str(exc_info.value)
    report = CompatibilityReport(
        tool_version=__version__,
        request=request,
        analysis_status=AnalysisStatus.INVALID_INPUT,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("variant-encoding-mismatch"),
                AnalysisIssueKind.INVALID_INPUT,
                str(exc_info.value),
                (_PEER,),
            ),
        ),
    )

    payload = _assert_report_surfaces(
        report,
        verdict=None,
        exit_code=WorkflowExitCode.INVALID_INPUT,
        status=AnalysisStatus.INVALID_INPUT,
    )
    assert payload["scientific_result"] is None
