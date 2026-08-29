"""Compatibility constraints and their separate evaluation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat._compat import StrEnum, assert_never
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    RequirementId,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.identity import Md5Digest, RefgetSequenceId
from refcompat.model.reference_context import SequenceBinding
from refcompat.model.resources import ResourceId

ConstraintId = NewType("ConstraintId", str)


class ConstraintRule(StrEnum):
    """Typed rule connecting one requirement to comparable capabilities."""

    SEQUENCE_PRESENCE = "sequence_presence"
    SEQUENCE_LENGTH = "sequence_length"
    SEQUENCE_IDENTITY = "sequence_identity"
    SEQUENCE_ORDER = "sequence_order"
    COORDINATE_BOUNDS = "coordinate_bounds"
    REFERENCE_BASES = "reference_bases"


class ConstraintState(StrEnum):
    """Outcome of evaluating one compatibility constraint."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class SatisfactionMode(StrEnum):
    """Mechanism by which a satisfied constraint was established."""

    EXACT = "exact"
    VERIFIED_ALIAS = "verified_alias"
    VERIFIED_SEQUENCE_IDENTITY = "verified_sequence_identity"
    VERIFIED_SUBSET = "verified_subset"
    EXHAUSTIVE_DIRECT = "exhaustive_direct"


@dataclass(frozen=True, slots=True)
class CompatibilityConstraint:
    """Immutable compatibility question before evidence-backed evaluation."""

    id: ConstraintId
    requirement: Requirement
    candidate_capabilities: tuple[Capability, ...]
    rule: ConstraintRule
    sequence_bindings: tuple[SequenceBinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("constraint ID must not be empty")
        capability_ids = tuple(capability.id for capability in self.candidate_capabilities)
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("constraint candidate capability IDs must be unique")

        binding_ids = tuple(binding.id for binding in self.sequence_bindings)
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("constraint sequence-binding IDs must be unique")
        local_names = tuple(binding.local_sequence_name for binding in self.sequence_bindings)
        if len(set(local_names)) != len(local_names):
            raise ValueError("constraint sequence bindings must map each local name at most once")
        if any(
            binding.resource_id != self.requirement.resource_id
            for binding in self.sequence_bindings
        ):
            raise ValueError("constraint sequence bindings must belong to the requirement resource")
        if any(
            not _binding_is_relevant_to_requirement(self.requirement, binding)
            for binding in self.sequence_bindings
        ):
            raise ValueError("constraint sequence bindings must address the requirement names")

        expected_rule = constraint_rule_for_requirement(self.requirement)
        if self.rule is not expected_rule:
            raise ValueError("constraint rule must match the requirement type")
        if any(
            not capability_is_comparable(self.requirement, capability)
            for capability in self.candidate_capabilities
        ):
            raise ValueError("constraint capabilities must match the requirement type")


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation:
    """Result of evaluating one immutable compatibility constraint.

    ``relevant_capability_ids`` identifies the capabilities that determined a
    satisfied or contradicted result. An unresolved evaluation may legitimately
    have none. Generalized evidence is derived separately so this result remains
    the immutable truth evaluation rather than becoming an evidence container.
    """

    constraint_id: ConstraintId
    requirement_id: RequirementId
    state: ConstraintState
    satisfaction_mode: SatisfactionMode | None = None
    relevant_capability_ids: tuple[CapabilityId, ...] = ()

    def __post_init__(self) -> None:
        if not self.constraint_id:
            raise ValueError("constraint-evaluation constraint ID must not be empty")
        if not self.requirement_id:
            raise ValueError("constraint-evaluation requirement ID must not be empty")
        if len(set(self.relevant_capability_ids)) != len(self.relevant_capability_ids):
            raise ValueError("constraint-evaluation capability IDs must be unique")

        if self.state is ConstraintState.SATISFIED:
            if self.satisfaction_mode is None:
                raise ValueError("satisfied constraint evaluation requires a satisfaction mode")
            if not self.relevant_capability_ids:
                raise ValueError("satisfied constraint evaluation requires a relevant capability")
        elif self.satisfaction_mode is not None:
            raise ValueError("only satisfied constraint evaluations may have a satisfaction mode")
        elif self.state is ConstraintState.UNSATISFIED and not self.relevant_capability_ids:
            raise ValueError("unsatisfied constraint evaluation requires a relevant capability")
        elif self.state is ConstraintState.NOT_APPLICABLE and self.relevant_capability_ids:
            raise ValueError(
                "not-applicable constraint evaluation cannot cite candidate capabilities"
            )


def constraint_rule_for_requirement(requirement: Requirement) -> ConstraintRule:
    """Return the only rule valid for one typed requirement."""

    if isinstance(requirement, SequencePresenceRequirement):
        return ConstraintRule.SEQUENCE_PRESENCE
    if isinstance(requirement, SequenceLengthRequirement):
        return ConstraintRule.SEQUENCE_LENGTH
    if isinstance(requirement, SequenceIdentityRequirement):
        return ConstraintRule.SEQUENCE_IDENTITY
    if isinstance(requirement, SequenceOrderRequirement):
        return ConstraintRule.SEQUENCE_ORDER
    if isinstance(requirement, CoordinateBoundsRequirement):
        return ConstraintRule.COORDINATE_BOUNDS
    if isinstance(requirement, ReferenceBaseRequirement):
        return ConstraintRule.REFERENCE_BASES
    assert_never(requirement)


def capability_is_comparable(requirement: Requirement, capability: Capability) -> bool:
    """Whether a capability belongs to the scientific dimension of a requirement."""

    if isinstance(requirement, SequencePresenceRequirement):
        if isinstance(capability, SequencePresenceCapability):
            return True
        return (
            isinstance(capability, SequenceIdentityAbsenceCapability)
            and capability.subject_resource_id == requirement.resource_id
            and capability.sequence_name == requirement.sequence_name
        )
    if isinstance(requirement, SequenceLengthRequirement):
        return isinstance(capability, SequenceLengthCapability)
    if isinstance(requirement, SequenceIdentityRequirement):
        if not isinstance(capability, SequenceIdentityCapability):
            return False
        if capability.provenance is not SequenceIdentityProvenance.CONTENT_DERIVED:
            return False
        if isinstance(requirement.identity, RefgetSequenceId):
            return isinstance(capability.identity, RefgetSequenceId)
        if isinstance(requirement.identity, Md5Digest):
            return isinstance(capability.identity, Md5Digest)
        assert_never(requirement.identity)
    if isinstance(requirement, SequenceOrderRequirement):
        return isinstance(capability, SequenceOrderCapability)
    if isinstance(requirement, CoordinateBoundsRequirement):
        return (
            isinstance(capability, CoordinateBoundsValidationCapability)
            and capability.resource_id == requirement.anchor_resource_id
            and capability.subject_resource_id == requirement.resource_id
            and capability.checked_count == requirement.coordinate_count
        )
    if isinstance(requirement, ReferenceBaseRequirement):
        return (
            isinstance(capability, ReferenceBaseValidationCapability)
            and capability.resource_id == requirement.anchor_resource_id
            and capability.subject_resource_id == requirement.resource_id
            and capability.checked_count == requirement.record_count
        )
    assert_never(requirement)


def projected_sequence_name(
    constraint: CompatibilityConstraint,
    local_sequence_name: str,
    candidate_resource_id: ResourceId,
) -> tuple[str, SequenceBinding | None] | None:
    """Project one requirement-local name into a candidate resource namespace.

    A verified binding takes precedence over an identical string label. Without
    a binding, the local name is projected exactly and no alias is inferred.
    """

    binding = next(
        (
            item
            for item in constraint.sequence_bindings
            if item.local_sequence_name == local_sequence_name
        ),
        None,
    )
    if binding is None:
        return local_sequence_name, None
    if binding.anchor_resource_id != candidate_resource_id:
        return None
    return binding.anchor_sequence_name, binding


def projected_sequence_order(
    constraint: CompatibilityConstraint,
    requirement: SequenceOrderRequirement,
    candidate_resource_id: ResourceId,
) -> tuple[tuple[str, ...], tuple[SequenceBinding, ...]] | None:
    """Project ordered requirement-local names into one candidate namespace."""

    projected_names: list[str] = []
    used_bindings: list[SequenceBinding] = []
    for local_name in requirement.sequence_names:
        projected = projected_sequence_name(constraint, local_name, candidate_resource_id)
        if projected is None:
            return None
        projected_name, binding = projected
        projected_names.append(projected_name)
        if binding is not None and binding.anchor_sequence_name != binding.local_sequence_name:
            used_bindings.append(binding)
    return tuple(projected_names), tuple(used_bindings)


def _binding_is_relevant_to_requirement(
    requirement: Requirement,
    binding: SequenceBinding,
) -> bool:
    if isinstance(
        requirement,
        (
            SequencePresenceRequirement,
            SequenceLengthRequirement,
            SequenceIdentityRequirement,
        ),
    ):
        return binding.local_sequence_name == requirement.sequence_name
    if isinstance(requirement, SequenceOrderRequirement):
        return binding.local_sequence_name in requirement.sequence_names
    if isinstance(requirement, (CoordinateBoundsRequirement, ReferenceBaseRequirement)):
        return False
    assert_never(requirement)
