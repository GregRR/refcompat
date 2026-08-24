"""Project VCF observations and direct REF validation into generic reasoning."""

from __future__ import annotations

import hashlib
import json

from refcompat.model.constraints import CompatibilityConstraint, ConstraintId
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    ResourceContract,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ResourceId
from refcompat.model.vcf import VcfContextSnapshot
from refcompat.model.vcf_contract import VcfContractProjection
from refcompat.model.vcf_ref import VcfRefValidationResult
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence
from refcompat.reasoning.vcf_ref_pattern import classify_vcf_ref_conflicts


def project_vcf_contract(
    snapshot: VcfContextSnapshot,
    validation: VcfRefValidationResult,
    reference_context: ReferenceContext,
) -> VcfContractProjection:
    """Build scalable generic requirements/evidence from exhaustive VCF facts.

    Actual CHROM usage becomes one mandatory sequence-presence requirement per
    used sequence. Exhaustive REF validation becomes one resource-level
    reference-base requirement rather than one object per VCF record. A single
    mismatch therefore remains a hard contradiction even beside many matches,
    while name/bounds cases that prevented direct comparison remain unresolved.
    """

    _validate_inputs(snapshot, validation, reference_context)

    presence_requirements = tuple(
        SequencePresenceRequirement(
            id=_requirement_id("presence", snapshot.resource_id, sequence_name),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=sequence_name,
        )
        for sequence_name in snapshot.used_sequence_names
    )
    base_requirement = ReferenceBaseRequirement(
        id=_requirement_id(
            "reference-bases",
            snapshot.resource_id,
            f"{reference_context.anchor_resource_id}:{snapshot.record_count}",
        ),
        resource_id=snapshot.resource_id,
        anchor_resource_id=reference_context.anchor_resource_id,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        record_count=snapshot.record_count,
    )
    contract = ResourceContract(
        resource_id=snapshot.resource_id,
        requirements=(*presence_requirements, base_requirement),
    )

    base_capability = ReferenceBaseValidationCapability(
        id=_reference_base_capability_id(validation),
        resource_id=validation.fasta_resource_id,
        subject_resource_id=validation.vcf_resource_id,
        checked_count=validation.record_count,
        match_count=validation.match_count,
        mismatch_count=validation.mismatch_count,
        unresolved_count=(validation.out_of_bounds_count + validation.unresolved_sequence_count),
    )

    constraints: list[CompatibilityConstraint] = []
    for requirement in presence_requirements:
        candidates = tuple(
            capability
            for capability in reference_context.anchor_capabilities
            if isinstance(capability, SequencePresenceCapability)
            and capability.sequence_name == requirement.sequence_name
        )
        constraints.append(_constraint(reference_context, requirement, candidates))
    constraints.append(_constraint(reference_context, base_requirement, (base_capability,)))

    constraint_tuple = tuple(constraints)
    evaluations = tuple(evaluate_constraint(constraint) for constraint in constraint_tuple)
    evidence = aggregate_constraint_evidence(constraint_tuple, evaluations)
    conflict_pattern = classify_vcf_ref_conflicts(validation)
    return VcfContractProjection(
        vcf_resource_id=snapshot.resource_id,
        fasta_resource_id=validation.fasta_resource_id,
        contract=contract,
        reference_base_capability=base_capability,
        constraints=constraint_tuple,
        evaluations=evaluations,
        evidence=evidence,
        validation=validation,
        conflict_pattern=conflict_pattern,
    )


def _validate_inputs(
    snapshot: VcfContextSnapshot,
    validation: VcfRefValidationResult,
    reference_context: ReferenceContext,
) -> None:
    if snapshot.resource_id != validation.vcf_resource_id:
        raise ValueError("VCF context and REF validation must belong to the same VCF resource")
    if validation.fasta_resource_id != reference_context.anchor_resource_id:
        raise ValueError("VCF REF validation must use the reference-context FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("VCF resource must be inside the reference-context scope")
    if snapshot.record_count != validation.record_count:
        raise ValueError("VCF context and REF validation record counts must match")

    usage = {item.sequence_name: item.record_count for item in snapshot.chrom_usage}
    summaries = {item.sequence_name: item.record_count for item in validation.sequence_summaries}
    if usage != summaries:
        raise ValueError("VCF context CHROM usage must match REF validation sequence coverage")


def _constraint(
    context: ReferenceContext,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
) -> CompatibilityConstraint:
    return build_constraint(
        _constraint_id(context.anchor_resource_id, requirement, candidates),
        requirement,
        candidates,
    )


def _requirement_id(kind: str, resource_id: ResourceId, value: str) -> RequirementId:
    return RequirementId(f"vcf-requirement:{_digest([kind, str(resource_id), value])}")


def _reference_base_capability_id(validation: VcfRefValidationResult) -> CapabilityId:
    problems = [
        [
            check.record.ordinal,
            check.state.value,
            check.record.sequence_name,
            check.record.position,
            check.record.ref.upper(),
            check.fasta_bases,
        ]
        for check in validation.problem_records
    ]
    return CapabilityId(
        "reference-base-capability:"
        + _digest(
            [
                str(validation.vcf_resource_id),
                str(validation.fasta_resource_id),
                validation.record_count,
                validation.match_count,
                validation.mismatch_count,
                validation.out_of_bounds_count,
                validation.unresolved_sequence_count,
                problems,
            ]
        )
    )


def _constraint_id(
    anchor_resource_id: ResourceId,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
) -> ConstraintId:
    return ConstraintId(
        "vcf-constraint:"
        + _digest(
            [
                str(anchor_resource_id),
                str(requirement.id),
                [str(capability.id) for capability in candidates],
            ]
        )
    )


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
