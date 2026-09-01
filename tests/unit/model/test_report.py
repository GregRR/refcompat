"""Unit tests for the Milestone 7 compatibility-report root model."""

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
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityReport,
    CompatibilityVerdict,
    ConflictCoreExtraction,
    ConstraintId,
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
    VerdictAggregation,
)
from refcompat.reasoning import aggregate_bundle_verdict, extract_conflict_cores, reason_bundle

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_IDENTITY = RefgetSequenceId("SQ." + "A" * 32)
_ORIGIN = RequirementOrigin.CORE_FORMAT


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope(resource_ids=(_REFERENCE, _CONSUMER)),
    )


def _snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        resource_id=_REFERENCE,
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 10, 0, _IDENTITY),),
    )


def _requirement(
    requirement_id: str,
    *,
    length: int = 10,
    sequence_name: str = "chr1",
) -> SequenceLengthRequirement:
    return SequenceLengthRequirement(
        RequirementId(requirement_id),
        _CONSUMER,
        _ORIGIN,
        RequirementLevel.MANDATORY,
        sequence_name,
        length,
    )


def _bundle(*requirements: SequenceLengthRequirement) -> BundleReasoningResult:
    return reason_bundle(
        _request(),
        _snapshot(),
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, requirements=tuple(requirements)),
        ),
    )


def _scientific_result(
    *requirements: SequenceLengthRequirement,
) -> tuple[BundleReasoningResult, VerdictAggregation, ConflictCoreExtraction]:
    bundle = _bundle(*requirements)
    verdict = aggregate_bundle_verdict(bundle)
    cores = extract_conflict_cores(bundle, verdict)
    return bundle, verdict, cores


def _complete_report(*requirements: SequenceLengthRequirement) -> CompatibilityReport:
    bundle, verdict, cores = _scientific_result(*requirements)
    return CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=bundle.request,
        analysis_status=AnalysisStatus.COMPLETE,
        bundle=bundle,
        verdict=verdict,
        conflict_cores=cores,
    )


def _issue(
    kind: AnalysisIssueKind,
    *,
    issue_id: str = "issue",
) -> AnalysisIssue:
    return AnalysisIssue(
        id=AnalysisIssueId(issue_id),
        kind=kind,
        detail="requested operation did not complete",
        resource_ids=(_CONSUMER,),
    )


def test_complete_analysis_can_be_compatible() -> None:
    report = _complete_report(_requirement("length"))

    assert report.analysis_status is AnalysisStatus.COMPLETE
    assert report.verdict is not None
    assert report.verdict.verdict is CompatibilityVerdict.COMPATIBLE


def test_complete_analysis_can_be_indeterminate_without_becoming_partial() -> None:
    report = _complete_report(
        _requirement("missing", sequence_name="missing"),
    )

    assert report.analysis_status is AnalysisStatus.COMPLETE
    assert report.verdict is not None
    assert report.verdict.verdict is CompatibilityVerdict.INDETERMINATE
    assert report.analysis_issues == ()


def test_complete_analysis_requires_full_scientific_result_and_no_issues() -> None:
    request = _request()
    with pytest.raises(ValueError, match="requires bundle, verdict, and conflict-core"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=request,
            analysis_status=AnalysisStatus.COMPLETE,
        )

    bundle, verdict, cores = _scientific_result(_requirement("length"))
    with pytest.raises(ValueError, match="cannot carry analysis issues"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.COMPLETE,
            analysis_issues=(_issue(AnalysisIssueKind.INCOMPLETE_OPERATION),),
            bundle=bundle,
            verdict=verdict,
            conflict_cores=cores,
        )


def test_partial_analysis_requires_issue_and_never_allows_positive_verdict() -> None:
    bundle, verdict, cores = _scientific_result(_requirement("length"))

    with pytest.raises(ValueError, match="requires at least one analysis issue"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.PARTIAL,
        )

    with pytest.raises(ValueError, match="cannot carry a positive"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.PARTIAL,
            analysis_issues=(_issue(AnalysisIssueKind.INCOMPLETE_OPERATION),),
            bundle=bundle,
            verdict=verdict,
            conflict_cores=cores,
        )


