"""Stable whole-bundle workflow exit-code policy tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

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
from refcompat.reporting import WorkflowExitCode, workflow_exit_code

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_EXTRA = ResourceId("extra")


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _complete_report(
    *,
    sequence_name: str = "chr1",
    length: int = 10,
    conditional: bool = False,
) -> CompatibilityReport:
    resources: tuple[Resource, ...] = (
        _resource(_REFERENCE, ResourceKind.FASTA),
        _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
    )
    if conditional:
        resources += (_resource(_EXTRA, ResourceKind.VCF),)
    request = EvaluationRequest(
        resources=resources,
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
        RequirementId("consumer:length"),
        _CONSUMER,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        sequence_name,
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


def _partial_report(report: CompatibilityReport) -> CompatibilityReport:
    return replace(
        report,
        analysis_status=AnalysisStatus.PARTIAL,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("incomplete"),
                AnalysisIssueKind.INCOMPLETE_OPERATION,
                "one requested operation did not complete",
                (_CONSUMER,),
            ),
        ),
    )


def _invalid_report() -> CompatibilityReport:
    base = _complete_report()
    return CompatibilityReport(
        tool_version=base.tool_version,
        request=base.request,
        analysis_status=AnalysisStatus.INVALID_INPUT,
        analysis_issues=(
            AnalysisIssue(
                AnalysisIssueId("invalid"),
                AnalysisIssueKind.INVALID_INPUT,
                "consumer input is malformed",
                (_CONSUMER,),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (_complete_report(), WorkflowExitCode.SUCCESS),
        (_complete_report(conditional=True), WorkflowExitCode.SUCCESS),
        (_complete_report(length=11), WorkflowExitCode.INCOMPATIBLE),
        (_complete_report(sequence_name="chrX"), WorkflowExitCode.INDETERMINATE),
        (_invalid_report(), WorkflowExitCode.INVALID_INPUT),
        (_partial_report(_complete_report(length=11)), WorkflowExitCode.PARTIAL),
        (_partial_report(_complete_report(sequence_name="chrX")), WorkflowExitCode.PARTIAL),
    ],
)
def test_workflow_exit_code_preserves_report_outcome_classes(
    report: CompatibilityReport,
    expected: WorkflowExitCode,
) -> None:
    assert workflow_exit_code(report) is expected


def test_workflow_exit_codes_are_stable_numeric_contract() -> None:
    assert {item.name: item.value for item in WorkflowExitCode} == {
        "SUCCESS": 0,
        "INCOMPATIBLE": 1,
        "INVALID_INPUT": 2,
        "INDETERMINATE": 3,
        "PARTIAL": 4,
        "OPERATIONAL_FAILURE": 5,
    }


def test_operational_failure_is_reserved_for_no_report_failure() -> None:
    reports = (
        _complete_report(),
        _complete_report(conditional=True),
        _complete_report(length=11),
        _complete_report(sequence_name="chrX"),
        _invalid_report(),
        _partial_report(_complete_report(length=11)),
    )

    assert all(
        workflow_exit_code(report) is not WorkflowExitCode.OPERATIONAL_FAILURE for report in reports
    )
