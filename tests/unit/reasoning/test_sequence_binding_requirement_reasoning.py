"""Tests for explicit local-to-anchor sequence-binding requirements."""

from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    CapabilityId,
    CollectionCompleteness,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    EvidenceKind,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
    FindingKind,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SatisfactionMode,
    SequenceBinding,
    SequenceBindingId,
    SequenceBindingMethod,
    SequenceBindingRequirement,
    SequenceBindingValidationCapability,
    SequenceBindingValidationState,
    SequenceCollectionSnapshot,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SnapshotSequence,
)
from refcompat.reasoning import build_reference_context, reason_bundle

_REFERENCE = ResourceId("reference")
_PEER = ResourceId("peer")
_REFGET = RefgetSequenceId("SQ." + "A" * 32)


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            Resource(_REFERENCE, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
            Resource(_PEER, ResourceKind.VCF, ArtifactIdentity(path=Path("peer.vcf"))),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope((_REFERENCE, _PEER)),
    )


def _snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 10, 0, _REFGET),),
    )


def _requirement(local_name: str = "1") -> SequenceBindingRequirement:
    return SequenceBindingRequirement(
        RequirementId(f"binding-{local_name}"),
        _PEER,
        _REFERENCE,
        RequirementOrigin.PROFILE,
        RequirementLevel.MANDATORY,
        local_name,
    )


def _binding(
    *,
    local_name: str = "1",
    method: SequenceBindingMethod = SequenceBindingMethod.AUTHORITATIVE_NAME,
    identity: RefgetSequenceId = _REFGET,
) -> SequenceBinding:
    context = build_reference_context(_request(), _snapshot())
    anchor_identity = next(
        capability
        for capability in context.anchor_capabilities
        if isinstance(capability, SequenceIdentityCapability)
        and capability.sequence_name == "chr1"
        and capability.identity == _REFGET
    )
    return SequenceBinding(
        SequenceBindingId(f"binding:{local_name}"),
        _PEER,
        local_name,
        _REFERENCE,
        "chr1",
        method,
        (identity,),
        (anchor_identity.id,),
    )


def _capability(
    state: SequenceBindingValidationState,
    *,
    local_name: str = "1",
) -> SequenceBindingValidationCapability:
    return SequenceBindingValidationCapability(
        CapabilityId(f"binding-validation:{local_name}:{state}"),
        _REFERENCE,
        _PEER,
        local_name,
        state,
        "chr1" if state is not SequenceBindingValidationState.PROVEN_ABSENT else None,
    )


def test_binding_requirement_does_not_fall_back_to_exact_name() -> None:
    contract = ResourceContract(_PEER, requirements=(_requirement("chr1"),))

    result = reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), contract),
    )

    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.evidence.evidence == ()
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_bound_validation_and_authoritative_binding_satisfy_requirement() -> None:
    requirement = _requirement()
    binding = _binding()
    capability = _capability(SequenceBindingValidationState.BOUND)

    result = reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), ResourceContract(_PEER, requirements=(requirement,))),
        supplemental_capabilities=(capability,),
        supplemental_sequence_bindings=(binding,),
    )

    assert result.evaluations[0].state is ConstraintState.SATISFIED
    assert result.evaluations[0].satisfaction_mode is SatisfactionMode.VERIFIED_SEQUENCE_BINDING
    evidence = result.evidence.evidence[0]
    assert evidence.kind is EvidenceKind.SEQUENCE_BINDING
    assert evidence.method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING
    assert evidence.strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    assert evidence.polarity is EvidencePolarity.SUPPORTS
    assert evidence.sequence_binding_ids == (binding.id,)


def test_proven_absent_binding_target_is_hard_profile_conflict() -> None:
    requirement = _requirement()
    capability = _capability(SequenceBindingValidationState.PROVEN_ABSENT)

    result = reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), ResourceContract(_PEER, requirements=(requirement,))),
        supplemental_capabilities=(capability,),
    )

    assert result.evaluations[0].state is ConstraintState.UNSATISFIED
    evidence = result.evidence.evidence[0]
    assert evidence.kind is EvidenceKind.SEQUENCE_BINDING
    assert evidence.method is EvidenceMethod.EXHAUSTIVE_SEQUENCE_IDENTITY_ABSENCE
    assert evidence.strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert evidence.polarity is EvidencePolarity.CONTRADICTS
    assert result.interpretation.findings[0].kind is FindingKind.SEQUENCE_BINDING_CONFLICT


