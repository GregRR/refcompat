"""Tests for decisive conflict-core extraction from bundle verdicts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    BundleReasoningResult,
    CollectionCompleteness,
    CompatibilityFinding,
    CompatibilityVerdict,
    ConflictCoreExtraction,
    ConflictCoreKind,
    EvaluationRequest,
    EvaluationScope,
    EvidenceId,
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
    VerdictAggregation,
)
from refcompat.reasoning import aggregate_bundle_verdict, extract_conflict_cores, reason_bundle

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_IDENTITY = RefgetSequenceId("SQ." + "A" * 32)
_ORIGIN = RequirementOrigin.CORE_FORMAT


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request(*, names: tuple[str, ...] | None = None) -> EvaluationRequest:
    return EvaluationRequest(
        resources=(
            _resource(_REFERENCE, ResourceKind.FASTA),
            _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
        ),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope(
            resource_ids=(_REFERENCE, _CONSUMER),
            anchor_sequence_names=names,
        ),
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


def _requirement(
    requirement_id: str,
    length: int,
    *,
    sequence_name: str = "chr1",
    level: RequirementLevel = RequirementLevel.MANDATORY,
) -> SequenceLengthRequirement:
    return SequenceLengthRequirement(
        RequirementId(requirement_id),
        _CONSUMER,
        _ORIGIN,
        level,
        sequence_name,
        length,
    )


def _bundle(*requirements: SequenceLengthRequirement) -> BundleReasoningResult:
    return reason_bundle(
        _request(),
        _snapshot(),
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, requirements=tuple(requirements)),
        ),
    )


def _extract(
    *requirements: SequenceLengthRequirement,
) -> tuple[BundleReasoningResult, VerdictAggregation, ConflictCoreExtraction]:
    bundle = _bundle(*requirements)
    verdict = aggregate_bundle_verdict(bundle)
    return bundle, verdict, extract_conflict_cores(bundle, verdict)


def test_compatible_bundle_has_no_conflict_core() -> None:
    _, verdict, extraction = _extract(_requirement("ok", 10))
    assert verdict.verdict is CompatibilityVerdict.COMPATIBLE
    assert extraction.cores == ()
    assert extraction.decisive_constraint_ids == ()


def test_conditional_compatible_bundle_has_no_conflict_core() -> None:
    requirement = _requirement("ok", 10)
    bundle = reason_bundle(
        _request(names=("chr1",)),
        _snapshot(),
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, requirements=(requirement,)),
        ),
    )
    verdict = aggregate_bundle_verdict(bundle)
    extraction = extract_conflict_cores(bundle, verdict)

    assert verdict.verdict is CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS
    assert extraction.cores == ()


def test_incompatible_core_contains_only_decisive_conflict_trace() -> None:
    bundle, verdict, extraction = _extract(
        _requirement("wrong", 11),
        _requirement("ok", 10),
        _requirement("advisory", 12, level=RequirementLevel.ADVISORY),
    )

    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert len(extraction.cores) == 1
    core = extraction.cores[0]
    assert core.kind is ConflictCoreKind.CONTRADICTION
    assert core.constraint_ids == (bundle.constraints[0].id,)
    assert core.finding_ids == (bundle.interpretation.findings[0].id,)
    assert core.evidence_ids == (bundle.interpretation.findings[0].evidence_ids[0],)
    assert core.resource_ids == (_CONSUMER, _REFERENCE)


def test_hard_conflict_precedence_excludes_unresolved_core() -> None:
    bundle, verdict, extraction = _extract(
        _requirement("wrong", 11),
        _requirement("missing", 10, sequence_name="missing"),
    )

    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert verdict.unresolved_mandatory_constraint_ids == (bundle.constraints[1].id,)
    assert extraction.decisive_constraint_ids == (bundle.constraints[0].id,)
    assert len(extraction.cores) == 1
    assert extraction.cores[0].constraint_ids == (bundle.constraints[0].id,)


def test_unresolved_without_evidence_has_minimal_resource_only_core() -> None:
    bundle, verdict, extraction = _extract(_requirement("missing", 10, sequence_name="missing"))

    assert verdict.verdict is CompatibilityVerdict.INDETERMINATE
    core = extraction.cores[0]
    assert core.kind is ConflictCoreKind.UNRESOLVED
    assert core.constraint_ids == (bundle.constraints[0].id,)
    assert core.evidence_ids == ()
    assert core.resource_ids == (_CONSUMER,)


def test_multiple_independent_conflicts_remain_separate_small_cores() -> None:
    bundle, _, extraction = _extract(
        _requirement("wrong-one", 11),
        _requirement("wrong-two", 12),
    )

    assert len(extraction.cores) == 2
    assert tuple(core.constraint_ids for core in extraction.cores) == (
        (bundle.constraints[0].id,),
        (bundle.constraints[1].id,),
    )
    assert all(len(core.evidence_ids) == 1 for core in extraction.cores)


def test_no_applicable_mandatory_basis_has_no_evidence_core() -> None:
    _, verdict, extraction = _extract(_requirement("advisory", 10, level=RequirementLevel.ADVISORY))

    assert verdict.verdict is CompatibilityVerdict.INDETERMINATE
    assert verdict.mandatory_constraint_ids == ()
    assert extraction.cores == ()


def test_conflict_core_ids_are_deterministic() -> None:
    bundle = _bundle(_requirement("wrong", 11))
    verdict = aggregate_bundle_verdict(bundle)
    first = extract_conflict_cores(bundle, verdict)
    second = extract_conflict_cores(bundle, verdict)
    assert first == second


def test_conflict_core_rejects_verdict_from_another_bundle() -> None:
    bundle = _bundle(_requirement("wrong", 11))
    other = _bundle(_requirement("missing", 10, sequence_name="missing"))
    other_verdict = aggregate_bundle_verdict(other)

    with pytest.raises(ValueError, match="verdict matching the bundle"):
        extract_conflict_cores(bundle, other_verdict)


def test_conflict_core_rejects_finding_with_unknown_evidence() -> None:
    bundle = _bundle(_requirement("wrong", 11))
    finding = bundle.interpretation.findings[0]
    malformed_finding = replace(
        finding,
        evidence_ids=(EvidenceId("missing-evidence"),),
    )
    malformed_bundle = replace(
        bundle,
        interpretation=InterpretationResult(findings=(malformed_finding,)),
    )
    verdict = aggregate_bundle_verdict(malformed_bundle)

    with pytest.raises(ValueError, match="evidence absent from bundle"):
        extract_conflict_cores(malformed_bundle, verdict)


def test_conflict_core_rejects_finding_with_wrong_requirement_trace() -> None:
    bundle = _bundle(_requirement("wrong", 11))
    finding = bundle.interpretation.findings[0]
    malformed_finding = replace(
        finding,
        requirement_ids=(RequirementId("wrong-requirement"),),
    )
    malformed_bundle = replace(
        bundle,
        interpretation=InterpretationResult(findings=(malformed_finding,)),
    )
    verdict = aggregate_bundle_verdict(malformed_bundle)

    with pytest.raises(ValueError, match="requirement trace"):
        extract_conflict_cores(malformed_bundle, verdict)


def test_conflict_core_rejects_finding_with_incomplete_resource_trace() -> None:
    bundle = _bundle(_requirement("wrong", 11))
    finding = bundle.interpretation.findings[0]
    malformed_finding = replace(finding, resource_ids=(_CONSUMER,))
    malformed_bundle = replace(
        bundle,
        interpretation=InterpretationResult(findings=(malformed_finding,)),
    )
    verdict = aggregate_bundle_verdict(malformed_bundle)

    with pytest.raises(ValueError, match="resource trace"):
        extract_conflict_cores(malformed_bundle, verdict)


def test_conflict_core_ignores_nondecisive_advisory_finding() -> None:
    bundle, verdict, extraction = _extract(
        _requirement("wrong", 11),
        _requirement("advisory-wrong", 12, level=RequirementLevel.ADVISORY),
    )

    assert len(bundle.interpretation.findings) == 2
    assert verdict.basis_finding_ids == (bundle.interpretation.findings[0].id,)
    assert extraction.cores[0].finding_ids == (bundle.interpretation.findings[0].id,)


def test_finding_identity_is_preserved_without_copying_unrelated_trace() -> None:
    bundle, verdict, extraction = _extract(_requirement("wrong", 11))
    original = bundle.interpretation.findings[0]
    core = extraction.cores[0]

    assert isinstance(original, CompatibilityFinding)
    assert core.finding_ids == (original.id,)
    assert core.requirement_ids == (bundle.constraints[0].requirement.id,)
    assert verdict.condition_ids == ()
