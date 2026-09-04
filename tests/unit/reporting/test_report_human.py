"""Human-readable compatibility-report rendering tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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
from refcompat.reporting import render_compatibility_report_human

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_FIXTURE = Path(__file__).parents[2] / "fixtures" / "milestone7" / "human-compatible-report.txt"


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(
        resource_id,
        kind,
        ArtifactIdentity(path=Path(f"/local/machine/{resource_id}")),
        display_name=f"{resource_id}.fixture",
    )


def _complete_report(*, length: int = 10) -> CompatibilityReport:
    request = EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope((_REFERENCE, _CONSUMER)),
    )
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence(
                "chr1",
                10,
                0,
                RefgetSequenceId("SQ." + "A" * 32),
            ),
        ),
    )
    requirement = SequenceLengthRequirement(
        RequirementId("consumer:length:chr1"),
        _CONSUMER,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        "chr1",
        length,
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


def test_human_compatible_known_answer() -> None:
    assert render_compatibility_report_human(_complete_report()) == _FIXTURE.read_text(
        encoding="utf-8"
    )


def test_human_incompatible_report_surfaces_decisive_trace() -> None:
    rendered = render_compatibility_report_human(_complete_report(length=11))

    assert "- tool version: 0.1.0.dev0" in rendered
    assert "- compatibility verdict: incompatible" in rendered
    assert "Decisive findings\n- finding:" in rendered
    assert "sequence_length_conflict" in rendered
    assert "Decisive conflict cores\n- conflict-core:" in rendered
    assert "contradiction" in rendered
    assert "  evidence: evidence:" in rendered


def test_human_invalid_input_does_not_invent_scientific_result() -> None:
    complete = _complete_report()
    report = CompatibilityReport(
        tool_version=complete.tool_version,
        request=complete.request,
        analysis_status=AnalysisStatus.INVALID_INPUT,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("invalid"),
                AnalysisIssueKind.INVALID_INPUT,
                "consumer header is malformed",
                (_CONSUMER,),
            ),
        ),
    )

    rendered = render_compatibility_report_human(report)

    assert "- status: invalid_input" in rendered
    assert "- compatibility verdict: unavailable" in rendered
    assert "- verified sequence bindings: unavailable" in rendered
    assert "consumer header is malformed" in rendered
    assert "Decisive findings" not in rendered
    assert "Decisive conflict cores" not in rendered


def test_human_partial_report_keeps_nonpositive_scientific_result_and_issue() -> None:
    incompatible = _complete_report(length=11)
    report = replace(
        incompatible,
        analysis_status=AnalysisStatus.PARTIAL,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("incomplete"),
                AnalysisIssueKind.INCOMPLETE_OPERATION,
                "provider enrichment did not complete",
                (_CONSUMER,),
            ),
        ),
    )

    rendered = render_compatibility_report_human(report)

    assert "- status: partial" in rendered
    assert "- tool version: 0.1.0.dev0" in rendered
    assert "- compatibility verdict: incompatible" in rendered
    assert "provider enrichment did not complete" in rendered
    assert "Decisive findings" in rendered


def test_human_rendering_omits_machine_local_artifact_paths() -> None:
    report = _complete_report()
    rendered = render_compatibility_report_human(report)

    assert "/local/machine/" not in rendered
