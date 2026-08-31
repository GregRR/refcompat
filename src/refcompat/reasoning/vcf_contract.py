"""Project VCF observations and direct REF validation into generic reasoning."""

from __future__ import annotations

import hashlib
import json

from refcompat.model.constraints import (
    CompatibilityConstraint,
    ConstraintId,
    capability_is_comparable,
)
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.identity import Md5Digest
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.model.resources import ResourceId
from refcompat.model.vcf import VcfContextSnapshot
from refcompat.model.vcf_contract import VcfContractProjection
from refcompat.model.vcf_ref import VcfRefValidationResult
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence
from refcompat.reasoning.vcf_binding import (
    derive_vcf_sequence_bindings,
    vcf_binding_identity_capabilities,
)
from refcompat.reasoning.vcf_ref_pattern import classify_vcf_ref_conflicts


def build_vcf_contract(
    snapshot: VcfContextSnapshot,
    reference_context: ReferenceContext,
) -> ResourceContract:
    """Build the context-specific VCF contract before direct REF validation.

    Actual CHROM usage creates mandatory presence requirements. Declared lengths
    for used contigs create mandatory sequence-length requirements. A
    syntactically valid ``##contig`` MD5 declaration for a used contig also
    creates a mandatory sequence-identity requirement, while only declarations
    safe for verified cross-name binding are retained as peer identity
    capabilities. The record set creates one aggregate reference-base
    requirement. Binding capabilities establish naming only; they are never
    direct reference-base compatibility evidence.
    """

    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("VCF resource must be inside the reference-context scope")

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
    identity_requirements = _declared_identity_requirements(snapshot)
    length_requirements = _declared_length_requirements(snapshot)
    base_requirement = ReferenceBaseRequirement(
        id=_requirement_id(
            "reference-bases",
            snapshot.resource_id,
            f"{reference_context.anchor_resource_id}:{snapshot.record_count}",
        ),
        resource_id=snapshot.resource_id,
        anchor_resource_id=reference_context.anchor_resource_id,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        record_count=snapshot.record_count,
    )
    return ResourceContract(
        resource_id=snapshot.resource_id,
        requirements=(
            *presence_requirements,
            *identity_requirements,
            *length_requirements,
            base_requirement,
        ),
        capabilities=vcf_binding_identity_capabilities(snapshot, reference_context),
    )


