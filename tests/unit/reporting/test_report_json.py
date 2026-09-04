"""Tests for stable and provisional Milestone 7 report JSON projections."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

from refcompat.model import (
    AnalysisIssue,
    AnalysisIssueId,
    AnalysisIssueKind,
    AnalysisStatus,
    ArtifactIdentity,
    CollectionCompleteness,
    CompatibilityReport,
    EvaluationRequest,
    EvaluationScope,
    ProfileId,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceLengthRequirement,
    SnapshotSequence,
)
from refcompat.reasoning import aggregate_bundle_verdict, extract_conflict_cores, reason_bundle
from refcompat.reporting import (
    DRAFT_REPORT_FORMAT,
    DRAFT_REPORT_REVISION,
    REPORT_FORMAT,
    REPORT_SCHEMA_VERSION,
    compatibility_report_draft_payload,
    compatibility_report_payload,
    render_compatibility_report_draft_json,
    render_compatibility_report_json,
)

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "milestone7"
_DRAFT_FIXTURE = _FIXTURE_DIR / "draft-compatible-report.json"
_STABLE_FIXTURE = _FIXTURE_DIR / "stable-compatible-report-1.0.0.json"
_STABLE_INCOMPATIBLE_FIXTURE = _FIXTURE_DIR / "stable-incompatible-report-1.0.0.json"


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(
        id=resource_id,
        kind=kind,
        artifact=ArtifactIdentity(path=Path(str(resource_id))),
    )


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope(resource_ids=(_REFERENCE, _CONSUMER)),
    )


def _complete_report(*, length: int = 10) -> CompatibilityReport:
    request = _request()
    snapshot = SequenceCollectionSnapshot(
        resource_id=_REFERENCE,
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence(
                local_name="chr1",
                length=10,
                ordinal=0,
                refget_id=RefgetSequenceId("SQ." + "A" * 32),
            ),
        ),
    )
    requirement = SequenceLengthRequirement(
        id=RequirementId("consumer:length:chr1"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=length,
    )
    bundle = reason_bundle(
        request,
        snapshot,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, requirements=(requirement,)),
        ),
    )
    verdict = aggregate_bundle_verdict(bundle)
    return CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=request,
        analysis_status=AnalysisStatus.COMPLETE,
        bundle=bundle,
        verdict=verdict,
        conflict_cores=extract_conflict_cores(bundle, verdict),
    )


def _invalid_report(*issues: AnalysisIssue) -> CompatibilityReport:
    return CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=_request(),
        analysis_status=AnalysisStatus.INVALID_INPUT,
        analysis_issues=issues,
    )


def test_stable_payload_is_self_identifying() -> None:
    payload = compatibility_report_payload(_complete_report())

    assert payload["report_format"] == {
        "name": REPORT_FORMAT,
        "schema_version": REPORT_SCHEMA_VERSION,
    }
    assert "stability" not in cast(dict[str, object], payload["report_format"])
    assert "revision" not in cast(dict[str, object], payload["report_format"])


def test_draft_payload_is_explicit_and_self_identifying() -> None:
    payload = compatibility_report_draft_payload(_complete_report())

    assert payload["report_format"] == {
        "name": DRAFT_REPORT_FORMAT,
        "stability": "draft",
        "revision": DRAFT_REPORT_REVISION,
    }
    assert "schema_version" not in payload
    assert "bundle" not in payload
    assert "reference_context" not in payload
    scientific = cast(dict[str, object], payload["scientific_result"])
    verdict = cast(dict[str, object], scientific["verdict"])
    requirements = cast(list[dict[str, object]], scientific["requirements"])
    constraints = cast(list[dict[str, object]], scientific["constraints"])
    request_payload = cast(dict[str, object], payload["request"])
    resources = cast(list[dict[str, object]], request_payload["resources"])
    artifact = cast(dict[str, object], resources[0]["artifact"])
    assert verdict["value"] == "compatible"
    assert requirements[0]["type"] == "sequence_length"
    assert constraints[0]["requirement_id"] == "consumer:length:chr1"
    assert "path" not in artifact


def test_invalid_input_serializes_without_scientific_result() -> None:
    report = _invalid_report(
        AnalysisIssue(
            id=AnalysisIssueId("bad-input"),
            kind=AnalysisIssueKind.INVALID_INPUT,
            detail="consumer header is malformed",
            resource_ids=(_CONSUMER,),
        )
    )

    payload = compatibility_report_draft_payload(report)

    assert payload["analysis"] == {
        "status": "invalid_input",
        "issues": [
            {
                "id": "bad-input",
                "kind": "invalid_input",
                "detail": "consumer header is malformed",
                "resource_ids": ["consumer"],
            }
        ],
    }
    assert payload["scientific_result"] is None


def test_issue_order_is_canonicalized_by_stable_id() -> None:
    first = AnalysisIssue(
        id=AnalysisIssueId("a"),
        kind=AnalysisIssueKind.INVALID_INPUT,
        detail="first",
    )
    second = AnalysisIssue(
        id=AnalysisIssueId("b"),
        kind=AnalysisIssueKind.INVALID_INPUT,
        detail="second",
    )

    left = render_compatibility_report_draft_json(_invalid_report(second, first))
    right = render_compatibility_report_draft_json(_invalid_report(first, second))

    assert left == right


def test_stable_rendered_json_is_utf8_deterministic_and_strict() -> None:
    report = _complete_report()

    first = render_compatibility_report_json(report)
    second = render_compatibility_report_json(report)

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first.decode("utf-8")) == compatibility_report_payload(report)


def test_rendered_json_is_utf8_deterministic_and_strict() -> None:
    report = _complete_report()

    first = render_compatibility_report_draft_json(report)
    second = render_compatibility_report_draft_json(report)

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first.decode("utf-8")) == compatibility_report_draft_payload(report)


def test_rendered_json_does_not_depend_on_local_artifact_paths() -> None:
    report = _complete_report()
    assert report.bundle is not None

    relocated_resources = tuple(
        replace(
            resource,
            artifact=replace(
                resource.artifact,
                path=Path("/different/local/root") / str(resource.id),
            ),
        )
        for resource in report.request.resources
    )
    relocated_request = replace(report.request, resources=relocated_resources)
    relocated_bundle = replace(report.bundle, request=relocated_request)
    relocated_report = replace(
        report,
        request=relocated_request,
        bundle=relocated_bundle,
    )

    assert render_compatibility_report_draft_json(relocated_report) == (
        render_compatibility_report_draft_json(report)
    )


def test_known_answer_fixture_pins_draft_bytes() -> None:
    assert render_compatibility_report_draft_json(_complete_report()) == _DRAFT_FIXTURE.read_bytes()


def test_known_answer_fixture_pins_stable_bytes() -> None:
    assert render_compatibility_report_json(_complete_report()) == _STABLE_FIXTURE.read_bytes()


def test_incompatible_known_answer_fixture_pins_stable_bytes() -> None:
    assert render_compatibility_report_json(_complete_report(length=11)) == (
        _STABLE_INCOMPATIBLE_FIXTURE.read_bytes()
    )


def test_stable_and_draft_payloads_share_only_the_report_body() -> None:
    stable = compatibility_report_payload(_complete_report())
    draft = compatibility_report_draft_payload(_complete_report())

    stable_body = {key: value for key, value in stable.items() if key != "report_format"}
    draft_body = {key: value for key, value in draft.items() if key != "report_format"}
    assert stable_body == draft_body


def test_incompatible_report_preserves_decisive_trace() -> None:
    payload = compatibility_report_draft_payload(_complete_report(length=11))
    scientific = cast(dict[str, object], payload["scientific_result"])
    verdict = cast(dict[str, object], scientific["verdict"])
    states = cast(dict[str, object], verdict["constraint_states"])
    evidence = cast(dict[str, object], scientific["evidence"])
    assert verdict["value"] == "incompatible"
    assert states["unsatisfied"]
    assert verdict["basis_finding_ids"]
    assert evidence["items"]
    assert scientific["findings"]
    assert scientific["conflict_cores"]


def test_request_resource_and_profile_order_are_preserved() -> None:
    report = _complete_report()
    request = replace(
        report.request,
        active_profiles=(ProfileId("z-profile"), ProfileId("a-profile")),
    )
    bundle = replace(report.bundle, request=request) if report.bundle is not None else None
    assert bundle is not None
    adjusted = replace(report, request=request, bundle=bundle)

    payload = compatibility_report_draft_payload(adjusted)
    request_payload = cast(dict[str, object], payload["request"])
    resources = cast(list[dict[str, object]], request_payload["resources"])
    assert request_payload["active_profiles"] == ["z-profile", "a-profile"]
    assert [item["id"] for item in resources] == ["reference", "consumer"]


def test_condition_exclusion_order_is_canonicalized() -> None:
    excluded_b = ResourceId("excluded-b")
    excluded_a = ResourceId("excluded-a")
    request = replace(
        _request(),
        resources=(
            *_request().resources,
            _resource(excluded_b, ResourceKind.VCF),
            _resource(excluded_a, ResourceKind.VCF),
        ),
    )
    snapshot = SequenceCollectionSnapshot(
        resource_id=_REFERENCE,
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence(local_name="chr1", length=10, ordinal=0),),
    )
    requirement = SequenceLengthRequirement(
        id=RequirementId("consumer:length:chr1"),
        resource_id=_CONSUMER,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=10,
    )
    bundle = reason_bundle(
        request,
        snapshot,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, requirements=(requirement,)),
        ),
    )
    verdict = aggregate_bundle_verdict(bundle)
    report = CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=request,
        analysis_status=AnalysisStatus.COMPLETE,
        bundle=bundle,
        verdict=verdict,
        conflict_cores=extract_conflict_cores(bundle, verdict),
    )

    condition = bundle.interpretation.conditions[0]
    reordered_condition = replace(
        condition,
        excluded_resource_ids=tuple(reversed(condition.excluded_resource_ids)),
    )
    reordered_bundle = replace(
        bundle,
        interpretation=replace(
            bundle.interpretation,
            conditions=(reordered_condition,),
        ),
    )
    reordered_report = replace(report, bundle=reordered_bundle)

    assert render_compatibility_report_draft_json(reordered_report) == (
        render_compatibility_report_draft_json(report)
    )
