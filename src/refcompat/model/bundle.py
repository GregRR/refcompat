"""Anchor-driven whole-bundle reasoning result below verdict aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import assert_never
from refcompat.model.constraints import CompatibilityConstraint, ConstraintEvaluation
from refcompat.model.contracts import (
    RequirementLevel,
    ResourceContract,
    SequenceBindingValidationCapability,
    SequenceBindingValidationState,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequenceIdentityValue,
    SequencePresenceRequirement,
    SupplementalCapability,
)
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.evidence import EvidenceAggregate
from refcompat.model.identity import Md5Digest, RefgetSequenceId, SnapshotSequence
from refcompat.model.interpretation import InterpretationResult
from refcompat.model.reference_context import (
    ReferenceContext,
    SequenceBinding,
    SequenceBindingMethod,
)


@dataclass(frozen=True, slots=True)
class BundleReasoningResult:
    """Traceable v0.1 bundle reasoning before top-level verdict policy.

    This object proves that one explicit FASTA anchor drove all current typed
    constraints. Reasoner-derived pair facts such as exhaustive sequence-identity
    absence remain separate from caller-supplied pair validations such as
    coordinate, reference-base, or profile-authorized binding checks. It
    intentionally has no compatibility verdict, analysis status, conflict core,
    or stable report serialization contract.
    """

    request: EvaluationRequest
    contracts: tuple[ResourceContract, ...]
    reference_context: ReferenceContext
    sequence_bindings: tuple[SequenceBinding, ...]
    constraints: tuple[CompatibilityConstraint, ...]
    evaluations: tuple[ConstraintEvaluation, ...]
    evidence: EvidenceAggregate
    interpretation: InterpretationResult
    derived_capabilities: tuple[SequenceIdentityAbsenceCapability, ...] = ()
    supplemental_capabilities: tuple[SupplementalCapability, ...] = ()

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

        derived_ids = tuple(capability.id for capability in self.derived_capabilities)
        if len(set(derived_ids)) != len(derived_ids):
            raise ValueError("bundle derived capability IDs must be unique")
        if any(
            capability.resource_id != self.request.anchor_resource_id
            or capability.subject_resource_id not in self.request.scope.resource_ids
            or capability.subject_resource_id == self.request.anchor_resource_id
            for capability in self.derived_capabilities
        ):
            raise ValueError(
                "bundle derived absence capabilities must be anchor-owned "
                "and describe scoped peer resources"
            )

        contracts_by_id = {contract.resource_id: contract for contract in self.contracts}
        # Derived negatives are decisive Tier-A pair facts. Recheck their
        # minimum derivation invariants instead of trusting caller-built results.
        for capability in self.derived_capabilities:
            source_contract = contracts_by_id[capability.subject_resource_id]
            if not any(
                isinstance(requirement, SequencePresenceRequirement)
                and requirement.sequence_name == capability.sequence_name
                for requirement in source_contract.requirements
            ):
                raise ValueError(
                    "bundle derived absence capability must address a presence requirement"
                )

            local_content_identities = tuple(
                item
                for item in source_contract.capabilities
                if isinstance(item, SequenceIdentityCapability)
                and item.provenance is SequenceIdentityProvenance.CONTENT_DERIVED
                and item.sequence_name == capability.sequence_name
            )
            if _has_identity_scheme_conflict(local_content_identities):
                raise ValueError(
                    "bundle derived absence capability cannot use conflicting local identity"
                )
            eligible_sources = tuple(
                item
                for item in local_content_identities
                if _anchor_identity_scheme_is_complete(
                    self.reference_context.anchor_snapshot.sequences,
                    item.identity,
                )
            )
            if not eligible_sources:
                raise ValueError(
                    "bundle derived absence capability requires complete anchor identity coverage"
                )
            if any(
                _anchor_contains_identity(
                    self.reference_context.anchor_snapshot.sequences,
                    item.identity,
                )
                for item in local_content_identities
            ):
                raise ValueError(
                    "bundle derived absence identity must be absent from the complete anchor"
                )
            if {item.id for item in eligible_sources} != set(
                capability.source_identity_capability_ids
            ):
                raise ValueError(
                    "bundle derived absence capability must cite every eligible content identity "
                    "from its subject contract"
                )
            if {item.identity for item in eligible_sources} != set(capability.identity_values):
                raise ValueError(
                    "bundle derived absence identity values must match their source capabilities"
                )
            source_observation_ids = {
                observation_id
                for item in eligible_sources
                for observation_id in item.source_observation_ids
            }
            if set(capability.source_observation_ids) != source_observation_ids:
                raise ValueError(
                    "bundle derived absence observations must match their source capabilities"
                )
            if _has_redundant_identity_requirement(
                self.reference_context.sequences,
                source_contract,
                capability.sequence_name,
                eligible_sources,
            ):
                raise ValueError(
                    "bundle derived absence capability duplicates a mandatory identity conflict"
                )

        supplemental_ids = tuple(capability.id for capability in self.supplemental_capabilities)
        if len(set(supplemental_ids)) != len(supplemental_ids):
            raise ValueError("bundle supplemental capability IDs must be unique")
        if any(
            capability.resource_id != self.request.anchor_resource_id
            or capability.subject_resource_id not in self.request.scope.resource_ids
            for capability in self.supplemental_capabilities
        ):
            raise ValueError(
                "bundle supplemental capabilities must be anchor-owned "
                "and describe scoped resources"
            )

        anchor_ids = {capability.id for capability in self.reference_context.anchor_capabilities}
        if anchor_ids.intersection(supplemental_ids):
            raise ValueError("bundle anchor and supplemental capability IDs must not overlap")
        if anchor_ids.intersection(derived_ids) or set(supplemental_ids).intersection(derived_ids):
            raise ValueError(
                "bundle derived capability IDs must not overlap anchor or supplemental IDs"
            )
        allowed_capability_ids = anchor_ids | set(derived_ids) | set(supplemental_ids)
        constraint_capability_ids = {
            capability.id
            for constraint in self.constraints
            for capability in constraint.candidate_capabilities
        }
        if not constraint_capability_ids.issubset(allowed_capability_ids):
            raise ValueError(
                "bundle constraints may cite only anchor or supplemental capabilities, "
                "plus reasoner-derived absence capabilities"
            )
        if not set(derived_ids).issubset(constraint_capability_ids):
            raise ValueError("bundle derived capabilities must be used by a constraint")
        if not set(supplemental_ids).issubset(constraint_capability_ids):
            raise ValueError("bundle supplemental capabilities must be used by a constraint")

        for supplemental_capability in self.supplemental_capabilities:
            if not isinstance(supplemental_capability, SequenceBindingValidationCapability):
                continue
            matching_bindings = tuple(
                binding
                for binding in self.sequence_bindings
                if binding.resource_id == supplemental_capability.subject_resource_id
                and binding.local_sequence_name == supplemental_capability.sequence_name
                and binding.anchor_resource_id == supplemental_capability.resource_id
            )
            if supplemental_capability.state is SequenceBindingValidationState.BOUND:
                if len(matching_bindings) != 1:
                    raise ValueError(
                        "bundle bound sequence-binding capability requires one matching binding"
                    )
                if (
                    matching_bindings[0].anchor_sequence_name
                    != supplemental_capability.anchor_sequence_name
                ):
                    raise ValueError(
                        "bundle sequence-binding capability target must match its binding"
                    )
            elif supplemental_capability.state is SequenceBindingValidationState.CONTENT_CONFLICT:
                if len(matching_bindings) != 1:
                    raise ValueError(
                        "bundle content-conflict capability requires one identity-derived binding"
                    )
                binding = matching_bindings[0]
                if (
                    binding.method is not SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
                    or binding.anchor_sequence_name == supplemental_capability.anchor_sequence_name
                ):
                    raise ValueError(
                        "bundle content-conflict capability requires a different identity target"
                    )

        evidence_constraint_ids = {item.constraint_id for item in self.evidence.evidence}
        if not evidence_constraint_ids.issubset(set(constraint_ids)):
            raise ValueError("bundle evidence may reference only bundle constraints")

        for condition in self.interpretation.conditions:
            if condition.anchor_resource_id != self.request.anchor_resource_id:
                raise ValueError("bundle condition must use the request FASTA anchor")
            if condition.scope != self.request.scope:
                raise ValueError("bundle condition scope must match the evaluation request")


def _has_identity_scheme_conflict(
    capabilities: tuple[SequenceIdentityCapability, ...],
) -> bool:
    md5_values = {
        capability.identity
        for capability in capabilities
        if isinstance(capability.identity, Md5Digest)
    }
    refget_values = {
        capability.identity
        for capability in capabilities
        if isinstance(capability.identity, RefgetSequenceId)
    }
    return len(md5_values) > 1 or len(refget_values) > 1


def _anchor_identity_scheme_is_complete(
    sequences: tuple[SnapshotSequence, ...],
    identity: SequenceIdentityValue,
) -> bool:
    if isinstance(identity, Md5Digest):
        return all(sequence.md5 is not None for sequence in sequences)
    if isinstance(identity, RefgetSequenceId):
        return all(sequence.refget_id is not None for sequence in sequences)
    assert_never(identity)


def _anchor_contains_identity(
    sequences: tuple[SnapshotSequence, ...],
    identity: SequenceIdentityValue,
) -> bool:
    if isinstance(identity, Md5Digest):
        return any(sequence.md5 == identity for sequence in sequences)
    if isinstance(identity, RefgetSequenceId):
        return any(sequence.refget_id == identity for sequence in sequences)
    assert_never(identity)


def _has_redundant_identity_requirement(
    sequences: tuple[SnapshotSequence, ...],
    contract: ResourceContract,
    local_name: str,
    source_capabilities: tuple[SequenceIdentityCapability, ...],
) -> bool:
    anchor_sequence = next(
        (sequence for sequence in sequences if sequence.local_name == local_name),
        None,
    )
    if anchor_sequence is None:
        return False

    mandatory_identities = {
        requirement.identity
        for requirement in contract.requirements
        if isinstance(requirement, SequenceIdentityRequirement)
        and requirement.level is RequirementLevel.MANDATORY
        and requirement.sequence_name == local_name
    }
    return any(
        capability.identity in mandatory_identities
        and _sequence_has_identity_scheme(anchor_sequence, capability.identity)
        for capability in source_capabilities
    )


def _sequence_has_identity_scheme(
    sequence: SnapshotSequence,
    identity: SequenceIdentityValue,
) -> bool:
    if isinstance(identity, Md5Digest):
        return sequence.md5 is not None
    if isinstance(identity, RefgetSequenceId):
        return sequence.refget_id is not None
    assert_never(identity)
