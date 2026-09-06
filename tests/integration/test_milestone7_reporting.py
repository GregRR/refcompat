"""Milestone 7 representative end-to-end compatibility-report paths."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from refcompat import __version__
from refcompat.inspectors.alignment import inspect_alignment_header
from refcompat.inspectors.annotation import (
    AnnotationParseError,
    inspect_annotation_context,
    iter_annotation_features,
)
from refcompat.inspectors.vcf import inspect_vcf_context, iter_vcf_ref_records
from refcompat.model import (
    AlignmentDictionaryRelationshipSummary,
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    AnalysisIssue,
    AnalysisIssueId,
    AnalysisIssueKind,
    AnalysisStatus,
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityReport,
    CompatibilityVerdict,
    CramOfflineReferenceAction,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ProfileProvenanceContext,
    RefgetSequenceId,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceBinding,
    SequenceCollectionSnapshot,
    SequenceDictionaryRecord,
    SnapshotSequence,
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
    build_vcf_contract,
    classify_alignment_dictionary_relationship,
    derive_annotation_sequence_bindings,
    evaluate_annotation_coordinates,
    evaluate_vcf_ref_records,
    extract_conflict_cores,
    plan_cram_offline_reference,
    project_annotation_contract,
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

_FIXTURES = Path(__file__).parents[1] / "fixtures"
_M5_FIXTURES = _FIXTURES / "milestone5"
_M7_FIXTURES = _FIXTURES / "milestone7"
_FASTA = ResourceId("reference")
_PEER = ResourceId("peer")
_OUTSIDE = ResourceId("outside")
_REFGET = RefgetSequenceId("SQ." + "A" * 32)
_MD5 = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_DB = UcscDatabaseId("testDb")
_PROVIDER_CONTEXT = UcscProviderContextId("testDb@m7-slice7")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...


class _SchemaValidatorClass(Protocol):
    def __call__(self, schema: object) -> _SchemaValidator: ...


class _JsonSchemaModule(Protocol):
    Draft202012Validator: _SchemaValidatorClass


class _AlignmentWriter(Protocol):
    def close(self) -> object: ...


class _PysamAlignmentModule(Protocol):
    def AlignmentFile(self, filename: str, mode: str, **kwargs: object) -> _AlignmentWriter: ...

    def faidx(self, filename: str) -> object: ...


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


def _pysam() -> _PysamAlignmentModule:
    return cast(_PysamAlignmentModule, import_module("pysam"))


def _schema(version: str) -> dict[str, Any]:
    resource = files("refcompat.schemas").joinpath(f"compatibility-report-{version}.schema.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _defined_report_ids(payload: dict[str, Any]) -> dict[str, set[str]]:
    request = cast(dict[str, Any], payload["request"])
    resources = cast(list[dict[str, Any]], request["resources"])
    analysis = cast(dict[str, Any], payload["analysis"])
    scientific = payload["scientific_result"]
    defined: dict[str, set[str]] = {
        "resource": {str(item["id"]) for item in resources},
        "analysis_issue": {
            str(item["id"]) for item in cast(list[dict[str, Any]], analysis["issues"])
        },
        "profile": {str(value) for value in cast(list[str], request["active_profiles"])},
    }
    if scientific is None:
        return defined

    result = cast(dict[str, Any], scientific)
    direct_namespaces = {
        "requirement": "requirements",
        "capability": "capabilities",
        "sequence_binding": "sequence_bindings",
        "observation": "observations",
        "constraint": "constraints",
        "finding": "findings",
        "condition": "conditions",
        "conflict_core": "conflict_cores",
    }
    for namespace, field in direct_namespaces.items():
        defined[namespace] = {
            str(item["id"]) for item in cast(list[dict[str, Any]], result.get(field, []))
        }
    evidence = cast(dict[str, Any], result["evidence"])
    defined["evidence"] = {
        str(item["id"]) for item in cast(list[dict[str, Any]], evidence["items"])
    }
    contexts = cast(list[dict[str, Any]], result.get("profile_contexts", []))
    defined["provider_context"] = {
        str(context["provider_context_id"])
        for context in contexts
        if context["provider_context_id"] is not None
    }
    defined["provider_source"] = {
        str(source["id"])
        for context in contexts
        for source in cast(list[dict[str, Any]], context["sources"])
    }
    return defined


def _reference_namespace(key: str) -> str | None:
    if key in {"target_binding_id", "policy_id"}:
        return None
    if key == "context_id" or key.endswith("provider_context_id"):
        return "provider_context"
    for namespace in (
        "provider_source",
        "sequence_binding",
        "analysis_issue",
        "conflict_core",
        "requirement",
        "capability",
        "observation",
        "constraint",
        "evidence",
        "finding",
        "condition",
        "resource",
        "profile",
    ):
        if key == f"{namespace}_id" or key == f"{namespace}_ids":
            return namespace
        if key.endswith(f"_{namespace}_id") or key.endswith(f"_{namespace}_ids"):
            return namespace
    return None


def _assert_referentially_closed(payload: dict[str, Any]) -> None:
    defined = _defined_report_ids(payload)

    def walk(value: object, *, key: str | None = None) -> None:
        if key is not None:
            namespace = _reference_namespace(key)
            if namespace is not None:
                candidates = value if isinstance(value, list) else [value]
                unresolved = {
                    str(candidate)
                    for candidate in candidates
                    if candidate is not None and str(candidate) not in defined.get(namespace, set())
                }
                assert not unresolved, f"dangling {namespace} reference(s): {sorted(unresolved)}"
        if isinstance(value, dict):
            for child_key, child in value.items():
                if child_key != "id":
                    walk(child, key=child_key)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)


def _assert_1_0_core_compatible(payload: dict[str, Any]) -> None:
    downgraded = copy.deepcopy(payload)
    report_format = cast(dict[str, Any], downgraded["report_format"])
    report_format["schema_version"] = "1.0.0"
    scientific = downgraded["scientific_result"]
    if scientific is not None:
        result = cast(dict[str, Any], scientific)
        for field in ("observations", "alignment_relationships", "profile_contexts"):
            result.pop(field)
    _jsonschema().Draft202012Validator(_schema("1.0.0")).validate(downgraded)


def _resource(resource_id: ResourceId, kind: ResourceKind, path: Path) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path), display_name=path.name)


def _anchor_snapshot(*, length: int = 4) -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", length, 0, _REFGET, _MD5 if length == 4 else None),),
    )


def _report(
    request: EvaluationRequest,
    bundle: BundleReasoningResult,
    *,
    alignment_relationships: tuple[AlignmentDictionaryRelationshipSummary, ...] = (),
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
        alignment_relationships=alignment_relationships,
        profile_contexts=profile_contexts,
    )


def _assert_report_surfaces(
    report: CompatibilityReport,
    *,
    verdict: CompatibilityVerdict | None,
    exit_code: WorkflowExitCode,
    status: AnalysisStatus = AnalysisStatus.COMPLETE,
) -> dict[str, Any]:
    serialized = render_compatibility_report_json(report)
    payload = cast(dict[str, Any], json.loads(serialized))
    _jsonschema().Draft202012Validator(_schema(REPORT_SCHEMA_VERSION)).validate(payload)
    _assert_referentially_closed(payload)
    _assert_1_0_core_compatible(payload)

    report_format = cast(dict[str, Any], payload["report_format"])
    analysis = cast(dict[str, Any], payload["analysis"])
    assert report_format["schema_version"] == REPORT_SCHEMA_VERSION
    assert analysis["status"] == status.value
    assert render_compatibility_report_json(report) == serialized
    human = render_compatibility_report_human(report)
    assert workflow_exit_code(report) is exit_code

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


def _write_vcf(path: Path, *, sequence_name: str = "chr1", ref: str = "A") -> Resource:
    path.write_text(
        "\n".join(
            (
                "##fileformat=VCFv4.5",
                f"##contig=<ID={sequence_name},length=4>",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                f"{sequence_name}\t1\t.\t{ref}\tC\t.\tPASS\t.",
                "",
            )
        ),
        encoding="ascii",
    )
    return _resource(_PEER, ResourceKind.VCF, path)


def _vcf_bundle(
    request: EvaluationRequest,
    vcf: Resource,
    *,
    sequence_bindings: tuple[SequenceBinding, ...] = (),
) -> BundleReasoningResult:
    anchor = _anchor_snapshot()
    context = build_reference_context(request, anchor)
    snapshot = inspect_vcf_context(vcf)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_PEER,
        fasta_resource_id=_FASTA,
        records=iter_vcf_ref_records(vcf),
        reference=_Reference(),
        sequence_bindings=sequence_bindings,
    )
    projection = project_vcf_contract(
        snapshot,
        validation,
        context,
        sequence_bindings=sequence_bindings,
    )
    contracts = tuple(
        projection.contract if resource_id == _PEER else ResourceContract(resource_id)
        for resource_id in request.scope.resource_ids
    )
    return reason_bundle(
        request,
        anchor,
        contracts,
        supplemental_capabilities=(projection.reference_base_capability,),
        supplemental_sequence_bindings=sequence_bindings,
    )


def _annotation_report(fixture_name: str) -> CompatibilityReport:
    annotation = _resource(_PEER, ResourceKind.GTF, _M5_FIXTURES / fixture_name)
    anchor_resource = _resource(_FASTA, ResourceKind.FASTA, Path("reference.fa"))
    request = EvaluationRequest(
        resources=(anchor_resource, annotation),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 100 if fixture_name != "gtf_alias.gtf" else 4, 0),),
    )
    context = build_reference_context(request, anchor)
    snapshot = inspect_annotation_context(annotation)
    bindings = derive_annotation_sequence_bindings(snapshot, context)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
        bindings,
    )
    projection = project_annotation_contract(snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    return _report(request, bundle)


def _provider_source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
) -> UcscProviderSource:
    return UcscProviderSource(
        source_id,
        _DB,
        _PROVIDER_CONTEXT,
        f"fixture://milestone7/{source_id}",
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


def _write_alignment(path: Path, kind: ResourceKind, reference: Path) -> Resource:
    module = _pysam()
    header = {
        "HD": {"VN": "1.6", "SO": "coordinate"},
        "SQ": [
            {
                "SN": "chr1",
                "LN": 4,
                "M5": _MD5.value,
                "UR": reference.as_uri(),
            }
        ],
    }
    if kind is ResourceKind.BAM:
        writer = module.AlignmentFile(str(path), "wb", header=header)
    else:
        module.faidx(str(reference))
        writer = module.AlignmentFile(
            str(path),
            "wc",
            header=header,
            reference_filename=str(reference),
        )
    writer.close()
    return _resource(_PEER, kind, path)


def test_scoped_vcf_report_path_is_conditional_success(tmp_path: Path) -> None:
    vcf = _write_vcf(tmp_path / "scoped.vcf")
    anchor_resource = _resource(_FASTA, ResourceKind.FASTA, Path("reference.fa"))
    outside = _resource(_OUTSIDE, ResourceKind.BAM, Path("outside.bam"))
    request = EvaluationRequest(
        resources=(anchor_resource, vcf, outside),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
    )
    report = _report(request, _vcf_bundle(request, vcf))

    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
        exit_code=WorkflowExitCode.SUCCESS,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    conditions = cast(list[dict[str, Any]], scientific["conditions"])
    assert conditions[0]["kind"] == "explicit_resource_scope"
    assert conditions[0]["excluded_resource_ids"] == [str(_OUTSIDE)]


@pytest.mark.parametrize("kind", [ResourceKind.BAM, ResourceKind.CRAM])
def test_alignment_report_paths_surface_dictionary_relationship(
    tmp_path: Path,
    kind: ResourceKind,
) -> None:
    reference = tmp_path / "reference.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    suffix = "bam" if kind is ResourceKind.BAM else "cram"
    alignment = _write_alignment(tmp_path / f"reads.{suffix}", kind, reference)
    anchor_resource = _resource(_FASTA, ResourceKind.FASTA, reference)
    request = EvaluationRequest(
        resources=(anchor_resource, alignment),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
    )
    anchor = _anchor_snapshot()
    context = build_reference_context(request, anchor)
    snapshot = inspect_alignment_header(alignment)
    contract = build_alignment_contract(snapshot, context)
    bundle = reason_bundle(request, anchor, (ResourceContract(_FASTA), contract))
    relationship = classify_alignment_dictionary_relationship(
        snapshot,
        context,
        bundle_result=bundle,
    )
    report = _report(request, bundle, alignment_relationships=(relationship,))

    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.COMPATIBLE,
        exit_code=WorkflowExitCode.SUCCESS,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    relationships = cast(list[dict[str, Any]], scientific["alignment_relationships"])
    assert relationships[0]["membership"] == "exact"
    assert relationships[0]["naming"] == "exact"
    assert relationships[0]["content"] == "m5_verified"


def test_annotation_incompatible_report_path_keeps_decisive_trace() -> None:
    report = _annotation_report("gtf_out_of_bounds.gtf")

    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.INCOMPATIBLE,
        exit_code=WorkflowExitCode.INCOMPATIBLE,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    assert cast(list[object], scientific["findings"])
    assert cast(list[object], scientific["conflict_cores"])


def test_annotation_indeterminate_report_path_is_complete() -> None:
    report = _annotation_report("gtf_alias.gtf")

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


def test_ucsc_profile_vcf_report_path_surfaces_provider_trace(tmp_path: Path) -> None:
    vcf = _write_vcf(tmp_path / "ucsc-alias.vcf", sequence_name="1")
    anchor_resource = _resource(_FASTA, ResourceKind.FASTA, Path("reference.fa"))
    request = EvaluationRequest(
        resources=(anchor_resource, vcf),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
        active_profiles=(UCSC_PREFLIGHT_PROFILE_ID,),
    )
    anchor = _anchor_snapshot()
    context = build_reference_context(request, anchor)
    vcf_snapshot = inspect_vcf_context(vcf)
    core_contract = build_vcf_contract(vcf_snapshot, context)
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
        records=iter_vcf_ref_records(vcf),
        reference=_Reference(),
        sequence_bindings=preflight.sequence_bindings,
    )
    vcf_projection = project_vcf_contract(
        vcf_snapshot,
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
            vcf_projection.reference_base_capability,
        ),
        supplemental_sequence_bindings=preflight.supplemental_sequence_bindings,
    )
    report = _report(
        request,
        bundle,
        profile_contexts=(project_ucsc_preflight_report_context(preflight),),
    )

    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.COMPATIBLE,
        exit_code=WorkflowExitCode.SUCCESS,
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    profile_contexts = cast(list[dict[str, Any]], scientific["profile_contexts"])
    trace = cast(list[dict[str, Any]], profile_contexts[0]["sequence_traces"])[0]
    assert trace["name_resolution_method"] == "authoritative_alias"
    assert trace["provider_target_name"] == "chr1"
    assert trace["target_resolution_state"] == "bound"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_M7_FIXTURES.glob("*.json")),
    ids=lambda path: path.name,
)
def test_milestone7_report_fixtures_are_referentially_closed(fixture_path: Path) -> None:
    payload = cast(
        dict[str, Any],
        json.loads(fixture_path.read_text(encoding="utf-8")),
    )

    _assert_referentially_closed(payload)


def test_referential_closure_detects_dangling_profile_capability() -> None:
    payload = cast(
        dict[str, Any],
        json.loads(
            (_M7_FIXTURES / "stable-ucsc-content-conflict-report-1.1.0.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    scientific = cast(dict[str, Any], payload["scientific_result"])
    contexts = cast(list[dict[str, Any]], scientific["profile_contexts"])
    traces = cast(list[dict[str, Any]], contexts[0]["sequence_traces"])
    traces[0]["target_anchor_capability_ids"] = ["missing-capability"]

    with pytest.raises(AssertionError, match="dangling capability reference"):
        _assert_referentially_closed(payload)


def test_deferred_cram_reference_path_is_partial_with_retained_incompatibility() -> None:
    anchor_resource = Resource(
        _FASTA,
        ResourceKind.FASTA,
        ArtifactIdentity(Path("missing-reference.fa")),
    )
    cram_resource = Resource(
        _PEER,
        ResourceKind.CRAM,
        ArtifactIdentity(Path("reads.cram")),
    )
    request = EvaluationRequest(
        resources=(anchor_resource, cram_resource),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
    )
    anchor = _anchor_snapshot()
    context = build_reference_context(request, anchor)
    snapshot = AlignmentHeaderSnapshot(
        _PEER,
        ResourceKind.CRAM,
        AlignmentHeaderData(sequences=(SequenceDictionaryRecord("chr1", 5, _MD5),)),
    )
    contract = build_alignment_contract(snapshot, context)
    bundle = reason_bundle(request, anchor, (ResourceContract(_FASTA), contract))
    verdict = aggregate_bundle_verdict(bundle)
    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE

    plan = plan_cram_offline_reference(
        snapshot,
        context,
        request,
        bundle_result=bundle,
    )
    assert plan.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING

    relationship = classify_alignment_dictionary_relationship(
        snapshot,
        context,
        bundle_result=bundle,
    )
    report = CompatibilityReport(
        tool_version=__version__,
        request=request,
        analysis_status=AnalysisStatus.PARTIAL,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("cram-reference-dependent-decoding-deferred"),
                AnalysisIssueKind.INCOMPLETE_OPERATION,
                "reference-dependent CRAM decoding was deferred",
                (_PEER,),
            ),
        ),
        bundle=bundle,
        verdict=verdict,
        conflict_cores=extract_conflict_cores(bundle, verdict),
        alignment_relationships=(relationship,),
    )

    payload = _assert_report_surfaces(
        report,
        verdict=CompatibilityVerdict.INCOMPATIBLE,
        exit_code=WorkflowExitCode.PARTIAL,
        status=AnalysisStatus.PARTIAL,
    )
    analysis = cast(dict[str, Any], payload["analysis"])
    assert cast(list[dict[str, Any]], analysis["issues"])[0]["kind"] == "incomplete_operation"


def test_malformed_annotation_path_is_invalid_input_without_scientific_result(
    tmp_path: Path,
) -> None:
    malformed_path = tmp_path / "malformed.gtf"
    malformed_path.write_text(">chr1\nACGT\n", encoding="utf-8")
    anchor_resource = Resource(
        _FASTA,
        ResourceKind.FASTA,
        ArtifactIdentity(Path("reference.fa")),
    )
    annotation = _resource(_PEER, ResourceKind.GTF, malformed_path)
    request = EvaluationRequest(
        resources=(anchor_resource, annotation),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER)),
    )

    with pytest.raises(AnnotationParseError) as exc_info:
        inspect_annotation_context(annotation)

    report = CompatibilityReport(
        tool_version=__version__,
        request=request,
        analysis_status=AnalysisStatus.INVALID_INPUT,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("annotation-parse-error"),
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
