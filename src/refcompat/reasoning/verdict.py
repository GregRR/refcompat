"""Aggregate mandatory bundle states into a categorical compatibility verdict."""

from __future__ import annotations

from typing import assert_never

from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.constraints import ConstraintEvaluation, ConstraintId, ConstraintState
from refcompat.model.contracts import RequirementLevel
from refcompat.model.interpretation import CompatibilityFinding, FindingId
from refcompat.model.verdict import CompatibilityVerdict, VerdictAggregation


def aggregate_bundle_verdict(bundle: BundleReasoningResult) -> VerdictAggregation:
    """Aggregate one validated bundle without scoring, voting, or advisory vetoes.

    Verdict precedence is intentionally categorical:

    1. any contradicted mandatory constraint -> ``INCOMPATIBLE``;
    2. otherwise any unresolved mandatory constraint -> ``INDETERMINATE``;
    3. otherwise no applicable mandatory constraint -> ``INDETERMINATE``;
    4. otherwise explicit scope conditions -> ``COMPATIBLE_WITH_CONDITIONS``;
    5. otherwise -> ``COMPATIBLE``.

    ``NOT_APPLICABLE`` mandatory constraints are neutral when at least one
    other mandatory relationship is actually satisfied. Advisory findings and
    evaluations remain available on ``bundle`` but cannot change this verdict.
    """

    evaluations_by_id = _validate_bundle_inputs(bundle)
    mandatory_constraint_ids = tuple(
        constraint.id
        for constraint in bundle.constraints
        if constraint.requirement.level is RequirementLevel.MANDATORY
    )

    satisfied: list[ConstraintId] = []
    unsatisfied: list[ConstraintId] = []
    unresolved: list[ConstraintId] = []
    not_applicable: list[ConstraintId] = []

    for constraint in bundle.constraints:
        if constraint.requirement.level is not RequirementLevel.MANDATORY:
            continue
        state = evaluations_by_id[constraint.id].state
        if state is ConstraintState.SATISFIED:
            satisfied.append(constraint.id)
        elif state is ConstraintState.UNSATISFIED:
            unsatisfied.append(constraint.id)
        elif state is ConstraintState.UNRESOLVED:
            unresolved.append(constraint.id)
        elif state is ConstraintState.NOT_APPLICABLE:
            not_applicable.append(constraint.id)
        else:
            assert_never(state)

    condition_ids = tuple(condition.id for condition in bundle.interpretation.conditions)

    if unsatisfied:
        verdict = CompatibilityVerdict.INCOMPATIBLE
        decisive_constraint_ids = tuple(unsatisfied)
    elif unresolved:
        verdict = CompatibilityVerdict.INDETERMINATE
        decisive_constraint_ids = tuple(unresolved)
    elif not satisfied:
        verdict = CompatibilityVerdict.INDETERMINATE
        decisive_constraint_ids = ()
    elif condition_ids:
        verdict = CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS
        decisive_constraint_ids = ()
    else:
        verdict = CompatibilityVerdict.COMPATIBLE
        decisive_constraint_ids = ()

    basis_finding_ids = _basis_findings(bundle.interpretation.findings, decisive_constraint_ids)
    if decisive_constraint_ids:
        _validate_decisive_findings(
            bundle.interpretation.findings,
            decisive_constraint_ids,
            basis_finding_ids,
        )

    return VerdictAggregation(
        verdict=verdict,
        mandatory_constraint_ids=mandatory_constraint_ids,
        satisfied_mandatory_constraint_ids=tuple(satisfied),
        unsatisfied_mandatory_constraint_ids=tuple(unsatisfied),
        unresolved_mandatory_constraint_ids=tuple(unresolved),
        not_applicable_mandatory_constraint_ids=tuple(not_applicable),
        condition_ids=condition_ids,
        basis_finding_ids=basis_finding_ids,
    )


def _validate_bundle_inputs(
    bundle: BundleReasoningResult,
) -> dict[ConstraintId, ConstraintEvaluation]:
    constraint_ids = tuple(constraint.id for constraint in bundle.constraints)
    evaluation_ids = tuple(evaluation.constraint_id for evaluation in bundle.evaluations)
    if len(set(constraint_ids)) != len(constraint_ids):
        raise ValueError("verdict aggregation requires unique constraint IDs")
    if len(set(evaluation_ids)) != len(evaluation_ids):
        raise ValueError("verdict aggregation requires unique evaluation constraint IDs")
    if set(constraint_ids) != set(evaluation_ids):
        raise ValueError("verdict aggregation requires exactly one evaluation per constraint")

    constraints_by_id = {constraint.id: constraint for constraint in bundle.constraints}
    evaluations_by_id = {evaluation.constraint_id: evaluation for evaluation in bundle.evaluations}
    for constraint_id, evaluation in evaluations_by_id.items():
        if evaluation.requirement_id != constraints_by_id[constraint_id].requirement.id:
            raise ValueError("verdict evaluation requirement ID does not match its constraint")

    return evaluations_by_id


def _basis_findings(
    findings: tuple[CompatibilityFinding, ...],
    decisive_constraint_ids: tuple[ConstraintId, ...],
) -> tuple[FindingId, ...]:
    decisive = set(decisive_constraint_ids)
    return tuple(
        finding.id for finding in findings if decisive.intersection(finding.constraint_ids)
    )


def _validate_decisive_findings(
    findings: tuple[CompatibilityFinding, ...],
    decisive_constraint_ids: tuple[ConstraintId, ...],
    basis_finding_ids: tuple[FindingId, ...],
) -> None:
    basis_ids = set(basis_finding_ids)
    covered = {
        constraint_id
        for finding in findings
        if finding.id in basis_ids
        for constraint_id in finding.constraint_ids
        if constraint_id in set(decisive_constraint_ids)
    }
    if covered != set(decisive_constraint_ids):
        raise ValueError("every decisive mandatory constraint must have a traceable finding")
