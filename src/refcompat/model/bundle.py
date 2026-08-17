"""Anchor-driven whole-bundle reasoning result below verdict aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from refcompat.model.constraints import CompatibilityConstraint, ConstraintEvaluation
from refcompat.model.contracts import ResourceContract
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.evidence import EvidenceAggregate
from refcompat.model.interpretation import InterpretationResult
from refcompat.model.reference_context import ReferenceContext, SequenceBinding


@dataclass(frozen=True, slots=True)
class BundleReasoningResult:
    """Traceable v0.1 bundle reasoning before top-level verdict policy.

    This object proves that one explicit FASTA anchor drove all current typed
    constraints. It intentionally has no compatibility verdict, analysis
    status, conflict core, or stable report serialization contract.
    """

    request: EvaluationRequest
    contracts: tuple[ResourceContract, ...]
    reference_context: ReferenceContext
    sequence_bindings: tuple[SequenceBinding, ...]
    constraints: tuple[CompatibilityConstraint, ...]
    evaluations: tuple[ConstraintEvaluation, ...]
    evidence: EvidenceAggregate
    interpretation: InterpretationResult

    def __post_init__(self) -> None:
        if self.reference_context.anchor_resource_id != self.request.anchor_resource_id:
            raise ValueError("bundle reference context must use the request FASTA anchor")
        if self.reference_context.scope != self.request.scope:
            raise ValueError("bundle reference context scope must match the evaluation request")

        contract_ids = tuple(contract.resource_id for contract in self.contracts)
        if len(set(contract_ids)) != len(contract_ids):
            raise ValueError("bundle resource-contract IDs must be unique")
        if set(contract_ids) != set(self.request.scope.resource_ids):
            raise ValueError("bundle reasoning requires exactly one contract per scoped resource")

        binding_ids = tuple(binding.id for binding in self.sequence_bindings)
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("bundle sequence-binding IDs must be unique")
        if any(
            binding.anchor_resource_id != self.request.anchor_resource_id
            or binding.resource_id not in self.request.scope.resource_ids
            for binding in self.sequence_bindings
        ):
            raise ValueError("bundle sequence bindings must map scoped resources to the anchor")

        constraint_ids = tuple(constraint.id for constraint in self.constraints)
        if len(set(constraint_ids)) != len(constraint_ids):
            raise ValueError("bundle constraint IDs must be unique")
        evaluation_ids = tuple(evaluation.constraint_id for evaluation in self.evaluations)
        if len(set(evaluation_ids)) != len(evaluation_ids):
            raise ValueError("bundle evaluation constraint IDs must be unique")
        if set(constraint_ids) != set(evaluation_ids):
            raise ValueError("bundle reasoning requires exactly one evaluation per constraint")

        evidence_constraint_ids = {item.constraint_id for item in self.evidence.evidence}
        if not evidence_constraint_ids.issubset(set(constraint_ids)):
            raise ValueError("bundle evidence may reference only bundle constraints")

        for condition in self.interpretation.conditions:
            if condition.anchor_resource_id != self.request.anchor_resource_id:
                raise ValueError("bundle condition must use the request FASTA anchor")
            if condition.scope != self.request.scope:
                raise ValueError("bundle condition scope must match the evaluation request")
