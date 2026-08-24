"""VCF projection into format-neutral compatibility contracts and evidence."""

from __future__ import annotations

from dataclasses import dataclass

from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintState,
)
from refcompat.model.contracts import ReferenceBaseValidationCapability, ResourceContract
from refcompat.model.evidence import EvidenceAggregate
from refcompat.model.resources import ResourceId
from refcompat.model.vcf_ref import VcfRefValidationResult
from refcompat.model.vcf_ref_pattern import VcfRefConflictPatternSummary


@dataclass(frozen=True, slots=True)
class VcfContractProjection:
    """Format-neutral reasoning inputs/results derived from VCF observations.

    The VCF contract contains only typed requirements. The anchor-owned direct
    reference-base capability remains separate because it is evidence derived
    from the VCF/FASTA pair, not an intrinsic capability of the VCF resource.
    ``validation`` retains the compact format-specific local detail, while
    ``conflict_pattern`` records threshold-free VCF-specific interpretation.
    """

    vcf_resource_id: ResourceId
    fasta_resource_id: ResourceId
    contract: ResourceContract
    reference_base_capability: ReferenceBaseValidationCapability
    constraints: tuple[CompatibilityConstraint, ...]
    evaluations: tuple[ConstraintEvaluation, ...]
    evidence: EvidenceAggregate
    validation: VcfRefValidationResult
    conflict_pattern: VcfRefConflictPatternSummary

    def __post_init__(self) -> None:
        if not self.vcf_resource_id or not self.fasta_resource_id:
            raise ValueError("VCF contract projection resource IDs must not be empty")
        if self.contract.resource_id != self.vcf_resource_id:
            raise ValueError("VCF contract projection contract must belong to the VCF")
        if self.reference_base_capability.resource_id != self.fasta_resource_id:
            raise ValueError("VCF contract projection capability must belong to the FASTA anchor")
        if self.reference_base_capability.subject_resource_id != self.vcf_resource_id:
            raise ValueError("VCF contract projection capability must describe the VCF resource")
        if self.validation.vcf_resource_id != self.vcf_resource_id:
            raise ValueError("VCF contract projection validation must belong to the VCF")
        if self.validation.fasta_resource_id != self.fasta_resource_id:
            raise ValueError("VCF contract projection validation must use the FASTA anchor")
        if self.conflict_pattern.vcf_resource_id != self.vcf_resource_id:
            raise ValueError("VCF contract projection conflict pattern must belong to the VCF")
        if self.conflict_pattern.fasta_resource_id != self.fasta_resource_id:
            raise ValueError("VCF contract projection conflict pattern must use the FASTA anchor")
        if self.conflict_pattern.record_count != self.validation.record_count:
            raise ValueError(
                "VCF contract projection conflict pattern must cover validation records"
            )
        if self.conflict_pattern.mismatch_count != self.validation.mismatch_count:
            raise ValueError(
                "VCF contract projection conflict pattern mismatch count must match validation"
            )
        expected_directly_compared = self.validation.match_count + self.validation.mismatch_count
        if self.conflict_pattern.directly_compared_count != expected_directly_compared:
            raise ValueError(
                "VCF contract projection conflict pattern compared count must match validation"
            )
        expected_compared_names = tuple(
            sorted(
                summary.sequence_name
                for summary in self.validation.sequence_summaries
                if summary.match_count + summary.mismatch_count > 0
            )
        )
        if self.conflict_pattern.compared_sequence_names != expected_compared_names:
            raise ValueError(
                "VCF contract projection conflict pattern compared sequences must match validation"
            )
        expected_affected_names = tuple(
            sorted(
                summary.sequence_name
                for summary in self.validation.sequence_summaries
                if summary.mismatch_count > 0
            )
        )
        if self.conflict_pattern.affected_sequence_names != expected_affected_names:
            raise ValueError(
                "VCF contract projection conflict pattern affected sequences must match validation"
            )
        expected_pattern_unresolved = (
            self.validation.out_of_bounds_count + self.validation.unresolved_sequence_count
        )
        if self.conflict_pattern.unresolved_count != expected_pattern_unresolved:
            raise ValueError(
                "VCF contract projection conflict pattern unresolved count must match validation"
            )

        if self.reference_base_capability.checked_count != self.validation.record_count:
            raise ValueError("VCF contract projection capability must cover the validation records")
        if self.reference_base_capability.match_count != self.validation.match_count:
            raise ValueError("VCF contract projection capability match count must match validation")
        if self.reference_base_capability.mismatch_count != self.validation.mismatch_count:
            raise ValueError(
                "VCF contract projection capability mismatch count must match validation"
            )
        expected_unresolved = (
            self.validation.out_of_bounds_count + self.validation.unresolved_sequence_count
        )
        if self.reference_base_capability.unresolved_count != expected_unresolved:
            raise ValueError(
                "VCF contract projection capability unresolved count must match validation"
            )

        constraint_ids = tuple(constraint.id for constraint in self.constraints)
        evaluation_ids = tuple(evaluation.constraint_id for evaluation in self.evaluations)
        if len(set(constraint_ids)) != len(constraint_ids):
            raise ValueError("VCF contract projection constraint IDs must be unique")
        if len(set(evaluation_ids)) != len(evaluation_ids):
            raise ValueError("VCF contract projection evaluation constraint IDs must be unique")
        if set(constraint_ids) != set(evaluation_ids):
            raise ValueError("VCF contract projection requires one evaluation per constraint")

        constraint_requirements = tuple(constraint.requirement for constraint in self.constraints)
        if constraint_requirements != self.contract.requirements:
            raise ValueError(
                "VCF contract projection constraints must cover exactly the contract requirements"
            )
        if any(
            constraint.requirement.resource_id != self.vcf_resource_id
            for constraint in self.constraints
        ):
            raise ValueError("VCF contract projection constraints must belong to the VCF")

        constraints_by_id = {constraint.id: constraint for constraint in self.constraints}
        evaluations_by_id = {
            evaluation.constraint_id: evaluation for evaluation in self.evaluations
        }
        for constraint_id, evaluation in evaluations_by_id.items():
            if evaluation.requirement_id != constraints_by_id[constraint_id].requirement.id:
                raise ValueError(
                    "VCF contract projection evaluation requirement does not match constraint"
                )

        reference_base_constraints = tuple(
            constraint
            for constraint in self.constraints
            if self.reference_base_capability.id
            in {capability.id for capability in constraint.candidate_capabilities}
        )
        if len(reference_base_constraints) != 1:
            raise ValueError("VCF contract projection must cite its reference-base capability once")

        known_constraint_ids = set(constraint_ids)
        evidence_constraint_ids = {item.constraint_id for item in self.evidence.evidence}
        aggregate_constraint_ids = (
            evidence_constraint_ids
            | set(self.evidence.unresolved_constraint_ids)
            | set(self.evidence.not_applicable_constraint_ids)
        )
        if not aggregate_constraint_ids.issubset(known_constraint_ids):
            raise ValueError("VCF contract projection evidence references an unknown constraint")

        expected_unresolved_ids = {
            evaluation.constraint_id
            for evaluation in self.evaluations
            if evaluation.state is ConstraintState.UNRESOLVED
        }
        expected_not_applicable_ids = {
            evaluation.constraint_id
            for evaluation in self.evaluations
            if evaluation.state is ConstraintState.NOT_APPLICABLE
        }
        if set(self.evidence.unresolved_constraint_ids) != expected_unresolved_ids:
            raise ValueError(
                "VCF contract projection unresolved evidence state must match evaluations"
            )
        if set(self.evidence.not_applicable_constraint_ids) != expected_not_applicable_ids:
            raise ValueError(
                "VCF contract projection not-applicable evidence state must match evaluations"
            )
