"""Tests for categorical whole-bundle verdict aggregation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConstraintEvaluation,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    EvidenceAggregate,
    InterpretationResult,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceLengthRequirement,
    SnapshotSequence,
)
from refcompat.reasoning import aggregate_bundle_verdict, reason_bundle

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_PEER = ResourceId("peer")
_IDENTITY = RefgetSequenceId("SQ." + "A" * 32)
_ORIGIN = RequirementOrigin.CORE_FORMAT


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request(
    *,
    include_peer: bool = False,
    names: tuple[str, ...] | None = None,
) -> EvaluationRequest:
    resources = [
        _resource(_REFERENCE, ResourceKind.FASTA),
        _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
    ]
    if include_peer:
        resources.append(_resource(_PEER, ResourceKind.SEQUENCE_DICTIONARY))
    return EvaluationRequest(
        resources=tuple(resources),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope(resource_ids=(_REFERENCE, _CONSUMER), anchor_sequence_names=names),
    )


def _snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        resource_id=_REFERENCE,
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _IDENTITY),
            SnapshotSequence("chr2", 20, 1, None),
        ),
    )


def _length_requirement(
    requirement_id: str,
    length: int,
    *,
    level: RequirementLevel = RequirementLevel.MANDATORY,
    sequence_name: str = "chr1",
) -> SequenceLengthRequirement:
    return SequenceLengthRequirement(
        RequirementId(requirement_id),
        _CONSUMER,
        _ORIGIN,
        level,
        sequence_name,
        length,
    )


def _bundle(
    *requirements: SequenceLengthRequirement,
    request: EvaluationRequest | None = None,
) -> BundleReasoningResult:
    consumer = ResourceContract(_CONSUMER, requirements=tuple(requirements))
    return reason_bundle(
        request or _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), consumer),
    )


def test_all_mandatory_satisfied_is_compatible() -> None:
    bundle = _bundle(_length_requirement("length", 10))
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.COMPATIBLE
    assert result.satisfied_mandatory_constraint_ids == (bundle.constraints[0].id,)
    assert result.basis_finding_ids == ()


def test_positive_result_with_explicit_scope_is_compatible_with_conditions() -> None:
    bundle = _bundle(
        _length_requirement("length", 10),
        request=_request(include_peer=True, names=("chr1",)),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS
    assert result.condition_ids == tuple(
        condition.id for condition in bundle.interpretation.conditions
    )


def test_mandatory_contradiction_is_incompatible_and_has_precedence() -> None:
    bundle = _bundle(
        _length_requirement("wrong", 11),
        _length_requirement("unknown", 1, sequence_name="missing"),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert result.unsatisfied_mandatory_constraint_ids == (bundle.constraints[0].id,)
    assert result.unresolved_mandatory_constraint_ids == (bundle.constraints[1].id,)
    assert result.basis_finding_ids == (bundle.interpretation.findings[0].id,)


def test_unresolved_mandatory_relationship_is_indeterminate() -> None:
    bundle = _bundle(_length_requirement("missing", 10, sequence_name="missing"))
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.INDETERMINATE
    assert result.unresolved_mandatory_constraint_ids == (bundle.constraints[0].id,)
    assert result.basis_finding_ids == (bundle.interpretation.findings[0].id,)


def test_conditions_do_not_upgrade_indeterminate_result() -> None:
    bundle = _bundle(
        _length_requirement("missing", 20, sequence_name="chr2"),
        request=_request(names=("chr1",)),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.INDETERMINATE
    assert result.condition_ids


def test_conditions_do_not_change_incompatible_precedence() -> None:
    bundle = _bundle(
        _length_requirement("wrong", 11),
        request=_request(names=("chr1",)),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert result.condition_ids


def test_advisory_unresolved_does_not_veto_satisfied_mandatory_requirement() -> None:
    bundle = _bundle(
        _length_requirement("required", 10),
        _length_requirement(
            "advisory-missing",
            1,
            level=RequirementLevel.ADVISORY,
            sequence_name="missing",
        ),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.COMPATIBLE
    assert result.basis_finding_ids == ()
    assert bundle.interpretation.findings


def test_conditions_do_not_create_positive_verdict_without_mandatory_basis() -> None:
    bundle = _bundle(
        _length_requirement("advisory", 10, level=RequirementLevel.ADVISORY),
        request=_request(names=("chr1",)),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.INDETERMINATE
    assert result.condition_ids


def test_advisory_conflict_does_not_veto_satisfied_mandatory_requirement() -> None:
    bundle = _bundle(
        _length_requirement("required", 10),
        _length_requirement("advisory", 11, level=RequirementLevel.ADVISORY),
    )
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.COMPATIBLE
    assert result.mandatory_constraint_ids == (bundle.constraints[0].id,)
    assert result.basis_finding_ids == ()
    assert bundle.interpretation.findings


def test_only_advisory_requirements_do_not_create_vacuous_compatibility() -> None:
    bundle = _bundle(_length_requirement("advisory", 10, level=RequirementLevel.ADVISORY))
    result = aggregate_bundle_verdict(bundle)

    assert result.verdict is CompatibilityVerdict.INDETERMINATE
    assert result.mandatory_constraint_ids == ()
    assert result.basis_finding_ids == ()


def test_zero_requirements_do_not_create_vacuous_compatibility() -> None:
    result = aggregate_bundle_verdict(_bundle())

    assert result.verdict is CompatibilityVerdict.INDETERMINATE
    assert result.mandatory_constraint_ids == ()
    assert result.basis_finding_ids == ()


def test_not_applicable_mandatory_is_neutral_when_another_mandatory_is_satisfied() -> None:
    bundle = _bundle(
        _length_requirement("required", 10),
        _length_requirement("synthetic-na", 20, sequence_name="chr2"),
    )
    not_applicable = ConstraintEvaluation(
        constraint_id=bundle.constraints[1].id,
        requirement_id=bundle.constraints[1].requirement.id,
        state=ConstraintState.NOT_APPLICABLE,
    )
    synthetic = replace(
        bundle,
        evaluations=(bundle.evaluations[0], not_applicable),
        evidence=EvidenceAggregate(
            evidence=bundle.evidence.for_constraint(bundle.constraints[0].id),
            not_applicable_constraint_ids=(bundle.constraints[1].id,),
        ),
        interpretation=InterpretationResult(),
    )

    result = aggregate_bundle_verdict(synthetic)
    assert result.verdict is CompatibilityVerdict.COMPATIBLE
    assert result.not_applicable_mandatory_constraint_ids == (bundle.constraints[1].id,)


def test_all_not_applicable_mandatory_constraints_are_indeterminate() -> None:
    bundle = _bundle(_length_requirement("synthetic-na", 10))
    not_applicable = ConstraintEvaluation(
        constraint_id=bundle.constraints[0].id,
        requirement_id=bundle.constraints[0].requirement.id,
        state=ConstraintState.NOT_APPLICABLE,
    )
    synthetic = replace(
        bundle,
        evaluations=(not_applicable,),
        evidence=EvidenceAggregate(not_applicable_constraint_ids=(bundle.constraints[0].id,)),
        interpretation=InterpretationResult(),
    )

    result = aggregate_bundle_verdict(synthetic)
    assert result.verdict is CompatibilityVerdict.INDETERMINATE


def test_decisive_mandatory_state_requires_traceable_finding() -> None:
    bundle = _bundle(_length_requirement("wrong", 11))
    malformed = replace(bundle, interpretation=InterpretationResult())

    with pytest.raises(ValueError, match="traceable finding"):
        aggregate_bundle_verdict(malformed)
