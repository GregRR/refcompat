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
from refcompat.model.constraints import ConstraintId, ConstraintRule, ConstraintState
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    RequirementLevel,
    SequenceIdentityCapability,
)
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.evidence import Evidence, EvidencePolarity
from refcompat.model.interpretation import ConditionKind, FindingId, FindingKind
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

    _validate_bundle_trace(request, bundle)

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


def _validate_bundle_trace(request: EvaluationRequest, bundle: BundleReasoningResult) -> None:
    """Reject dangling or cross-wired trace before it becomes report authority."""

    constraints_by_id = {constraint.id: constraint for constraint in bundle.constraints}
    evaluations_by_id = {evaluation.constraint_id: evaluation for evaluation in bundle.evaluations}

    requirements = tuple(
        requirement for contract in bundle.contracts for requirement in contract.requirements
    )
    requirement_ids = tuple(requirement.id for requirement in requirements)
    _validate_unique(requirement_ids, noun="compatibility report requirement IDs")
    requirements_by_id = {requirement.id: requirement for requirement in requirements}
    constraint_requirement_ids = tuple(
        constraint.requirement.id for constraint in bundle.constraints
    )
    if len(set(constraint_requirement_ids)) != len(constraint_requirement_ids):
        raise ValueError("compatibility report constraints must use unique requirement IDs")
    if set(constraint_requirement_ids) != set(requirement_ids):
        raise ValueError("compatibility report constraints must cover all scoped requirements")
    if any(
        requirements_by_id[constraint.requirement.id] != constraint.requirement
        for constraint in bundle.constraints
    ):
        raise ValueError("compatibility report constraint requirement is cross-wired")

    capability_index = _report_capability_index(bundle)
    bindings_by_id = {binding.id: binding for binding in bundle.sequence_bindings}
    anchor_names = {sequence.local_name for sequence in bundle.reference_context.sequences}

    for binding in bundle.sequence_bindings:
        if binding.anchor_sequence_name not in anchor_names:
            raise ValueError(
                "compatibility report sequence binding cites an unknown anchor sequence"
            )
        try:
            cited_capabilities = tuple(
                capability_index[capability_id] for capability_id in binding.capability_ids
            )
        except KeyError as exc:
            raise ValueError(
                "compatibility report sequence binding cites an unknown capability"
            ) from exc
        identity_capabilities: list[SequenceIdentityCapability] = []
        for capability in cited_capabilities:
            if not isinstance(capability, SequenceIdentityCapability):
                raise ValueError(
                    "compatibility report sequence binding must cite identity capabilities"
                )
            identity_capabilities.append(capability)
        if {capability.identity for capability in identity_capabilities} != set(
            binding.identity_values
        ):
            raise ValueError(
                "compatibility report sequence-binding identities do not match capability trace"
            )

    for constraint in bundle.constraints:
        for capability in constraint.candidate_capabilities:
            canonical = capability_index.get(capability.id)
            if canonical is None or canonical != capability:
                raise ValueError("compatibility report constraint capability is cross-wired")
        for binding in constraint.sequence_bindings:
            canonical_binding = bindings_by_id.get(binding.id)
            if canonical_binding is None or canonical_binding != binding:
                raise ValueError("compatibility report constraint sequence binding is cross-wired")

        evaluation = evaluations_by_id[constraint.id]
        if evaluation.requirement_id != constraint.requirement.id:
            raise ValueError(
                "compatibility report evaluation requirement does not match its constraint"
            )
        candidate_ids = {capability.id for capability in constraint.candidate_capabilities}
        if not set(evaluation.relevant_capability_ids).issubset(candidate_ids):
            raise ValueError(
                "compatibility report evaluation capability is absent from its constraint"
            )

    expected_unresolved = {
        evaluation.constraint_id
        for evaluation in bundle.evaluations
        if evaluation.state is ConstraintState.UNRESOLVED
    }
    if set(bundle.evidence.unresolved_constraint_ids) != expected_unresolved:
        raise ValueError(
            "compatibility report unresolved evidence basis does not match evaluations"
        )
    expected_not_applicable = {
        evaluation.constraint_id
        for evaluation in bundle.evaluations
        if evaluation.state is ConstraintState.NOT_APPLICABLE
    }
    if set(bundle.evidence.not_applicable_constraint_ids) != expected_not_applicable:
        raise ValueError(
            "compatibility report not-applicable evidence basis does not match evaluations"
        )

    evidence_by_constraint: dict[ConstraintId, list[Evidence]] = {
        constraint_id: [] for constraint_id in constraints_by_id
    }
    for item in bundle.evidence.evidence:
        evidence_constraint = constraints_by_id.get(item.constraint_id)
        if evidence_constraint is None:
            raise ValueError("compatibility report evidence cites an unknown constraint")
        if item.requirement_id != evidence_constraint.requirement.id:
            raise ValueError("compatibility report evidence requirement is cross-wired")
        candidates_by_id = {
            capability.id: capability for capability in evidence_constraint.candidate_capabilities
        }
        evidence_capability = candidates_by_id.get(item.capability_id)
        if evidence_capability is None:
            raise ValueError("compatibility report evidence capability is cross-wired")
        if set(item.source_observation_ids) != set(evidence_capability.source_observation_ids):
            raise ValueError(
                "compatibility report evidence observations do not match its capability"
            )
        binding_ids = {binding.id for binding in evidence_constraint.sequence_bindings}
        if not set(item.sequence_binding_ids).issubset(binding_ids):
            raise ValueError("compatibility report evidence sequence binding is cross-wired")
        evidence_by_constraint[item.constraint_id].append(item)

    for constraint in bundle.constraints:
        evaluation = evaluations_by_id[constraint.id]
        items = evidence_by_constraint[constraint.id]
        evidence_capability_ids = [item.capability_id for item in items]
        if len(evidence_capability_ids) != len(evaluation.relevant_capability_ids) or set(
            evidence_capability_ids
        ) != set(evaluation.relevant_capability_ids):
            raise ValueError(
                "compatibility report evidence capabilities do not match the evaluation"
            )
        if evaluation.state is ConstraintState.SATISFIED and any(
            item.polarity is not EvidencePolarity.SUPPORTS for item in items
        ):
            raise ValueError("compatibility report satisfied evaluation has contradicting evidence")
        if evaluation.state is ConstraintState.UNSATISFIED and any(
            item.polarity is not EvidencePolarity.CONTRADICTS for item in items
        ):
            raise ValueError("compatibility report unsatisfied evaluation has supporting evidence")

    supplied_resource_ids = {resource.id for resource in request.resources}
    expected_finding_constraint_ids = {
        evaluation.constraint_id
        for evaluation in bundle.evaluations
        if evaluation.state in (ConstraintState.UNSATISFIED, ConstraintState.UNRESOLVED)
    }
    finding_constraint_ids = tuple(
        constraint_id
        for finding in bundle.interpretation.findings
        for constraint_id in finding.constraint_ids
    )
    if set(finding_constraint_ids) != expected_finding_constraint_ids or len(
        set(finding_constraint_ids)
    ) != len(finding_constraint_ids):
        raise ValueError(
            "compatibility report findings must cover each failed or unresolved constraint once"
        )

    for finding in bundle.interpretation.findings:
        finding_constraints = tuple(
            constraints_by_id.get(constraint_id) for constraint_id in finding.constraint_ids
        )
        if any(constraint is None for constraint in finding_constraints):
            raise ValueError("compatibility report finding cites an unknown constraint")
        canonical_constraints = tuple(
            constraint for constraint in finding_constraints if constraint is not None
        )
        expected_requirement_ids = {
            constraint.requirement.id for constraint in canonical_constraints
        }
        if set(finding.requirement_ids) != expected_requirement_ids:
            raise ValueError("compatibility report finding requirements are cross-wired")

        expected_evidence_ids = {
            item.id
            for constraint in canonical_constraints
            for item in evidence_by_constraint[constraint.id]
        }
        if set(finding.evidence_ids) != expected_evidence_ids:
            raise ValueError("compatibility report finding evidence is cross-wired")

        expected_resource_ids = {
            constraint.requirement.resource_id for constraint in canonical_constraints
        }
        for constraint in canonical_constraints:
            relevant_capability_ids = set(evaluations_by_id[constraint.id].relevant_capability_ids)
            expected_resource_ids.update(
                capability.resource_id
                for capability in constraint.candidate_capabilities
                if capability.id in relevant_capability_ids
            )
        if set(finding.resource_ids) != expected_resource_ids:
            raise ValueError("compatibility report finding resources are cross-wired")
        if not expected_resource_ids.issubset(supplied_resource_ids):
            raise ValueError("compatibility report finding cites an unknown resource")

        finding_states = {
            evaluations_by_id[constraint.id].state for constraint in canonical_constraints
        }
        if finding.kind is FindingKind.UNRESOLVED_REQUIREMENT:
            if finding_states != {ConstraintState.UNRESOLVED}:
                raise ValueError(
                    "compatibility report unresolved finding does not match evaluation state"
                )
        elif finding_states != {ConstraintState.UNSATISFIED} or any(
            _finding_kind_for_rule(constraint.rule) is not finding.kind
            for constraint in canonical_constraints
        ):
            raise ValueError("compatibility report conflict finding is cross-wired")

    all_constraint_ids = set(constraints_by_id)
    expected_condition_kinds: set[ConditionKind] = set()
    excluded_resource_ids = supplied_resource_ids - set(request.scope.resource_ids)
    if excluded_resource_ids:
        expected_condition_kinds.add(ConditionKind.EXPLICIT_RESOURCE_SCOPE)
    if request.scope.anchor_sequence_names is not None:
        expected_condition_kinds.add(ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE)

    actual_condition_kinds = tuple(condition.kind for condition in bundle.interpretation.conditions)
    if (
        len(set(actual_condition_kinds)) != len(actual_condition_kinds)
        or set(actual_condition_kinds) != expected_condition_kinds
    ):
        raise ValueError("compatibility report scope conditions do not match the request")
    for condition in bundle.interpretation.conditions:
        if set(condition.constraint_ids) != all_constraint_ids:
            raise ValueError("compatibility report condition constraints do not match the bundle")
        if not set(condition.excluded_resource_ids).issubset(supplied_resource_ids):
            raise ValueError("compatibility report condition cites an unknown resource")
        if (
            condition.kind is ConditionKind.EXPLICIT_RESOURCE_SCOPE
            and set(condition.excluded_resource_ids) != excluded_resource_ids
        ):
            raise ValueError(
                "compatibility report resource-scope exclusions do not match the request"
            )


