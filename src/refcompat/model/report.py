"""Immutable whole-evaluation report root and analysis-completion status.

Milestone 7 keeps analysis execution status separate from scientific
compatibility.  This module validates that already-derived bundle, verdict, and
conflict-core values belong to one evaluation; it does not recompute reasoning
or define the stable JSON representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat._compat import StrEnum, assert_never
from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.conflict_core import ConflictCoreExtraction
from refcompat.model.constraints import ConstraintId, ConstraintState
from refcompat.model.contracts import RequirementLevel
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.interpretation import FindingId
from refcompat.model.resources import ResourceId
from refcompat.model.verdict import CompatibilityVerdict, VerdictAggregation

AnalysisIssueId = NewType("AnalysisIssueId", str)


class AnalysisStatus(StrEnum):
    """Whether the requested implemented analysis actually completed."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID_INPUT = "invalid_input"


class AnalysisIssueKind(StrEnum):
    """Why a report is not a complete scientific analysis."""

    INCOMPLETE_OPERATION = "incomplete_operation"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True, slots=True)
class AnalysisIssue:
    """One explicit execution/input issue limiting a non-complete report.

    ``detail`` is descriptive report content, not compatibility evidence.
    Resource IDs are optional because some failures affect the evaluation as a
    whole rather than one supplied artifact.
    """

    id: AnalysisIssueId
    kind: AnalysisIssueKind
    detail: str
    resource_ids: tuple[ResourceId, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("analysis issue ID must not be empty")
        if not self.detail:
            raise ValueError("analysis issue detail must not be empty")
        _validate_unique(self.resource_ids, noun="analysis issue resource IDs")


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    """Immutable root over one already-derived compatibility evaluation.

    The root keeps internal reasoning values together long enough for the M7
    reporting projection to serialize them explicitly.  Construction only
    checks cross-object consistency; it never invokes inspectors, rebuilds
    contracts, aggregates a verdict, or extracts conflict cores.

    ``bundle``/``verdict``/``conflict_cores`` are all required for a complete
    report.  A partial report may preserve a completed bundle-level scientific
    result, but that result may only be ``INCOMPATIBLE`` or ``INDETERMINATE``.
    Invalid input never carries a compatibility verdict.
    """

    tool_version: str
    request: EvaluationRequest
    analysis_status: AnalysisStatus
    analysis_issues: tuple[AnalysisIssue, ...] = ()
    bundle: BundleReasoningResult | None = None
    verdict: VerdictAggregation | None = None
    conflict_cores: ConflictCoreExtraction | None = None

    def __post_init__(self) -> None:
        if not self.tool_version:
            raise ValueError("compatibility report tool version must not be empty")

        issue_ids = tuple(issue.id for issue in self.analysis_issues)
        _validate_unique(issue_ids, noun="analysis issue IDs")
        scoped_resource_ids = set(self.request.scope.resource_ids)
        if any(
            not set(issue.resource_ids).issubset(scoped_resource_ids)
            for issue in self.analysis_issues
        ):
            raise ValueError("analysis issues may reference only scoped resources")

        if self.analysis_status is AnalysisStatus.COMPLETE:
            if self.analysis_issues:
                raise ValueError("complete analysis cannot carry analysis issues")
            self._validate_complete_scientific_result()
            return

        if not self.analysis_issues:
            raise ValueError("non-complete analysis requires at least one analysis issue")

        if self.analysis_status is AnalysisStatus.INVALID_INPUT:
            if any(
                issue.kind is not AnalysisIssueKind.INVALID_INPUT for issue in self.analysis_issues
            ):
                raise ValueError("invalid-input report requires invalid-input analysis issues")
            if any(value is not None for value in (self.bundle, self.verdict, self.conflict_cores)):
                raise ValueError("invalid-input report cannot carry a scientific result")
            return

        if self.analysis_status is AnalysisStatus.PARTIAL:
            if any(
                issue.kind is not AnalysisIssueKind.INCOMPLETE_OPERATION
                for issue in self.analysis_issues
            ):
                raise ValueError("partial report requires incomplete-operation issues")
            self._validate_partial_scientific_result()
            return

        assert_never(self.analysis_status)

    def _validate_complete_scientific_result(self) -> None:
        if self.bundle is None or self.verdict is None or self.conflict_cores is None:
            raise ValueError(
                "complete analysis requires bundle, verdict, and conflict-core results"
            )
        _validate_scientific_result(
            self.request,
            self.bundle,
            self.verdict,
            self.conflict_cores,
        )

    def _validate_partial_scientific_result(self) -> None:
        if self.bundle is None or self.verdict is None or self.conflict_cores is None:
            raise ValueError("partial analysis requires bundle, verdict, and conflict-core results")

        assert self.bundle is not None
        assert self.verdict is not None
        assert self.conflict_cores is not None
        if self.verdict.verdict in (
            CompatibilityVerdict.COMPATIBLE,
            CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
        ):
            raise ValueError("partial analysis cannot carry a positive compatibility verdict")
        _validate_scientific_result(
            self.request,
            self.bundle,
            self.verdict,
            self.conflict_cores,
        )


def _validate_scientific_result(
    request: EvaluationRequest,
    bundle: BundleReasoningResult,
    verdict: VerdictAggregation,
    conflict_cores: ConflictCoreExtraction,
) -> None:
    if bundle.request != request:
        raise ValueError("compatibility report bundle must match the evaluation request")

    evaluations_by_id = {evaluation.constraint_id: evaluation for evaluation in bundle.evaluations}
    mandatory_constraints = tuple(
        constraint
        for constraint in bundle.constraints
        if constraint.requirement.level is RequirementLevel.MANDATORY
    )
    mandatory_constraint_ids = tuple(constraint.id for constraint in mandatory_constraints)
    if verdict.mandatory_constraint_ids != mandatory_constraint_ids:
        raise ValueError("compatibility report verdict mandatory constraints do not match bundle")

    expected_by_state = {
        state: tuple(
            constraint.id
            for constraint in mandatory_constraints
            if evaluations_by_id[constraint.id].state is state
        )
        for state in ConstraintState
    }
    state_pairs = (
        (
            verdict.satisfied_mandatory_constraint_ids,
            expected_by_state[ConstraintState.SATISFIED],
        ),
        (
            verdict.unsatisfied_mandatory_constraint_ids,
            expected_by_state[ConstraintState.UNSATISFIED],
        ),
        (
            verdict.unresolved_mandatory_constraint_ids,
            expected_by_state[ConstraintState.UNRESOLVED],
        ),
        (
            verdict.not_applicable_mandatory_constraint_ids,
            expected_by_state[ConstraintState.NOT_APPLICABLE],
        ),
    )
    if any(actual != expected for actual, expected in state_pairs):
        raise ValueError("compatibility report verdict state basis does not match bundle")

    condition_ids = tuple(condition.id for condition in bundle.interpretation.conditions)
    if verdict.condition_ids != condition_ids:
        raise ValueError("compatibility report verdict conditions do not match bundle")

    decisive_constraint_ids = _decisive_constraint_ids(verdict)
    decisive = set(decisive_constraint_ids)
    expected_basis_finding_ids = tuple(
        finding.id
        for finding in bundle.interpretation.findings
        if decisive.intersection(finding.constraint_ids)
    )
    if verdict.basis_finding_ids != expected_basis_finding_ids:
        raise ValueError("compatibility report verdict findings do not match bundle")

    if conflict_cores.verdict is not verdict.verdict:
        raise ValueError("compatibility report conflict-core verdict does not match verdict")
    if conflict_cores.decisive_constraint_ids != decisive_constraint_ids:
        raise ValueError("compatibility report conflict-core basis does not match verdict")

    _validate_conflict_core_trace(
        request,
        bundle,
        conflict_cores,
        verdict.basis_finding_ids,
    )


def _decisive_constraint_ids(verdict: VerdictAggregation) -> tuple[ConstraintId, ...]:
    if verdict.verdict is CompatibilityVerdict.INCOMPATIBLE:
        return verdict.unsatisfied_mandatory_constraint_ids
    if verdict.verdict is CompatibilityVerdict.INDETERMINATE:
        return verdict.unresolved_mandatory_constraint_ids
    if verdict.verdict in (
        CompatibilityVerdict.COMPATIBLE,
        CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
    ):
        return ()
    assert_never(verdict.verdict)


def _validate_conflict_core_trace(
    request: EvaluationRequest,
    bundle: BundleReasoningResult,
    extraction: ConflictCoreExtraction,
    basis_finding_ids: tuple[FindingId, ...],
) -> None:
    constraints_by_id = {constraint.id: constraint for constraint in bundle.constraints}
    findings_by_id = {finding.id: finding for finding in bundle.interpretation.findings}
    evidence_by_id = {evidence.id: evidence for evidence in bundle.evidence.evidence}
    supplied_resource_ids = {resource.id for resource in request.resources}
    core_finding_ids = {finding_id for core in extraction.cores for finding_id in core.finding_ids}
    if core_finding_ids != set(basis_finding_ids):
        raise ValueError("compatibility report conflict-core findings do not match verdict")

    for core in extraction.cores:
        if not set(core.constraint_ids).issubset(constraints_by_id):
            raise ValueError("compatibility report conflict core cites unknown constraint")

        expected_requirement_ids = tuple(
            constraints_by_id[constraint_id].requirement.id for constraint_id in core.constraint_ids
        )
        if core.requirement_ids != expected_requirement_ids:
            raise ValueError("compatibility report conflict-core requirements do not match bundle")
        if not set(core.finding_ids).issubset(findings_by_id):
            raise ValueError("compatibility report conflict core cites unknown finding")
        covered_constraints = {
            constraint_id
            for finding_id in core.finding_ids
            for constraint_id in findings_by_id[finding_id].constraint_ids
            if constraint_id in set(core.constraint_ids)
        }
        if covered_constraints != set(core.constraint_ids):
            raise ValueError("compatibility report conflict-core findings do not match bundle")

        if not set(core.evidence_ids).issubset(evidence_by_id):
            raise ValueError("compatibility report conflict core cites unknown evidence")
        expected_evidence_ids = tuple(
            evidence_id
            for finding_id in core.finding_ids
            for evidence_id in findings_by_id[finding_id].evidence_ids
            if evidence_by_id[evidence_id].constraint_id in core.constraint_ids
        )
        if core.evidence_ids != expected_evidence_ids:
            raise ValueError("compatibility report conflict-core evidence does not match bundle")

        expected_resource_ids: list[ResourceId] = []
        for constraint_id in core.constraint_ids:
            _append_unique(
                expected_resource_ids,
                constraints_by_id[constraint_id].requirement.resource_id,
            )
        for evidence_id in core.evidence_ids:
            evidence = evidence_by_id[evidence_id]
            constraint = constraints_by_id[evidence.constraint_id]
            capability = next(
                (
                    candidate
                    for candidate in constraint.candidate_capabilities
                    if candidate.id == evidence.capability_id
                ),
                None,
            )
            if capability is None:
                raise ValueError(
                    "compatibility report conflict-core capability does not match bundle"
                )
            _append_unique(expected_resource_ids, capability.resource_id)

        if core.resource_ids != tuple(expected_resource_ids):
            raise ValueError("compatibility report conflict-core resources do not match bundle")
        if not set(core.resource_ids).issubset(supplied_resource_ids):
            raise ValueError("compatibility report conflict core cites unknown resource")


def _validate_unique(values: tuple[object, ...], *, noun: str) -> None:
    if any(not value for value in values):
        raise ValueError(f"{noun} must not contain empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{noun} must be unique")


def _append_unique(values: list[ResourceId], value: ResourceId) -> None:
    if value not in values:
        values.append(value)
