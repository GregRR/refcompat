"""Project annotation observations and coordinate validation into generic reasoning."""

from __future__ import annotations

import hashlib
import json

from refcompat.model.annotation import AnnotationContextSnapshot
from refcompat.model.annotation_bounds import AnnotationCoordinateValidationResult
from refcompat.model.annotation_contract import AnnotationContractProjection
from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintId,
    capability_is_comparable,
)
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
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.model.resources import ResourceId
from refcompat.reasoning.annotation_binding import (
    annotation_binding_identity_capabilities,
    annotation_embedded_identity_capabilities,
    derive_annotation_sequence_bindings,
)
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence


def build_annotation_contract(
    snapshot: AnnotationContextSnapshot,
    reference_context: ReferenceContext,
    *,
    binding_identity_capabilities: tuple[SequenceIdentityCapability, ...] = (),
) -> ResourceContract:
    """Build sparse annotation requirements plus permitted binding capabilities."""

    if snapshot.resource_id == reference_context.anchor_resource_id:
        raise ValueError("annotation contract resource cannot be the FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("annotation resource must be inside the reference-context scope")

    presence_names = _required_sequence_names(snapshot)
    presence_requirements = tuple(
        SequencePresenceRequirement(
            id=_requirement_id("presence", snapshot.resource_id, sequence_name),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=sequence_name,
        )
        for sequence_name in presence_names
    )
    identity_capabilities = annotation_embedded_identity_capabilities(snapshot)
    binding_capabilities = annotation_binding_identity_capabilities(
        snapshot,
        binding_identity_capabilities,
    )
    identity_requirements = tuple(
        SequenceIdentityRequirement(
            id=_requirement_id(
                "embedded-identity",
                snapshot.resource_id,
                f"{capability.sequence_name}:{capability.identity.value}",
            ),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=capability.sequence_name,
            identity=capability.identity,
        )
        for capability in identity_capabilities
    )
    bounds_requirement = CoordinateBoundsRequirement(
        id=_requirement_id(
            "coordinate-bounds",
            snapshot.resource_id,
            f"{reference_context.anchor_resource_id}:"
            f"{snapshot.feature_count + len(snapshot.sequence_regions)}",
        ),
        resource_id=snapshot.resource_id,
        anchor_resource_id=reference_context.anchor_resource_id,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        coordinate_count=snapshot.feature_count + len(snapshot.sequence_regions),
    )
    return ResourceContract(
        resource_id=snapshot.resource_id,
        requirements=(*presence_requirements, *identity_requirements, bounds_requirement),
        capabilities=binding_capabilities,
    )


def project_annotation_contract(
    snapshot: AnnotationContextSnapshot,
    validation: AnnotationCoordinateValidationResult,
    reference_context: ReferenceContext,
    *,
    binding_identity_capabilities: tuple[SequenceIdentityCapability, ...] = (),
) -> AnnotationContractProjection:
    """Project annotation coordinates and embedded identities into generic reasoning.

    Verified cross-name bindings are derived independently from permitted
    annotation-owned content identities and the complete FASTA anchor. Embedded
    GFF3 sequence content is one such source; callers may additionally supply
    independently established content-derived identities for reference-relevant
    annotation seqids. If bindings exist, the supplied exhaustive validation
    must have used exactly those bindings.
    """

    contract = build_annotation_contract(
        snapshot,
        reference_context,
        binding_identity_capabilities=binding_identity_capabilities,
    )
    sequence_bindings = derive_annotation_sequence_bindings(
        snapshot,
        reference_context,
        binding_identity_capabilities=binding_identity_capabilities,
    )
    _validate_inputs(snapshot, validation, reference_context, sequence_bindings)

    presence_requirements = tuple(
        requirement
        for requirement in contract.requirements
        if isinstance(requirement, SequencePresenceRequirement)
    )
    identity_requirements = tuple(
        requirement
        for requirement in contract.requirements
        if isinstance(requirement, SequenceIdentityRequirement)
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
        checked_count=validation.coordinate_count,
        representable_count=validation.coordinate_representable_count,
        conflict_count=validation.coordinate_conflict_count,
        unresolved_count=validation.coordinate_unresolved_count,
    )

    bindings_by_name = {binding.local_sequence_name: binding for binding in sequence_bindings}
    constraints: list[CompatibilityConstraint] = []
    for presence_requirement in presence_requirements:
        binding = bindings_by_name.get(presence_requirement.sequence_name)
        target_name = (
            binding.anchor_sequence_name
            if binding is not None
            else presence_requirement.sequence_name
        )
        presence_candidates = tuple(
            presence_capability
            for presence_capability in reference_context.anchor_capabilities
            if isinstance(presence_capability, SequencePresenceCapability)
            and presence_capability.sequence_name == target_name
        )
        constraints.append(
            _constraint(
                reference_context,
                presence_requirement,
                presence_candidates,
                sequence_bindings=((binding,) if binding is not None else ()),
            )
        )
    for identity_requirement in identity_requirements:
        binding = bindings_by_name.get(identity_requirement.sequence_name)
        target_name = (
            binding.anchor_sequence_name
            if binding is not None
            else identity_requirement.sequence_name
        )
        identity_candidates = tuple(
            identity_capability
            for identity_capability in reference_context.anchor_capabilities
            if isinstance(identity_capability, SequenceIdentityCapability)
            and identity_capability.sequence_name == target_name
            and capability_is_comparable(identity_requirement, identity_capability)
        )
        constraints.append(
            _constraint(
                reference_context,
                identity_requirement,
                identity_candidates,
                sequence_bindings=((binding,) if binding is not None else ()),
            )
        )
    constraints.append(_constraint(reference_context, bounds_requirement, (bounds_capability,)))

    constraint_tuple = tuple(constraints)
    evaluations = tuple(evaluate_constraint(constraint) for constraint in constraint_tuple)
    evidence = aggregate_constraint_evidence(constraint_tuple, evaluations)
    return AnnotationContractProjection(
        annotation_resource_id=snapshot.resource_id,
        fasta_resource_id=validation.fasta_resource_id,
        contract=contract,
        sequence_bindings=sequence_bindings,
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
    sequence_bindings: tuple[SequenceBinding, ...],
) -> None:
    if snapshot.resource_id != validation.annotation_resource_id:
        raise ValueError("annotation context and validation must belong to the same resource")
    if validation.fasta_resource_id != reference_context.anchor_resource_id:
        raise ValueError("annotation validation must use the reference-context FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("annotation resource must be inside the reference-context scope")
    if snapshot.feature_count != validation.feature_count:
        raise ValueError("annotation context and validation feature counts must match")

    expected_binding_ids = tuple(sorted((binding.id for binding in sequence_bindings), key=str))
    if validation.sequence_binding_ids != expected_binding_ids:
        raise ValueError(
            "annotation coordinate validation must use exactly the verified sequence bindings"
        )

    region_validation = validation.sequence_region_validation
    if snapshot.sequence_regions:
        if region_validation is None:
            raise ValueError("GFF3 sequence-region observations require sequence-region validation")
        observed_regions = tuple(
            (region.sequence_name, region.start, region.end, region.line_number)
            for region in snapshot.sequence_regions
        )
        validated_regions = tuple(
            (
                check.region.sequence_name,
                check.region.start,
                check.region.end,
                check.region.line_number,
            )
            for check in region_validation.checks
        )
        if observed_regions != validated_regions:
            raise ValueError("GFF3 sequence-region validation must match inspected directives")
    elif region_validation is not None and region_validation.region_count:
        raise ValueError("sequence-region validation cannot invent directives")

    usage = {item.sequence_name: item.feature_count for item in snapshot.sequence_usage}
    summaries = {item.sequence_name: item.feature_count for item in validation.sequence_summaries}
    if usage != summaries:
        raise ValueError("annotation seqid usage must match coordinate validation coverage")


def _required_sequence_names(snapshot: AnnotationContextSnapshot) -> tuple[str, ...]:
    """Feature-used seqids followed by any sequence-region-only seqids."""

    names = list(snapshot.used_sequence_names)
    seen = set(names)
    for region in snapshot.sequence_regions:
        if region.sequence_name not in seen:
            names.append(region.sequence_name)
            seen.add(region.sequence_name)
    return tuple(names)


def _constraint(
    context: ReferenceContext,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
    *,
    sequence_bindings: tuple[SequenceBinding, ...] = (),
) -> CompatibilityConstraint:
    return build_constraint(
        _constraint_id(
            context.anchor_resource_id,
            requirement,
            candidates,
            sequence_bindings,
        ),
        requirement,
        candidates,
        sequence_bindings,
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
                validation.circular_representable_count,
                validation.out_of_bounds_count,
                validation.unresolved_sequence_count,
                validation.circular_bounds_unresolved_count,
                [str(binding_id) for binding_id in validation.sequence_binding_ids],
                [
                    [
                        check.region.sequence_name,
                        check.region.start,
                        check.region.end,
                        check.state.value,
                        check.anchor_sequence_name,
                        check.anchor_sequence_length,
                    ]
                    for check in (
                        validation.sequence_region_validation.checks
                        if validation.sequence_region_validation is not None
                        else ()
                    )
                ],
                problems,
            ]
        )
    )


def _constraint_id(
    anchor_resource_id: ResourceId,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
    sequence_bindings: tuple[SequenceBinding, ...],
) -> ConstraintId:
    return ConstraintId(
        "annotation-constraint:"
        + _digest(
            [
                str(anchor_resource_id),
                str(requirement.id),
                [str(capability.id) for capability in candidates],
                [str(binding.id) for binding in sequence_bindings],
            ]
        )
    )


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
