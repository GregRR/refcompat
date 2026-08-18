"""Extract compact decisive conflict/evidence cores from bundle reasoning."""

from __future__ import annotations

import hashlib
import json
from typing import assert_never

from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.conflict_core import (
    ConflictCore,
    ConflictCoreExtraction,
    ConflictCoreId,
    ConflictCoreKind,
)
from refcompat.model.constraints import CompatibilityConstraint, ConstraintId
from refcompat.model.contracts import RequirementId
from refcompat.model.evidence import Evidence, EvidenceId
from refcompat.model.interpretation import CompatibilityFinding, FindingId
from refcompat.model.resources import ResourceId
from refcompat.model.verdict import CompatibilityVerdict, VerdictAggregation
from refcompat.reasoning.verdict import aggregate_bundle_verdict


def extract_conflict_cores(
    bundle: BundleReasoningResult,
    verdict: VerdictAggregation,
) -> ConflictCoreExtraction:
    """Extract only the decisive resource/evidence traces for one verdict.

    The function does not recompute scientific truth or minimize by evidence
    count. It projects the already-decided verdict basis into one compact core
    per decisive finding, excluding satisfied and advisory material.
    """

    expected = aggregate_bundle_verdict(bundle)
    if verdict != expected:
        raise ValueError("conflict-core extraction requires verdict matching the bundle")

    decisive_constraint_ids, kind = _decisive_basis(verdict)
    if not decisive_constraint_ids:
        return ConflictCoreExtraction(verdict=verdict.verdict)
    if kind is None:
        raise AssertionError("decisive verdict basis requires a conflict-core kind")

    constraints_by_id = {constraint.id: constraint for constraint in bundle.constraints}
    findings_by_id = {finding.id: finding for finding in bundle.interpretation.findings}
    evidence_by_id = {evidence.id: evidence for evidence in bundle.evidence.evidence}
    decisive = set(decisive_constraint_ids)

    cores: list[ConflictCore] = []
    for finding_id in verdict.basis_finding_ids:
        try:
            finding = findings_by_id[finding_id]
        except KeyError as exc:
            raise ValueError("verdict basis finding is absent from bundle interpretation") from exc

        core_constraint_ids = tuple(
            constraint_id for constraint_id in finding.constraint_ids if constraint_id in decisive
        )
        if not core_constraint_ids:
            raise ValueError("verdict basis finding does not cover a decisive constraint")

        core_constraints = tuple(constraints_by_id[item] for item in core_constraint_ids)
        requirement_ids = tuple(constraint.requirement.id for constraint in core_constraints)
        if not set(requirement_ids).issubset(set(finding.requirement_ids)):
            raise ValueError(
                "verdict basis finding requirement trace does not match its constraint"
            )
        evidence_ids = _core_evidence_ids(
            finding,
            core_constraint_ids,
            evidence_by_id,
        )
        resource_ids = _core_resource_ids(
            core_constraints,
            evidence_ids,
            evidence_by_id,
        )
        if not set(resource_ids).issubset(set(finding.resource_ids)):
            raise ValueError(
                "verdict basis finding resource trace does not match decisive evidence"
            )
        if kind is ConflictCoreKind.CONTRADICTION:
            evidence_constraints = {evidence_by_id[item].constraint_id for item in evidence_ids}
            if not set(core_constraint_ids).issubset(evidence_constraints):
                raise ValueError("every contradiction core constraint requires traceable evidence")
        cores.append(
            ConflictCore(
                id=_make_core_id(
                    kind=kind,
                    constraint_ids=core_constraint_ids,
                    requirement_ids=requirement_ids,
                    finding_ids=(finding.id,),
                    evidence_ids=evidence_ids,
                    resource_ids=resource_ids,
                ),
                kind=kind,
                constraint_ids=core_constraint_ids,
                requirement_ids=requirement_ids,
                finding_ids=(finding.id,),
                evidence_ids=evidence_ids,
                resource_ids=resource_ids,
            )
        )

    return ConflictCoreExtraction(
        verdict=verdict.verdict,
        decisive_constraint_ids=decisive_constraint_ids,
        cores=tuple(cores),
    )


def _decisive_basis(
    verdict: VerdictAggregation,
) -> tuple[tuple[ConstraintId, ...], ConflictCoreKind | None]:
    if verdict.verdict is CompatibilityVerdict.INCOMPATIBLE:
        return verdict.unsatisfied_mandatory_constraint_ids, ConflictCoreKind.CONTRADICTION
    if verdict.verdict is CompatibilityVerdict.INDETERMINATE:
        return verdict.unresolved_mandatory_constraint_ids, ConflictCoreKind.UNRESOLVED
    if verdict.verdict in (
        CompatibilityVerdict.COMPATIBLE,
        CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
    ):
        return (), None
    assert_never(verdict.verdict)


def _core_evidence_ids(
    finding: CompatibilityFinding,
    constraint_ids: tuple[ConstraintId, ...],
    evidence_by_id: dict[EvidenceId, Evidence],
) -> tuple[EvidenceId, ...]:
    constraint_set = set(constraint_ids)
    result: list[EvidenceId] = []
    for evidence_id in finding.evidence_ids:
        try:
            evidence = evidence_by_id[evidence_id]
        except KeyError as exc:
            raise ValueError("finding cites evidence absent from bundle evidence") from exc
        if evidence.constraint_id in constraint_set:
            result.append(evidence.id)
    return tuple(result)


def _core_resource_ids(
    constraints: tuple[CompatibilityConstraint, ...],
    evidence_ids: tuple[EvidenceId, ...],
    evidence_by_id: dict[EvidenceId, Evidence],
) -> tuple[ResourceId, ...]:
    resources: list[ResourceId] = []
    constraints_by_id = {constraint.id: constraint for constraint in constraints}

    for constraint in constraints:
        _append_unique(resources, constraint.requirement.resource_id)

    for evidence_id in evidence_ids:
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
            raise ValueError("conflict-core evidence capability is absent from its constraint")
        _append_unique(resources, capability.resource_id)

    return tuple(resources)


def _append_unique(values: list[ResourceId], value: ResourceId) -> None:
    if value not in values:
        values.append(value)


def _make_core_id(
    *,
    kind: ConflictCoreKind,
    constraint_ids: tuple[ConstraintId, ...],
    requirement_ids: tuple[RequirementId, ...],
    finding_ids: tuple[FindingId, ...],
    evidence_ids: tuple[EvidenceId, ...],
    resource_ids: tuple[ResourceId, ...],
) -> ConflictCoreId:
    payload = json.dumps(
        [
            kind.value,
            sorted(map(str, constraint_ids)),
            sorted(map(str, requirement_ids)),
            sorted(map(str, finding_ids)),
            sorted(map(str, evidence_ids)),
            sorted(map(str, resource_ids)),
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ConflictCoreId("conflict-core:" + hashlib.sha256(payload).hexdigest())