def project_vcf_contract(
    snapshot: VcfContextSnapshot,
    validation: VcfRefValidationResult,
    reference_context: ReferenceContext,
    *,
    sequence_bindings: tuple[SequenceBinding, ...] | None = None,
) -> VcfContractProjection:
    """Build scalable generic requirements/evidence from exhaustive VCF facts.

    By default, verified cross-name bindings are derived independently from VCF
    ``##contig`` MD5 identity claims and the complete FASTA anchor. A caller may
    instead supply an already verified binding set, such as a profile-authorized
    naming relationship. In either case the exhaustive validation must have used
    exactly those bindings; stale exact-name validation is rejected rather than
    silently projected.
    """

    contract = build_vcf_contract(snapshot, reference_context)
    if sequence_bindings is None:
        sequence_bindings = derive_vcf_sequence_bindings(snapshot, reference_context)
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
    length_requirements = tuple(
        requirement
        for requirement in contract.requirements
        if isinstance(requirement, SequenceLengthRequirement)
    )
    base_requirement = next(
        requirement
        for requirement in contract.requirements
        if isinstance(requirement, ReferenceBaseRequirement)
    )

    base_capability = ReferenceBaseValidationCapability(
        id=_reference_base_capability_id(validation),
        resource_id=validation.fasta_resource_id,
        subject_resource_id=validation.vcf_resource_id,
        checked_count=validation.record_count,
        match_count=validation.match_count,
        mismatch_count=validation.mismatch_count,
        unresolved_count=(validation.out_of_bounds_count + validation.unresolved_sequence_count),
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
        relevant_bindings = (binding,) if binding is not None else ()
        constraints.append(
            _constraint(
                reference_context,
                presence_requirement,
                presence_candidates,
                sequence_bindings=relevant_bindings,
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
        relevant_bindings = (binding,) if binding is not None else ()
        constraints.append(
            _constraint(
                reference_context,
                identity_requirement,
                identity_candidates,
                sequence_bindings=relevant_bindings,
            )
        )
    for length_requirement in length_requirements:
        binding = bindings_by_name.get(length_requirement.sequence_name)
        target_name = (
            binding.anchor_sequence_name
            if binding is not None
            else length_requirement.sequence_name
        )
        length_candidates = tuple(
            length_capability
            for length_capability in reference_context.anchor_capabilities
            if isinstance(length_capability, SequenceLengthCapability)
            and length_capability.sequence_name == target_name
        )
        relevant_bindings = (binding,) if binding is not None else ()
        constraints.append(
            _constraint(
                reference_context,
                length_requirement,
                length_candidates,
                sequence_bindings=relevant_bindings,
            )
        )
    constraints.append(_constraint(reference_context, base_requirement, (base_capability,)))

    constraint_tuple = tuple(constraints)
    evaluations = tuple(evaluate_constraint(constraint) for constraint in constraint_tuple)
    evidence = aggregate_constraint_evidence(constraint_tuple, evaluations)
    conflict_pattern = classify_vcf_ref_conflicts(validation)
    return VcfContractProjection(
        vcf_resource_id=snapshot.resource_id,
        fasta_resource_id=validation.fasta_resource_id,
        contract=contract,
        sequence_bindings=sequence_bindings,
        reference_base_capability=base_capability,
        constraints=constraint_tuple,
        evaluations=evaluations,
        evidence=evidence,
        validation=validation,
        conflict_pattern=conflict_pattern,
    )


def _declared_identity_requirements(
    snapshot: VcfContextSnapshot,
) -> tuple[SequenceIdentityRequirement, ...]:
    used_names = set(snapshot.used_sequence_names)
    requirements: list[SequenceIdentityRequirement] = []
    for contig in snapshot.header.contigs:
        if contig.name not in used_names or contig.md5 is None:
            continue
        try:
            digest = Md5Digest(contig.md5)
        except ValueError:
            continue
        requirements.append(
            SequenceIdentityRequirement(
                id=_requirement_id(
                    "identity",
                    snapshot.resource_id,
                    f"{contig.name}:{digest.value}",
                ),
                resource_id=snapshot.resource_id,
                origin=RequirementOrigin.CORE_FORMAT,
                level=RequirementLevel.MANDATORY,
                sequence_name=contig.name,
                identity=digest,
            )
        )
    return tuple(requirements)


def _declared_length_requirements(
    snapshot: VcfContextSnapshot,
) -> tuple[SequenceLengthRequirement, ...]:
    used_names = set(snapshot.used_sequence_names)
    return tuple(
        SequenceLengthRequirement(
            id=_requirement_id(
                "length",
                snapshot.resource_id,
                f"{contig.name}:{contig.length}",
            ),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=contig.name,
            length=contig.length,
        )
        for contig in snapshot.header.contigs
        if contig.name in used_names and contig.length is not None
    )


def _validate_inputs(
    snapshot: VcfContextSnapshot,
    validation: VcfRefValidationResult,
    reference_context: ReferenceContext,
    sequence_bindings: tuple[SequenceBinding, ...],
) -> None:
    if snapshot.resource_id != validation.vcf_resource_id:
        raise ValueError("VCF context and REF validation must belong to the same VCF resource")
    if validation.fasta_resource_id != reference_context.anchor_resource_id:
        raise ValueError("VCF REF validation must use the reference-context FASTA anchor")
    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("VCF resource must be inside the reference-context scope")
    if snapshot.record_count != validation.record_count:
        raise ValueError("VCF context and REF validation record counts must match")

    expected_binding_ids = tuple(sorted((binding.id for binding in sequence_bindings), key=str))
    if validation.sequence_binding_ids != expected_binding_ids:
        raise ValueError(
            "VCF REF validation must use exactly the verified sequence bindings for this context"
        )

    usage = {item.sequence_name: item.record_count for item in snapshot.chrom_usage}
    summaries = {item.sequence_name: item.record_count for item in validation.sequence_summaries}
    if usage != summaries:
        raise ValueError("VCF context CHROM usage must match REF validation sequence coverage")


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
    return RequirementId(f"vcf-requirement:{_digest([kind, str(resource_id), value])}")


def _reference_base_capability_id(validation: VcfRefValidationResult) -> CapabilityId:
    problems = [
        [
            check.record.ordinal,
            check.state.value,
            check.record.sequence_name,
            check.record.position,
            check.record.ref.upper(),
            check.fasta_bases,
        ]
        for check in validation.problem_records
    ]
    return CapabilityId(
        "reference-base-capability:"
        + _digest(
            [
                str(validation.vcf_resource_id),
                str(validation.fasta_resource_id),
                validation.record_count,
                validation.match_count,
                validation.mismatch_count,
                validation.out_of_bounds_count,
                validation.unresolved_sequence_count,
                [str(binding_id) for binding_id in validation.sequence_binding_ids],
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
        "vcf-constraint:"
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