def test_partial_analysis_may_preserve_independently_incompatible_result() -> None:
    bundle, verdict, cores = _scientific_result(_requirement("wrong", length=11))
    report = CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=bundle.request,
        analysis_status=AnalysisStatus.PARTIAL,
        analysis_issues=(_issue(AnalysisIssueKind.INCOMPLETE_OPERATION),),
        bundle=bundle,
        verdict=verdict,
        conflict_cores=cores,
    )

    assert report.verdict is not None
    assert report.verdict.verdict is CompatibilityVerdict.INCOMPATIBLE


def test_partial_analysis_may_preserve_indeterminate_result() -> None:
    bundle, verdict, cores = _scientific_result(_requirement("missing", sequence_name="missing"))
    report = CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=bundle.request,
        analysis_status=AnalysisStatus.PARTIAL,
        analysis_issues=(_issue(AnalysisIssueKind.INCOMPLETE_OPERATION),),
        bundle=bundle,
        verdict=verdict,
        conflict_cores=cores,
    )

    assert report.verdict is not None
    assert report.verdict.verdict is CompatibilityVerdict.INDETERMINATE


def test_partial_scientific_result_is_all_or_nothing() -> None:
    bundle, verdict, _ = _scientific_result(_requirement("missing", sequence_name="missing"))

    with pytest.raises(
        ValueError,
        match="partial analysis requires bundle, verdict, and conflict-core",
    ):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.PARTIAL,
            analysis_issues=(_issue(AnalysisIssueKind.INCOMPLETE_OPERATION),),
            bundle=bundle,
            verdict=verdict,
        )


def test_invalid_input_has_issues_but_never_a_scientific_verdict() -> None:
    report = CompatibilityReport(
        tool_version="0.1.0.dev0",
        request=_request(),
        analysis_status=AnalysisStatus.INVALID_INPUT,
        analysis_issues=(_issue(AnalysisIssueKind.INVALID_INPUT),),
    )
    assert report.verdict is None

    bundle, verdict, cores = _scientific_result(_requirement("length"))
    with pytest.raises(ValueError, match="cannot carry a scientific result"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.INVALID_INPUT,
            analysis_issues=(_issue(AnalysisIssueKind.INVALID_INPUT),),
            bundle=bundle,
            verdict=verdict,
            conflict_cores=cores,
        )


def test_analysis_issue_kind_must_match_noncomplete_status() -> None:
    with pytest.raises(ValueError, match="partial report requires incomplete-operation"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=_request(),
            analysis_status=AnalysisStatus.PARTIAL,
            analysis_issues=(_issue(AnalysisIssueKind.INVALID_INPUT),),
        )

    with pytest.raises(ValueError, match="invalid-input report requires invalid-input"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=_request(),
            analysis_status=AnalysisStatus.INVALID_INPUT,
            analysis_issues=(_issue(AnalysisIssueKind.INCOMPLETE_OPERATION),),
        )


def test_report_rejects_crosswired_bundle_request() -> None:
    bundle, verdict, cores = _scientific_result(_requirement("length"))
    other_request = replace(
        bundle.request,
        policy_id=None,
        active_profiles=(ProfileId("other-profile"),),
    )

    with pytest.raises(ValueError, match="bundle must match the evaluation request"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=other_request,
            analysis_status=AnalysisStatus.COMPLETE,
            bundle=bundle,
            verdict=verdict,
            conflict_cores=cores,
        )


def test_report_rejects_verdict_from_different_bundle() -> None:
    bundle, _, cores = _scientific_result(_requirement("length"))
    other_bundle, other_verdict, _ = _scientific_result(
        _requirement("missing", sequence_name="missing")
    )

    assert other_bundle.request == bundle.request
    with pytest.raises(ValueError, match="mandatory constraints do not match bundle"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.COMPLETE,
            bundle=bundle,
            verdict=other_verdict,
            conflict_cores=cores,
        )