def _finding_kind_for_rule(rule: ConstraintRule) -> FindingKind:
    if rule is ConstraintRule.SEQUENCE_PRESENCE:
        return FindingKind.MISSING_REQUIRED_SEQUENCE
    if rule is ConstraintRule.SEQUENCE_LENGTH:
        return FindingKind.SEQUENCE_LENGTH_CONFLICT
    if rule is ConstraintRule.SEQUENCE_IDENTITY:
        return FindingKind.SEQUENCE_IDENTITY_CONFLICT
    if rule is ConstraintRule.SEQUENCE_BINDING:
        return FindingKind.SEQUENCE_BINDING_CONFLICT
    if rule is ConstraintRule.SEQUENCE_ORDER:
        return FindingKind.SEQUENCE_ORDER_CONFLICT
    if rule is ConstraintRule.COORDINATE_BOUNDS:
        return FindingKind.COORDINATE_BOUNDS_CONFLICT
    if rule is ConstraintRule.REFERENCE_BASES:
        return FindingKind.REFERENCE_BASE_CONFLICT
    assert_never(rule)


def _report_capability_index(bundle: BundleReasoningResult) -> dict[CapabilityId, Capability]:
    capabilities: list[Capability] = []
    for contract in bundle.contracts:
        capabilities.extend(contract.capabilities)
    capabilities.extend(bundle.reference_context.anchor_capabilities)
    capabilities.extend(bundle.derived_capabilities)
    capabilities.extend(bundle.supplemental_capabilities)

    capability_ids = tuple(capability.id for capability in capabilities)
    _validate_unique(capability_ids, noun="compatibility report capability IDs")
    return {capability.id: capability for capability in capabilities}


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
