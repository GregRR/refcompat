"""Compatibility constraints and their separate evaluation results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType, assert_never

from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    Requirement,
    RequirementId,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.identity import Md5Digest, RefgetSequenceId

ConstraintId = NewType("ConstraintId", str)


class ConstraintRule(StrEnum):
    """Typed rule connecting one requirement to comparable capabilities."""

    SEQUENCE_PRESENCE = "sequence_presence"
    SEQUENCE_LENGTH = "sequence_length"
    SEQUENCE_IDENTITY = "sequence_identity"
    SEQUENCE_ORDER = "sequence_order"


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


@dataclass(frozen=True, slots=True)
class CompatibilityConstraint:
    """Immutable compatibility question before evidence-backed evaluation."""

    id: ConstraintId
    requirement: Requirement
    candidate_capabilities: tuple[Capability, ...]
    rule: ConstraintRule

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("constraint ID must not be empty")
        capability_ids = tuple(capability.id for capability in self.candidate_capabilities)
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("constraint candidate capability IDs must be unique")

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
    assert_never(requirement)


def capability_is_comparable(requirement: Requirement, capability: Capability) -> bool:
    """Whether a capability belongs to the scientific dimension of a requirement."""

    if isinstance(requirement, SequencePresenceRequirement):
        return isinstance(capability, SequencePresenceCapability)
    if isinstance(requirement, SequenceLengthRequirement):
        return isinstance(capability, SequenceLengthCapability)
    if isinstance(requirement, SequenceIdentityRequirement):
        if not isinstance(capability, SequenceIdentityCapability):
            return False
        if isinstance(requirement.identity, RefgetSequenceId):
            return isinstance(capability.identity, RefgetSequenceId)
        if isinstance(requirement.identity, Md5Digest):
            return isinstance(capability.identity, Md5Digest)
        assert_never(requirement.identity)
    if isinstance(requirement, SequenceOrderRequirement):
        return isinstance(capability, SequenceOrderCapability)
    assert_never(requirement)