def test_report_rejects_verdict_state_basis_not_matching_bundle() -> None:
    bundle, _verdict, cores = _scientific_result(_requirement("length"))
    synthetic_constraint = ConstraintId("synthetic")
    malformed = VerdictAggregation(
        verdict=CompatibilityVerdict.COMPATIBLE,
        mandatory_constraint_ids=(synthetic_constraint,),
        satisfied_mandatory_constraint_ids=(synthetic_constraint,),
    )

    with pytest.raises(ValueError, match="mandatory constraints do not match bundle"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.COMPLETE,
            bundle=bundle,
            verdict=malformed,
            conflict_cores=cores,
        )


def test_report_rejects_conflict_core_from_different_result() -> None:
    bundle, verdict, _ = _scientific_result(_requirement("wrong", length=11))
    other_bundle, other_verdict, other_cores = _scientific_result(
        _requirement("other-wrong", length=12)
    )
    assert other_bundle.request == bundle.request
    assert other_verdict.verdict is CompatibilityVerdict.INCOMPATIBLE

    with pytest.raises(ValueError, match="conflict-core basis does not match verdict"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.COMPLETE,
            bundle=bundle,
            verdict=verdict,
            conflict_cores=other_cores,
        )


def test_report_rejects_analysis_issue_for_unsupplied_resource() -> None:
    issue = replace(
        _issue(AnalysisIssueKind.INVALID_INPUT),
        resource_ids=(ResourceId("other"),),
    )
    with pytest.raises(ValueError, match="only scoped resources"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=_request(),
            analysis_status=AnalysisStatus.INVALID_INPUT,
            analysis_issues=(issue,),
        )


def test_report_requires_nonempty_tool_version_and_unique_issue_ids() -> None:
    request = _request()
    with pytest.raises(ValueError, match="tool version"):
        CompatibilityReport(
            tool_version="",
            request=request,
            analysis_status=AnalysisStatus.INVALID_INPUT,
            analysis_issues=(_issue(AnalysisIssueKind.INVALID_INPUT),),
        )

    issue = _issue(AnalysisIssueKind.INVALID_INPUT)
    with pytest.raises(ValueError, match="analysis issue IDs must be unique"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=request,
            analysis_status=AnalysisStatus.INVALID_INPUT,
            analysis_issues=(issue, issue),
        )


def test_analysis_issue_requires_nonempty_trace_fields() -> None:
    with pytest.raises(ValueError, match="analysis issue ID"):
        AnalysisIssue(
            id=AnalysisIssueId(""),
            kind=AnalysisIssueKind.INVALID_INPUT,
            detail="invalid FASTA",
        )
    with pytest.raises(ValueError, match="analysis issue detail"):
        AnalysisIssue(
            id=AnalysisIssueId("issue"),
            kind=AnalysisIssueKind.INVALID_INPUT,
            detail="",
        )
    with pytest.raises(ValueError, match="resource IDs must be unique"):
        AnalysisIssue(
            id=AnalysisIssueId("issue"),
            kind=AnalysisIssueKind.INVALID_INPUT,
            detail="invalid FASTA",
            resource_ids=(_REFERENCE, _REFERENCE),
        )


def test_report_rejects_crosswired_conflict_core_resource_trace() -> None:
    bundle, verdict, cores = _scientific_result(_requirement("wrong", length=11))
    core = cores.cores[0]
    malformed_core = replace(
        core,
        resource_ids=tuple(reversed(core.resource_ids)),
    )
    malformed_extraction = replace(cores, cores=(malformed_core,))

    with pytest.raises(ValueError, match="conflict-core resources do not match bundle"):
        CompatibilityReport(
            tool_version="0.1.0.dev0",
            request=bundle.request,
            analysis_status=AnalysisStatus.COMPLETE,
            bundle=bundle,
            verdict=verdict,
            conflict_cores=malformed_extraction,
        )
