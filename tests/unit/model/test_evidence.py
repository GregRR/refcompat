"""Unit tests for generalized qualitative evidence model invariants."""

from __future__ import annotations

import pytest

from refcompat.model.constraints import ConstraintId
from refcompat.model.contracts import CapabilityId, RequirementId
from refcompat.model.evidence import (
    Evidence,
    EvidenceAggregate,
    EvidenceId,
    EvidenceKind,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
)
from refcompat.model.observations import ObservationId
from refcompat.model.reference_context import SequenceBindingId


def _evidence(
    evidence_id: str,
    *,
    strength: EvidenceStrength = EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTS,
    constraint_id: str = "constraint",
) -> Evidence:
    return Evidence(
        id=EvidenceId(evidence_id),
        kind=EvidenceKind.SEQUENCE_LENGTH,
        method=EvidenceMethod.EXACT_TYPED_CONSTRAINT,
        strength=strength,
        polarity=polarity,
        constraint_id=ConstraintId(constraint_id),
        requirement_id=RequirementId("requirement"),
        capability_id=CapabilityId(f"capability-{evidence_id}"),
        source_observation_ids=(ObservationId(f"observation-{evidence_id}"),),
    )


def test_evidence_keeps_traceability_and_qualitative_classification() -> None:
    item = _evidence("e1")

    assert item.constraint_id == ConstraintId("constraint")
    assert item.source_observation_ids == (ObservationId("observation-e1"),)
    assert item.strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert item.polarity is EvidencePolarity.SUPPORTS


def test_evidence_rejects_empty_or_duplicate_trace_ids() -> None:
    with pytest.raises(ValueError, match="evidence ID"):
        Evidence(
            id=EvidenceId(""),
            kind=EvidenceKind.SEQUENCE_LENGTH,
            method=EvidenceMethod.EXACT_TYPED_CONSTRAINT,
            strength=EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            polarity=EvidencePolarity.SUPPORTS,
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("requirement"),
            capability_id=CapabilityId("capability"),
        )

    with pytest.raises(ValueError, match="observation IDs must be unique"):
        Evidence(
            id=EvidenceId("e1"),
            kind=EvidenceKind.SEQUENCE_LENGTH,
            method=EvidenceMethod.EXACT_TYPED_CONSTRAINT,
            strength=EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            polarity=EvidencePolarity.SUPPORTS,
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("requirement"),
            capability_id=CapabilityId("capability"),
            source_observation_ids=(ObservationId("same"), ObservationId("same")),
        )


def test_aggregate_preserves_support_contradiction_and_hard_conflict() -> None:
    weak_support = _evidence("support")
    hard_conflict = _evidence(
        "conflict",
        strength=EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT,
        polarity=EvidencePolarity.CONTRADICTS,
        constraint_id="identity",
    )
    aggregate = EvidenceAggregate(evidence=(weak_support, hard_conflict))

    assert aggregate.supporting_evidence == (weak_support,)
    assert aggregate.contradicting_evidence == (hard_conflict,)
    assert aggregate.conclusive_contradictions == (hard_conflict,)
    assert aggregate.has_conclusive_contradiction is True
    assert aggregate.for_constraint(ConstraintId("identity")) == (hard_conflict,)


def test_aggregate_rejects_duplicate_ids_or_conflicting_status_lists() -> None:
    item = _evidence("same")
    duplicate = Evidence(
        id=item.id,
        kind=item.kind,
        method=item.method,
        strength=item.strength,
        polarity=item.polarity,
        constraint_id=ConstraintId("other"),
        requirement_id=item.requirement_id,
        capability_id=CapabilityId("other-capability"),
    )
    with pytest.raises(ValueError, match="evidence IDs must be unique"):
        EvidenceAggregate(evidence=(item, duplicate))

    with pytest.raises(ValueError, match="both unresolved and not applicable"):
        EvidenceAggregate(
            unresolved_constraint_ids=(ConstraintId("constraint"),),
            not_applicable_constraint_ids=(ConstraintId("constraint"),),
        )

    with pytest.raises(ValueError, match="unresolved constraint IDs must not be empty"):
        EvidenceAggregate(unresolved_constraint_ids=(ConstraintId(""),))


def test_evidence_method_and_binding_trace_must_agree() -> None:
    with pytest.raises(ValueError, match="requires a binding ID"):
        Evidence(
            id=EvidenceId("bound"),
            kind=EvidenceKind.SEQUENCE_LENGTH,
            method=EvidenceMethod.VERIFIED_SEQUENCE_BINDING,
            strength=EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            polarity=EvidencePolarity.SUPPORTS,
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("requirement"),
            capability_id=CapabilityId("capability"),
        )

    with pytest.raises(ValueError, match="cannot cite a sequence binding"):
        Evidence(
            id=EvidenceId("exact"),
            kind=EvidenceKind.SEQUENCE_LENGTH,
            method=EvidenceMethod.EXACT_TYPED_CONSTRAINT,
            strength=EvidenceStrength.TIER_B_DIRECT_STRUCTURAL,
            polarity=EvidencePolarity.SUPPORTS,
            constraint_id=ConstraintId("constraint"),
            requirement_id=RequirementId("requirement"),
            capability_id=CapabilityId("capability"),
            sequence_binding_ids=(SequenceBindingId("binding"),),
        )
