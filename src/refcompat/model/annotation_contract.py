"""Annotation projection into format-neutral compatibility reasoning."""

from __future__ import annotations

from dataclasses import dataclass

from refcompat.model.annotation_bounds import AnnotationCoordinateValidationResult
from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintEvaluation,
    ConstraintState,
)
from refcompat.model.contracts import (
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    ResourceContract,
)
from refcompat.model.evidence import EvidenceAggregate
from refcompat.model.reference_context import SequenceBinding
from refcompat.model.resources import ResourceId


@dataclass(frozen=True, slots=True)
class AnnotationContractProjection:
    """Generic contract/evidence projection for one annotation and FASTA pair."""

    annotation_resource_id: ResourceId
    fasta_resource_id: ResourceId
    contract: ResourceContract
    sequence_bindings: tuple[SequenceBinding, ...]
    coordinate_bounds_capability: CoordinateBoundsValidationCapability
    constraints: tuple[CompatibilityConstraint, ...]
    evaluations: tuple[ConstraintEvaluation, ...]
    evidence: EvidenceAggregate
    validation: AnnotationCoordinateValidationResult

    def __post_init__(self) -> None:
        if not self.annotation_resource_id or not self.fasta_resource_id:
            raise ValueError("annotation contract projection resource IDs must not be empty")
        if self.contract.resource_id != self.annotation_resource_id:
            raise ValueError("annotation projection contract must belong to the annotation")
        if self.validation.annotation_resource_id != self.annotation_resource_id:
            raise ValueError("annotation projection validation must belong to the annotation")
        if self.validation.fasta_resource_id != self.fasta_resource_id:
            raise ValueError("annotation projection validation must use the FASTA anchor")
        binding_ids = tuple(binding.id for binding in self.sequence_bindings)
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("annotation projection sequence binding IDs must be unique")
        if tuple(sorted(binding_ids, key=str)) != self.validation.sequence_binding_ids:
            raise ValueError("annotation projection bindings must match coordinate validation")
        if any(
            binding.resource_id != self.annotation_resource_id for binding in self.sequence_bindings
        ):
            raise ValueError("annotation projection bindings must belong to the annotation")
        if any(
            binding.anchor_resource_id != self.fasta_resource_id
            for binding in self.sequence_bindings
        ):
            raise ValueError("annotation projection bindings must target the FASTA anchor")

        if self.coordinate_bounds_capability.resource_id != self.fasta_resource_id:
            raise ValueError("annotation coordinate capability must belong to the FASTA anchor")
        if self.coordinate_bounds_capability.subject_resource_id != self.annotation_resource_id:
            raise ValueError("annotation coordinate capability must describe the annotation")
        if self.coordinate_bounds_capability.checked_count != self.validation.coordinate_count:
            raise ValueError("annotation coordinate capability must cover validation statements")
        if (
            self.coordinate_bounds_capability.representable_count
            != self.validation.coordinate_representable_count
        ):
            raise ValueError("annotation coordinate capability representable count must match")
        if (
            self.coordinate_bounds_capability.conflict_count
            != self.validation.coordinate_conflict_count
        ):
            raise ValueError("annotation coordinate capability conflict count must match")
        if (
            self.coordinate_bounds_capability.unresolved_count
            != self.validation.coordinate_unresolved_count
        ):
            raise ValueError("annotation coordinate capability unresolved count must match")

        constraint_ids = tuple(constraint.id for constraint in self.constraints)
        evaluation_ids = tuple(evaluation.constraint_id for evaluation in self.evaluations)
        if len(set(constraint_ids)) != len(constraint_ids):
            raise ValueError("annotation projection constraint IDs must be unique")
        if len(set(evaluation_ids)) != len(evaluation_ids):
            raise ValueError("annotation projection evaluation IDs must be unique")
        if set(constraint_ids) != set(evaluation_ids):
            raise ValueError("annotation projection requires one evaluation per constraint")
        if (
            tuple(constraint.requirement for constraint in self.constraints)
            != self.contract.requirements
        ):
            raise ValueError("annotation projection constraints must cover contract requirements")
        if any(
            constraint.requirement.resource_id != self.annotation_resource_id
            for constraint in self.constraints
        ):
            raise ValueError("annotation projection constraints must belong to the annotation")

        constraints_by_id = {constraint.id: constraint for constraint in self.constraints}
        for evaluation in self.evaluations:
            constraint = constraints_by_id[evaluation.constraint_id]
            if evaluation.requirement_id != constraint.requirement.id:
                raise ValueError(
                    "annotation projection evaluation requirement must match its constraint"
                )

        coordinate_constraints = tuple(
            constraint
            for constraint in self.constraints
            if isinstance(constraint.requirement, CoordinateBoundsRequirement)
        )
        if len(coordinate_constraints) != 1:
            raise ValueError("annotation projection requires exactly one coordinate constraint")
        coordinate_candidate_ids = tuple(
            capability.id
            for capability in coordinate_constraints[0].candidate_capabilities
            if isinstance(capability, CoordinateBoundsValidationCapability)
        )
        if coordinate_candidate_ids != (self.coordinate_bounds_capability.id,):
            raise ValueError(
                "annotation projection must cite its coordinate capability exactly once"
            )

        known_constraint_ids = set(constraint_ids)
        evidence_constraint_ids = {item.constraint_id for item in self.evidence.evidence}
        aggregate_constraint_ids = (
            evidence_constraint_ids
            | set(self.evidence.unresolved_constraint_ids)
            | set(self.evidence.not_applicable_constraint_ids)
        )
        if not aggregate_constraint_ids.issubset(known_constraint_ids):
            raise ValueError("annotation projection evidence references an unknown constraint")

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
            raise ValueError("annotation projection unresolved evidence must match evaluations")
        if set(self.evidence.not_applicable_constraint_ids) != expected_not_applicable_ids:
            raise ValueError("annotation projection not-applicable evidence must match evaluations")
