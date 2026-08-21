"""Traceable qualitative evidence for compatibility reasoning.

Evidence remains qualitative. RefCompat preserves evidence strength and polarity
without converting them into a numeric compatibility score or allowing counts of
weak evidence to cancel stronger contradictions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat._compat import StrEnum
from refcompat.model.constraints import ConstraintId
from refcompat.model.contracts import CapabilityId, RequirementId
from refcompat.model.observations import ObservationId
from refcompat.model.reference_context import SequenceBindingId

EvidenceId = NewType("EvidenceId", str)


class EvidenceStrength(StrEnum):
    """Qualitative evidence tiers; these are not numeric compatibility scores."""

    TIER_A_CONCLUSIVE_CONTENT = "tier_a_conclusive_content"
    TIER_B_DIRECT_STRUCTURAL = "tier_b_direct_structural"
    TIER_C_PROVENANCE_METADATA = "tier_c_provenance_metadata"
    TIER_D_HEURISTIC_CONTEXT = "tier_d_heuristic_context"


class EvidencePolarity(StrEnum):
    """Whether a piece of evidence supports or contradicts a proposition."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class EvidenceKind(StrEnum):
    """Scientific dimension addressed by one generalized evidence item."""

    SEQUENCE_PRESENCE = "sequence_presence"
    SEQUENCE_LENGTH = "sequence_length"
    SEQUENCE_IDENTITY = "sequence_identity"
    SEQUENCE_ORDER = "sequence_order"


class EvidenceMethod(StrEnum):
    """Documented method used to derive an evidence relationship."""

    EXACT_TYPED_CONSTRAINT = "exact_typed_constraint"
    VERIFIED_SEQUENCE_BINDING = "verified_sequence_binding"


@dataclass(frozen=True, slots=True)
class Evidence:
    """One traceable support/contradiction relationship for a constraint.

    ``capability_id`` identifies the concrete candidate fact used for this
    relationship. ``source_observation_ids`` carries any observation trace
    already attached to that capability. An empty observation tuple is allowed
    while contract producers are still being introduced; it must not be
    interpreted as proof that no source observation exists.
    """

    id: EvidenceId
    kind: EvidenceKind
    method: EvidenceMethod
    strength: EvidenceStrength
    polarity: EvidencePolarity
    constraint_id: ConstraintId
    requirement_id: RequirementId
    capability_id: CapabilityId
    source_observation_ids: tuple[ObservationId, ...] = ()
    sequence_binding_ids: tuple[SequenceBindingId, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("evidence ID must not be empty")
        if not self.constraint_id:
            raise ValueError("evidence constraint ID must not be empty")
        if not self.requirement_id:
            raise ValueError("evidence requirement ID must not be empty")
        if not self.capability_id:
            raise ValueError("evidence capability ID must not be empty")
        if any(not observation_id for observation_id in self.source_observation_ids):
            raise ValueError("evidence source observation IDs must not be empty")
        if len(set(self.source_observation_ids)) != len(self.source_observation_ids):
            raise ValueError("evidence source observation IDs must be unique")
        if any(not binding_id for binding_id in self.sequence_binding_ids):
            raise ValueError("evidence sequence-binding IDs must not be empty")
        if len(set(self.sequence_binding_ids)) != len(self.sequence_binding_ids):
            raise ValueError("evidence sequence-binding IDs must be unique")
        if (
            self.method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING
            and not self.sequence_binding_ids
        ):
            raise ValueError("verified sequence-binding evidence requires a binding ID")
        if self.method is EvidenceMethod.EXACT_TYPED_CONSTRAINT and self.sequence_binding_ids:
            raise ValueError("exact typed-constraint evidence cannot cite a sequence binding")


@dataclass(frozen=True, slots=True)
class EvidenceAggregate:
    """Deterministic qualitative aggregation across constraint evaluations.

    The aggregate retains individual evidence items and unresolved/non-applicable
    constraint IDs. It intentionally exposes no numeric score and no whole-bundle
    compatibility verdict. An unresolved constraint may still carry evidence when
    its candidate facts conflict with one another.
    """

    evidence: tuple[Evidence, ...] = ()
    unresolved_constraint_ids: tuple[ConstraintId, ...] = ()
    not_applicable_constraint_ids: tuple[ConstraintId, ...] = ()

    def __post_init__(self) -> None:
        evidence_ids = tuple(item.id for item in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("aggregate evidence IDs must be unique")
        if any(not constraint_id for constraint_id in self.unresolved_constraint_ids):
            raise ValueError("aggregate unresolved constraint IDs must not be empty")
        if len(set(self.unresolved_constraint_ids)) != len(self.unresolved_constraint_ids):
            raise ValueError("aggregate unresolved constraint IDs must be unique")
        if any(not constraint_id for constraint_id in self.not_applicable_constraint_ids):
            raise ValueError("aggregate not-applicable constraint IDs must not be empty")
        if len(set(self.not_applicable_constraint_ids)) != len(self.not_applicable_constraint_ids):
            raise ValueError("aggregate not-applicable constraint IDs must be unique")
        if set(self.unresolved_constraint_ids) & set(self.not_applicable_constraint_ids):
            raise ValueError("a constraint cannot be both unresolved and not applicable")

    @property
    def supporting_evidence(self) -> tuple[Evidence, ...]:
        """Evidence items that support their associated requirements."""

        return tuple(item for item in self.evidence if item.polarity is EvidencePolarity.SUPPORTS)

    @property
    def contradicting_evidence(self) -> tuple[Evidence, ...]:
        """Evidence items that contradict their associated requirements."""

        return tuple(
            item for item in self.evidence if item.polarity is EvidencePolarity.CONTRADICTS
        )

    @property
    def conclusive_contradictions(self) -> tuple[Evidence, ...]:
        """Tier-A contradictions retained for later hard-conflict reasoning."""

        return tuple(
            item
            for item in self.evidence
            if item.polarity is EvidencePolarity.CONTRADICTS
            and item.strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
        )

    @property
    def has_conclusive_contradiction(self) -> bool:
        """Whether any Tier-A contradiction exists; this is not a bundle verdict."""

        return bool(self.conclusive_contradictions)

    def for_constraint(self, constraint_id: ConstraintId) -> tuple[Evidence, ...]:
        """Return evidence items associated with one constraint in aggregate order."""

        return tuple(item for item in self.evidence if item.constraint_id == constraint_id)
