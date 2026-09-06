"""Milestone 7 representative end-to-end compatibility-report paths."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from refcompat import __version__
from refcompat.inspectors.alignment import inspect_alignment_header
from refcompat.inspectors.annotation import inspect_annotation_context, iter_annotation_features
from refcompat.inspectors.vcf import inspect_vcf_context, iter_vcf_ref_records
from refcompat.model import (
    AlignmentDictionaryRelationshipSummary,
    AnalysisStatus,
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityReport,
    CompatibilityVerdict,
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
    verdict: CompatibilityVerdict,
    exit_code: WorkflowExitCode,
) -> dict[str, Any]:
    serialized = render_compatibility_report_json(report)
    payload = cast(dict[str, Any], json.loads(serialized))
    schema_resource = files("refcompat.schemas").joinpath(
        f"compatibility-report-{REPORT_SCHEMA_VERSION}.schema.json"
    )
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    _jsonschema().Draft202012Validator(schema).validate(payload)

    report_format = cast(dict[str, Any], payload["report_format"])
    scientific = cast(dict[str, Any], payload["scientific_result"])
    assert report_format["schema_version"] == REPORT_SCHEMA_VERSION
    verdict_payload = cast(dict[str, Any], scientific["verdict"])
    assert verdict_payload["value"] == verdict.value
    assert render_compatibility_report_json(report) == serialized
    human = render_compatibility_report_human(report)
    assert f"- compatibility verdict: {verdict.value}" in human
    assert workflow_exit_code(report) is exit_code
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
