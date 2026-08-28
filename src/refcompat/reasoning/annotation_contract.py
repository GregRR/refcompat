"""Project annotation observations and coordinate validation into generic reasoning."""

from __future__ import annotations

import hashlib
import json

from refcompat.model.annotation import AnnotationContextSnapshot
from refcompat.model.annotation_bounds import AnnotationCoordinateValidationResult
from refcompat.model.annotation_contract import AnnotationContractProjection
from refcompat.model.constraints import CompatibilityConstraint, ConstraintId
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    Requirement,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    ResourceContract,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence


def build_annotation_contract(
    snapshot: AnnotationContextSnapshot,
    reference_context: ReferenceContext,
) -> ResourceContract:
    """Build the sparse annotation contract before pair-derived bounds evidence."""

    if snapshot.resource_id == reference_context.anchor_resource_id:
        raise ValueError("annotation contract resource cannot be the FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("annotation resource must be inside the reference-context scope")

    presence_requirements = tuple(
        SequencePresenceRequirement(
            id=_requirement_id("presence", snapshot.resource_id, sequence_name),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=sequence_name,
        )
        for sequence_name in snapshot.used_sequence_names
    )
    bounds_requirement = CoordinateBoundsRequirement(
        id=_requirement_id(
            "coordinate-bounds",
            snapshot.resource_id,
            f"{reference_context.anchor_resource_id}:{snapshot.feature_count}",
        ),
        resource_id=snapshot.resource_id,
        anchor_resource_id=reference_context.anchor_resource_id,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        coordinate_count=snapshot.feature_count,
    )
    return ResourceContract(
        resource_id=snapshot.resource_id,
        requirements=(*presence_requirements, bounds_requirement),
    )


def project_annotation_contract(
    snapshot: AnnotationContextSnapshot,
    validation: AnnotationCoordinateValidationResult,
    reference_context: ReferenceContext,
) -> AnnotationContractProjection:
    """Project exact-name annotation bounds validation into generic reasoning."""

    contract = build_annotation_contract(snapshot, reference_context)
    _validate_inputs(snapshot, validation, reference_context)

    presence_requirements = tuple(
        requirement
        for requirement in contract.requirements
        if isinstance(requirement, SequencePresenceRequirement)
    )
    bounds_requirement = next(
        requirement
        for requirement in contract.requirements
        if isinstance(requirement, CoordinateBoundsRequirement)
    )
    bounds_capability = CoordinateBoundsValidationCapability(
        id=_coordinate_capability_id(validation),
        resource_id=validation.fasta_resource_id,
        subject_resource_id=validation.annotation_resource_id,
        checked_count=validation.feature_count,
        representable_count=validation.representable_count,
        conflict_count=validation.out_of_bounds_count,
        unresolved_count=validation.unresolved_count,
    )

    constraints: list[CompatibilityConstraint] = []
    for requirement in presence_requirements:
        candidates = tuple(
            capability
            for capability in reference_context.anchor_capabilities
            if isinstance(capability, SequencePresenceCapability)
            and capability.sequence_name == requirement.sequence_name
        )
        constraints.append(_constraint(reference_context, requirement, candidates))
    constraints.append(_constraint(reference_context, bounds_requirement, (bounds_capability,)))

    constraint_tuple = tuple(constraints)
    evaluations = tuple(evaluate_constraint(constraint) for constraint in constraint_tuple)
    evidence = aggregate_constraint_evidence(constraint_tuple, evaluations)
    return AnnotationContractProjection(
        annotation_resource_id=snapshot.resource_id,
        fasta_resource_id=validation.fasta_resource_id,
        contract=contract,
        coordinate_bounds_capability=bounds_capability,
        constraints=constraint_tuple,
        evaluations=evaluations,
        evidence=evidence,
        validation=validation,
    )


def _validate_inputs(
    snapshot: AnnotationContextSnapshot,
    validation: AnnotationCoordinateValidationResult,
    reference_context: ReferenceContext,
) -> None:
    if snapshot.resource_id != validation.annotation_resource_id:
        raise ValueError("annotation context and validation must belong to the same resource")
    if validation.fasta_resource_id != reference_context.anchor_resource_id:
        raise ValueError("annotation validation must use the reference-context FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("annotation resource must be inside the reference-context scope")
    if snapshot.feature_count != validation.feature_count:
        raise ValueError("annotation context and validation feature counts must match")

    usage = {item.sequence_name: item.feature_count for item in snapshot.sequence_usage}
    summaries = {item.sequence_name: item.feature_count for item in validation.sequence_summaries}
    if usage != summaries:
        raise ValueError("annotation seqid usage must match coordinate validation coverage")


def _constraint(
    context: ReferenceContext,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
) -> CompatibilityConstraint:
    return build_constraint(
        _constraint_id(context.anchor_resource_id, requirement, candidates),
        requirement,
        candidates,
    )


def _requirement_id(kind: str, resource_id: ResourceId, value: str) -> RequirementId:
    return RequirementId(f"annotation-requirement:{_digest([kind, str(resource_id), value])}")


def _coordinate_capability_id(validation: AnnotationCoordinateValidationResult) -> CapabilityId:
    problems = [
        [
            check.feature.ordinal,
            check.state.value,
            check.feature.sequence_name,
            check.feature.start,
            check.feature.end,
            check.anchor_sequence_name,
            check.anchor_sequence_length,
        ]
        for check in validation.problem_checks
    ]
    return CapabilityId(
        "coordinate-bounds-capability:"
        + _digest(
            [
                str(validation.annotation_resource_id),
                str(validation.fasta_resource_id),
                validation.feature_count,
                validation.representable_count,
                validation.out_of_bounds_count,
                validation.unresolved_sequence_count,
                validation.circular_bounds_unresolved_count,
                problems,
            ]
        )
    )


def _constraint_id(
    anchor_resource_id: ResourceId,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
) -> ConstraintId:
    return ConstraintId(
        "annotation-constraint:"
        + _digest(
            [
                str(anchor_resource_id),
                str(requirement.id),
                [str(capability.id) for capability in candidates],
            ]
        )
    )


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