def test_content_conflict_binding_is_hard_profile_conflict() -> None:
    requirement = _requirement()
    chr2_identity = RefgetSequenceId("SQ." + "B" * 32)
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _REFGET),
            SnapshotSequence("chr2", 10, 1, chr2_identity),
        ),
    )
    capability = _capability(SequenceBindingValidationState.CONTENT_CONFLICT)
    peer_identity = SequenceIdentityCapability(
        CapabilityId("peer-content:1"),
        _PEER,
        "1",
        chr2_identity,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    result = reason_bundle(
        _request(),
        snapshot,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(
                _PEER,
                requirements=(requirement,),
                capabilities=(peer_identity,),
            ),
        ),
        supplemental_capabilities=(capability,),
    )

    assert len(result.sequence_bindings) == 1
    binding = result.sequence_bindings[0]
    assert binding.method is SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
    assert binding.anchor_sequence_name == "chr2"
    assert result.evaluations[0].state is ConstraintState.UNSATISFIED
    evidence = result.evidence.evidence[0]
    assert evidence.kind is EvidenceKind.SEQUENCE_BINDING
    assert evidence.method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING
    assert evidence.strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert evidence.polarity is EvidencePolarity.CONTRADICTS
    assert evidence.sequence_binding_ids == (binding.id,)
    assert result.interpretation.findings[0].kind is FindingKind.SEQUENCE_BINDING_CONFLICT


def test_proven_absent_target_can_coexist_with_other_identity_binding() -> None:
    requirement = _requirement()
    chr2_identity = RefgetSequenceId("SQ." + "B" * 32)
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _REFGET),
            SnapshotSequence("chr2", 10, 1, chr2_identity),
        ),
    )
    peer_identity = SequenceIdentityCapability(
        CapabilityId("peer-content:1"),
        _PEER,
        "1",
        chr2_identity,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    capability = _capability(SequenceBindingValidationState.PROVEN_ABSENT)

    result = reason_bundle(
        _request(),
        snapshot,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(
                _PEER,
                requirements=(requirement,),
                capabilities=(peer_identity,),
            ),
        ),
        supplemental_capabilities=(capability,),
    )

    assert len(result.sequence_bindings) == 1
    assert result.sequence_bindings[0].anchor_sequence_name == "chr2"
    assert result.evaluations[0].state is ConstraintState.UNSATISFIED
    assert result.evidence.evidence[0].method is EvidenceMethod.EXHAUSTIVE_SEQUENCE_IDENTITY_ABSENCE


def test_supplemental_authoritative_binding_requires_bound_validation() -> None:
    requirement = _requirement()
    binding = _binding()

    with pytest.raises(ValueError, match="requires one matching bound validation"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), ResourceContract(_PEER, requirements=(requirement,))),
            supplemental_sequence_bindings=(binding,),
        )


def test_supplemental_binding_requires_full_anchor_identity_resolution() -> None:
    requirement = _requirement()
    incomplete_snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _REFGET),
            SnapshotSequence("chr2", 10, 1),
        ),
    )
    context = build_reference_context(_request(), incomplete_snapshot)
    anchor_identity = next(
        capability
        for capability in context.anchor_capabilities
        if isinstance(capability, SequenceIdentityCapability)
        and capability.sequence_name == "chr1"
        and capability.identity == _REFGET
    )
    binding = SequenceBinding(
        SequenceBindingId("binding:incomplete-anchor"),
        _PEER,
        "1",
        _REFERENCE,
        "chr1",
        SequenceBindingMethod.AUTHORITATIVE_NAME,
        (_REFGET,),
        (anchor_identity.id,),
    )
    capability = _capability(SequenceBindingValidationState.BOUND)

    with pytest.raises(ValueError, match="uniquely resolve on the full anchor"):
        reason_bundle(
            _request(),
            incomplete_snapshot,
            (ResourceContract(_REFERENCE), ResourceContract(_PEER, requirements=(requirement,))),
            supplemental_capabilities=(capability,),
            supplemental_sequence_bindings=(binding,),
        )


def test_resource_contract_cannot_supply_pair_binding_validation() -> None:
    with pytest.raises(ValueError, match="pair-derived"):
        ResourceContract(
            _REFERENCE,
            capabilities=(_capability(SequenceBindingValidationState.PROVEN_ABSENT),),
        )


def test_bundle_rejects_non_authoritative_supplemental_sequence_binding() -> None:
    requirement = _requirement()
    binding = _binding(method=SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY)
    capability = _capability(SequenceBindingValidationState.BOUND)

    with pytest.raises(ValueError, match="authoritative-name method"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), ResourceContract(_PEER, requirements=(requirement,))),
            supplemental_capabilities=(capability,),
            supplemental_sequence_bindings=(binding,),
        )


def test_bundle_rejects_supplemental_binding_with_wrong_anchor_identity() -> None:
    requirement = _requirement()
    wrong_identity = RefgetSequenceId("SQ." + "B" * 32)
    binding = _binding(identity=wrong_identity)
    capability = _capability(SequenceBindingValidationState.BOUND)

    with pytest.raises(ValueError, match="identities must match"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), ResourceContract(_PEER, requirements=(requirement,))),
            supplemental_capabilities=(capability,),
            supplemental_sequence_bindings=(binding,),
        )
