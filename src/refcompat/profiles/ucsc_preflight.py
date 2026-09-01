"""Project the UCSC preflight profile into generic RefCompat reasoning.

This layer composes provider-authoritative naming with the independently
content-bound UCSC target relationship. It adds profile-origin binding
requirements and pair-derived validation capabilities, but delegates ordinary
resource requirements, evidence, findings, conditions, and verdict aggregation
to the generic reasoner.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from refcompat.model.contracts import (
    CapabilityId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    ResourceContract,
    SequenceBindingRequirement,
    SequenceBindingValidationCapability,
    SequenceBindingValidationState,
    SequenceIdentityCapability,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest, ProfileId
from refcompat.model.reference_context import (
    ReferenceContext,
    SequenceBinding,
    SequenceBindingId,
    SequenceBindingMethod,
)
from refcompat.model.resources import ResourceId
from refcompat.profiles.ucsc import (
    UcscDatabaseId,
    UcscNameResolution,
    UcscNameResolutionReason,
    UcscNameResolutionState,
    UcscProviderContextId,
    UcscProviderSnapshot,
    UcscTargetBinding,
    UcscTargetResolution,
    UcscTargetResolutionState,
)
from refcompat.profiles.ucsc_reasoning import (
    resolve_ucsc_sequence_name,
    resolve_ucsc_target,
)
from refcompat.reasoning.reference_context import (
    derive_sequence_bindings,
    identity_evidence_is_consistent_with_anchor_target,
)

UCSC_PREFLIGHT_PROFILE_ID = ProfileId("ucsc-preflight")


@dataclass(frozen=True, slots=True)
class UcscPreflightTarget:
    """Explicit native UCSC database selected by the caller."""

    database_id: UcscDatabaseId

    def __post_init__(self) -> None:
        if not self.database_id:
            raise ValueError("UCSC preflight target database ID must not be empty")


@dataclass(frozen=True, slots=True)
class UcscPreflightSequenceProjection:
    """Trace one resource-local sequence through the UCSC profile relationship."""

    resource_id: ResourceId
    local_sequence_name: str
    requirement: SequenceBindingRequirement
    name_resolution: UcscNameResolution
    target_resolution: UcscTargetResolution | None = None
    sequence_binding: SequenceBinding | None = None
    validation_capability: SequenceBindingValidationCapability | None = None

    def __post_init__(self) -> None:
        if not self.resource_id or not self.local_sequence_name:
            raise ValueError("UCSC preflight sequence projection identifiers must not be empty")
        if self.requirement.resource_id != self.resource_id:
            raise ValueError("UCSC profile requirement must belong to the projected resource")
        if self.requirement.sequence_name != self.local_sequence_name:
            raise ValueError("UCSC profile requirement must address the projected local name")
        if self.name_resolution.local_name != self.local_sequence_name:
            raise ValueError("UCSC name resolution must address the projected local name")
        if self.name_resolution.state is UcscNameResolutionState.UNRESOLVED:
            if self.target_resolution is not None:
                raise ValueError("unresolved UCSC name cannot have a target resolution")
            if self.sequence_binding is not None or self.validation_capability is not None:
                raise ValueError("unresolved UCSC name cannot produce a binding validation")
            return
        if self.target_resolution is None:
            raise ValueError("resolved UCSC name requires a target resolution")
        if self.target_resolution.canonical_name != self.name_resolution.canonical_name:
            raise ValueError("UCSC target resolution must match the resolved canonical name")
        if self.sequence_binding is not None:
            if self.sequence_binding.resource_id != self.resource_id:
                raise ValueError("UCSC projected binding must belong to the projected resource")
            if self.sequence_binding.local_sequence_name != self.local_sequence_name:
                raise ValueError("UCSC projected binding must address the projected local name")
            if self.sequence_binding.anchor_resource_id != self.requirement.anchor_resource_id:
                raise ValueError("UCSC projected binding must target the required anchor")
        if self.validation_capability is not None:
            if self.validation_capability.resource_id != self.requirement.anchor_resource_id:
                raise ValueError("UCSC binding validation must belong to the required anchor")
            if self.validation_capability.subject_resource_id != self.resource_id:
                raise ValueError("UCSC binding validation must describe the projected resource")
            if self.validation_capability.sequence_name != self.local_sequence_name:
                raise ValueError("UCSC binding validation must address the projected local name")

        if self.target_resolution.state is UcscTargetResolutionState.UNRESOLVED:
            if self.sequence_binding is not None or self.validation_capability is not None:
                raise ValueError("unresolved UCSC target cannot produce a binding validation")
        elif self.target_resolution.state is UcscTargetResolutionState.PROVEN_ABSENT:
            if self.sequence_binding is not None:
                raise ValueError("absent UCSC target cannot produce a sequence binding")
            if (
                self.validation_capability is None
                or self.validation_capability.state
                is not SequenceBindingValidationState.PROVEN_ABSENT
            ):
                raise ValueError("absent UCSC target requires a proven-absent validation")
        elif self.sequence_binding is not None:
            if self.validation_capability is None:
                raise ValueError("bound UCSC target binding requires validation")
            if self.validation_capability.state is SequenceBindingValidationState.BOUND:
                if (
                    self.validation_capability.anchor_sequence_name
                    != self.sequence_binding.anchor_sequence_name
                ):
                    raise ValueError("bound UCSC target binding requires matching validation")
            elif (
                self.validation_capability.state is SequenceBindingValidationState.CONTENT_CONFLICT
            ):
                assert self.target_resolution.binding is not None
                if (
                    self.sequence_binding.method
                    is not SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
                    or self.sequence_binding.anchor_sequence_name
                    == self.target_resolution.binding.anchor_sequence_name
                    or self.validation_capability.anchor_sequence_name
                    != self.target_resolution.binding.anchor_sequence_name
                ):
                    raise ValueError(
                        "UCSC content-conflict validation requires a different identity binding"
                    )
            else:
                raise ValueError("bound UCSC target cannot use proven-absent validation")
        elif self.validation_capability is not None:
            raise ValueError("bound UCSC validation requires a sequence binding")


@dataclass(frozen=True, slots=True)
class UcscPreflightProjection:
    """Generic-reasoner inputs plus provider trace for one UCSC preflight target."""

    target: UcscPreflightTarget
    provider_snapshot: UcscProviderSnapshot | None
    reference_context: ReferenceContext
    contracts: tuple[ResourceContract, ...]
    sequence_projections: tuple[UcscPreflightSequenceProjection, ...]
    sequence_bindings: tuple[SequenceBinding, ...]
    supplemental_sequence_bindings: tuple[SequenceBinding, ...]
    binding_capabilities: tuple[SequenceBindingValidationCapability, ...]

    def __post_init__(self) -> None:
        if (
            self.provider_snapshot is not None
            and self.target.database_id != self.provider_snapshot.database_id
        ):
            raise ValueError("UCSC preflight target must match the provider snapshot database")
        if self.provider_snapshot is None:
            if self.binding_capabilities or self.supplemental_sequence_bindings:
                raise ValueError(
                    "unavailable UCSC provider evidence cannot produce profile binding evidence"
                )
            if any(
                projection.name_resolution.reason
                is not UcscNameResolutionReason.PROVIDER_EVIDENCE_UNAVAILABLE
                for projection in self.sequence_projections
            ):
                raise ValueError(
                    "unavailable UCSC provider evidence requires unresolved name traces"
                )
        contract_ids = tuple(contract.resource_id for contract in self.contracts)
        if len(set(contract_ids)) != len(contract_ids):
            raise ValueError("UCSC preflight contracts must have unique resource IDs")
        if set(contract_ids) != set(self.reference_context.scope.resource_ids):
            raise ValueError("UCSC preflight projection requires one contract per scoped resource")
        binding_ids = tuple(binding.id for binding in self.sequence_bindings)
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("UCSC preflight sequence-binding IDs must be unique")
        binding_keys = tuple(
            (binding.resource_id, binding.local_sequence_name) for binding in self.sequence_bindings
        )
        if len(set(binding_keys)) != len(binding_keys):
            raise ValueError("UCSC preflight must map each resource-local name at most once")
        supplemental_ids = {binding.id for binding in self.supplemental_sequence_bindings}
        if not supplemental_ids.issubset(set(binding_ids)):
            raise ValueError("UCSC supplemental bindings must be included in effective bindings")
        capability_ids = tuple(capability.id for capability in self.binding_capabilities)
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("UCSC binding-validation capability IDs must be unique")

        projection_keys = tuple(
            (projection.resource_id, projection.local_sequence_name)
            for projection in self.sequence_projections
        )
        if len(set(projection_keys)) != len(projection_keys):
            raise ValueError("UCSC preflight sequence projections must be unique")
        contracts_by_id = {contract.resource_id: contract for contract in self.contracts}
        for projection in self.sequence_projections:
            if projection.requirement not in contracts_by_id[projection.resource_id].requirements:
                raise ValueError("UCSC profile requirement must be retained in its contract")

        projected_capability_ids = {
            projection.validation_capability.id
            for projection in self.sequence_projections
            if projection.validation_capability is not None
        }
        if set(capability_ids) != projected_capability_ids:
            raise ValueError(
                "UCSC binding capabilities must match the per-sequence projection trace"
            )
        projected_binding_ids = {
            projection.sequence_binding.id
            for projection in self.sequence_projections
            if projection.sequence_binding is not None
        }
        if not supplemental_ids.issubset(projected_binding_ids):
            raise ValueError("UCSC supplemental bindings must have per-sequence projection trace")
        if any(
            binding.anchor_resource_id != self.reference_context.anchor_resource_id
            for binding in self.sequence_bindings
        ):
            raise ValueError("UCSC preflight sequence bindings must target the selected anchor")


def project_ucsc_preflight(
    request: EvaluationRequest,
    target: UcscPreflightTarget,
    provider_snapshot: UcscProviderSnapshot | None,
    reference_context: ReferenceContext,
    contracts: tuple[ResourceContract, ...],
) -> UcscPreflightProjection:
    """Add mandatory UCSC target-binding requirements to scoped peer contracts.

    The provider target is explicit and fixed before reasoning. Every peer
    sequence already required by a core presence requirement receives one
    profile-origin ``SequenceBindingRequirement``. A provider name/target chain
    produces a positive validation only after the canonical UCSC target is
    content-bound to the selected FASTA anchor. Exhaustive provider-target
    absence produces a hard negative validation. An independently established
    peer identity binding to a different anchor target produces a hard content
    conflict. Incomplete or ambiguous relationships contribute no capability and
    therefore remain unresolved in the generic reasoner.
    """

    _validate_projection_inputs(request, target, provider_snapshot, reference_context, contracts)
    ordered_contracts = _ordered_contracts(request, contracts)
    existing_bindings = derive_sequence_bindings(reference_context, ordered_contracts)
    effective_by_key = {
        (binding.resource_id, binding.local_sequence_name): binding for binding in existing_bindings
    }

    sequence_projections: list[UcscPreflightSequenceProjection] = []
    supplemental_bindings: list[SequenceBinding] = []
    binding_capabilities: list[SequenceBindingValidationCapability] = []
    projected_contracts: list[ResourceContract] = []

    for contract in ordered_contracts:
        if contract.resource_id == request.anchor_resource_id:
            projected_contracts.append(contract)
            continue

        profile_requirements: list[SequenceBindingRequirement] = []
        for local_name, level in _required_sequence_names(contract):
            requirement = SequenceBindingRequirement(
                id=_binding_requirement_id(
                    target,
                    request.anchor_resource_id,
                    contract.resource_id,
                    local_name,
                ),
                resource_id=contract.resource_id,
                anchor_resource_id=request.anchor_resource_id,
                origin=RequirementOrigin.PROFILE,
                level=level,
                sequence_name=local_name,
            )
            profile_requirements.append(requirement)

            name_resolution = (
                resolve_ucsc_sequence_name(provider_snapshot, local_name)
                if provider_snapshot is not None
                else UcscNameResolution(
                    local_name,
                    UcscNameResolutionState.UNRESOLVED,
                    UcscNameResolutionReason.PROVIDER_EVIDENCE_UNAVAILABLE,
                )
            )
            target_resolution: UcscTargetResolution | None = None
            sequence_binding: SequenceBinding | None = None
            validation_capability: SequenceBindingValidationCapability | None = None

            if name_resolution.state is UcscNameResolutionState.RESOLVED:
                assert provider_snapshot is not None
                assert name_resolution.canonical_name is not None
                target_resolution = resolve_ucsc_target(
                    provider_snapshot,
                    reference_context,
                    name_resolution.canonical_name,
                )
                if target_resolution.state is UcscTargetResolutionState.BOUND:
                    assert target_resolution.binding is not None
                    target_binding = target_resolution.binding
                    key = (contract.resource_id, local_name)
                    existing = effective_by_key.get(key)
                    local_identities = tuple(
                        capability
                        for capability in contract.capabilities
                        if isinstance(capability, SequenceIdentityCapability)
                        and capability.sequence_name == local_name
                    )
                    if existing is None and not identity_evidence_is_consistent_with_anchor_target(
                        reference_context,
                        local_identities,
                        target_binding.anchor_sequence_name,
                    ):
                        sequence_binding = None
                    elif existing is None:
                        sequence_binding = _authoritative_sequence_binding(
                            contract.resource_id,
                            local_name,
                            name_resolution,
                            target_binding,
                        )
                        effective_by_key[key] = sequence_binding
                        supplemental_bindings.append(sequence_binding)
                    elif existing.anchor_sequence_name == target_binding.anchor_sequence_name:
                        sequence_binding = existing
                    else:
                        sequence_binding = existing
                        validation_capability = _content_conflict_validation_capability(
                            contract.resource_id,
                            local_name,
                            name_resolution,
                            target_resolution,
                            existing,
                        )

                    if sequence_binding is not None and validation_capability is None:
                        validation_capability = _bound_validation_capability(
                            contract.resource_id,
                            local_name,
                            name_resolution,
                            target_resolution,
                            sequence_binding,
                        )
                elif target_resolution.state is UcscTargetResolutionState.PROVEN_ABSENT:
                    validation_capability = _absent_validation_capability(
                        contract.resource_id,
                        local_name,
                        name_resolution,
                        target_resolution,
                        provider_snapshot,
                        request.anchor_resource_id,
                    )

            if validation_capability is not None:
                binding_capabilities.append(validation_capability)
            sequence_projections.append(
                UcscPreflightSequenceProjection(
                    resource_id=contract.resource_id,
                    local_sequence_name=local_name,
                    requirement=requirement,
                    name_resolution=name_resolution,
                    target_resolution=target_resolution,
                    sequence_binding=sequence_binding,
                    validation_capability=validation_capability,
                )
            )

        projected_contracts.append(
            ResourceContract(
                resource_id=contract.resource_id,
                requirements=(*contract.requirements, *profile_requirements),
                capabilities=contract.capabilities,
            )
        )

    return UcscPreflightProjection(
        target=target,
        provider_snapshot=provider_snapshot,
        reference_context=reference_context,
        contracts=tuple(projected_contracts),
        sequence_projections=tuple(sequence_projections),
        sequence_bindings=tuple(effective_by_key.values()),
        supplemental_sequence_bindings=tuple(supplemental_bindings),
        binding_capabilities=tuple(binding_capabilities),
    )


def _validate_projection_inputs(
    request: EvaluationRequest,
    target: UcscPreflightTarget,
    provider_snapshot: UcscProviderSnapshot | None,
    reference_context: ReferenceContext,
    contracts: tuple[ResourceContract, ...],
) -> None:
    if UCSC_PREFLIGHT_PROFILE_ID not in request.active_profiles:
        raise ValueError("UCSC preflight projection requires the ucsc-preflight profile")
    unsupported_profiles = tuple(
        profile_id
        for profile_id in request.active_profiles
        if profile_id != UCSC_PREFLIGHT_PROFILE_ID
    )
    if unsupported_profiles:
        raise ValueError("UCSC preflight projection cannot silently ignore other active profiles")
    if provider_snapshot is not None and target.database_id != provider_snapshot.database_id:
        raise ValueError("selected UCSC database must match the provider snapshot")
    if reference_context.anchor_resource_id != request.anchor_resource_id:
        raise ValueError("UCSC preflight reference context must use the request FASTA anchor")
    if reference_context.scope != request.scope:
        raise ValueError("UCSC preflight reference context must use the request scope")
    resource_ids = tuple(contract.resource_id for contract in contracts)
    if len(set(resource_ids)) != len(resource_ids):
        raise ValueError("UCSC preflight contracts must have unique resource IDs")
    if set(resource_ids) != set(request.scope.resource_ids):
        raise ValueError("UCSC preflight projection requires one contract per scoped resource")


def _ordered_contracts(
    request: EvaluationRequest,
    contracts: tuple[ResourceContract, ...],
) -> tuple[ResourceContract, ...]:
    by_id = {contract.resource_id: contract for contract in contracts}
    return tuple(by_id[resource_id] for resource_id in request.scope.resource_ids)


def _required_sequence_names(
    contract: ResourceContract,
) -> tuple[tuple[str, RequirementLevel], ...]:
    levels: dict[str, RequirementLevel] = {}
    order: list[str] = []
    for requirement in contract.requirements:
        if not isinstance(requirement, SequencePresenceRequirement):
            continue
        if requirement.sequence_name not in levels:
            levels[requirement.sequence_name] = requirement.level
            order.append(requirement.sequence_name)
        elif requirement.level is RequirementLevel.MANDATORY:
            levels[requirement.sequence_name] = RequirementLevel.MANDATORY
    return tuple((name, levels[name]) for name in order)


def _authoritative_sequence_binding(
    resource_id: ResourceId,
    local_name: str,
    name_resolution: UcscNameResolution,
    target_binding: UcscTargetBinding,
) -> SequenceBinding:
    return SequenceBinding(
        id=_authoritative_binding_id(resource_id, local_name, name_resolution, target_binding),
        resource_id=resource_id,
        local_sequence_name=local_name,
        anchor_resource_id=target_binding.anchor_resource_id,
        anchor_sequence_name=target_binding.anchor_sequence_name,
        method=SequenceBindingMethod.AUTHORITATIVE_NAME,
        identity_values=target_binding.identity_values,
        capability_ids=target_binding.anchor_capability_ids,
    )


def _bound_validation_capability(
    resource_id: ResourceId,
    local_name: str,
    name_resolution: UcscNameResolution,
    target_resolution: UcscTargetResolution,
    sequence_binding: SequenceBinding,
) -> SequenceBindingValidationCapability:
    assert target_resolution.binding is not None
    return SequenceBindingValidationCapability(
        id=_binding_validation_capability_id(
            resource_id,
            local_name,
            name_resolution,
            target_resolution,
            SequenceBindingValidationState.BOUND,
            database_id=target_resolution.binding.database_id,
            context_id=target_resolution.binding.context_id,
            anchor_resource_id=sequence_binding.anchor_resource_id,
        ),
        resource_id=sequence_binding.anchor_resource_id,
        subject_resource_id=resource_id,
        sequence_name=local_name,
        state=SequenceBindingValidationState.BOUND,
        anchor_sequence_name=sequence_binding.anchor_sequence_name,
    )


def _content_conflict_validation_capability(
    resource_id: ResourceId,
    local_name: str,
    name_resolution: UcscNameResolution,
    target_resolution: UcscTargetResolution,
    existing_binding: SequenceBinding,
) -> SequenceBindingValidationCapability:
    assert target_resolution.binding is not None
    target_binding = target_resolution.binding
    if existing_binding.method is not SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY:
        raise ValueError(
            "UCSC content conflict requires an independently identity-derived local binding"
        )
    if existing_binding.anchor_sequence_name == target_binding.anchor_sequence_name:
        raise ValueError("UCSC content conflict requires different anchor targets")
    return SequenceBindingValidationCapability(
        id=_binding_validation_capability_id(
            resource_id,
            local_name,
            name_resolution,
            target_resolution,
            SequenceBindingValidationState.CONTENT_CONFLICT,
            database_id=target_binding.database_id,
            context_id=target_binding.context_id,
            anchor_resource_id=target_binding.anchor_resource_id,
        ),
        resource_id=target_binding.anchor_resource_id,
        subject_resource_id=resource_id,
        sequence_name=local_name,
        state=SequenceBindingValidationState.CONTENT_CONFLICT,
        anchor_sequence_name=target_binding.anchor_sequence_name,
    )


def _absent_validation_capability(
    resource_id: ResourceId,
    local_name: str,
    name_resolution: UcscNameResolution,
    target_resolution: UcscTargetResolution,
    provider_snapshot: UcscProviderSnapshot,
    anchor_resource_id: ResourceId,
) -> SequenceBindingValidationCapability:
    return SequenceBindingValidationCapability(
        id=_binding_validation_capability_id(
            resource_id,
            local_name,
            name_resolution,
            target_resolution,
            SequenceBindingValidationState.PROVEN_ABSENT,
            database_id=provider_snapshot.database_id,
            context_id=provider_snapshot.context_id,
            anchor_resource_id=anchor_resource_id,
        ),
        resource_id=anchor_resource_id,
        subject_resource_id=resource_id,
        sequence_name=local_name,
        state=SequenceBindingValidationState.PROVEN_ABSENT,
    )


def _binding_requirement_id(
    target: UcscPreflightTarget,
    anchor_resource_id: ResourceId,
    resource_id: ResourceId,
    local_name: str,
) -> RequirementId:
    return RequirementId(
        "ucsc-profile-requirement:"
        + _digest(
            [
                str(UCSC_PREFLIGHT_PROFILE_ID),
                str(target.database_id),
                str(anchor_resource_id),
                str(resource_id),
                local_name,
            ]
        )
    )


def _authoritative_binding_id(
    resource_id: ResourceId,
    local_name: str,
    name_resolution: UcscNameResolution,
    target_binding: UcscTargetBinding,
) -> SequenceBindingId:
    return SequenceBindingId(
        "sequence-binding:authoritative-name:"
        + _digest(
            [
                str(resource_id),
                local_name,
                str(name_resolution.canonical_name),
                str(name_resolution.method),
                *(str(source_id) for source_id in name_resolution.provider_source_ids),
                str(target_binding.id),
            ]
        )
    )


def _binding_validation_capability_id(
    resource_id: ResourceId,
    local_name: str,
    name_resolution: UcscNameResolution,
    target_resolution: UcscTargetResolution,
    state: SequenceBindingValidationState,
    *,
    database_id: UcscDatabaseId,
    context_id: UcscProviderContextId,
    anchor_resource_id: ResourceId,
) -> CapabilityId:
    target_trace = (
        str(target_resolution.binding.id)
        if target_resolution.binding is not None
        else [identity.value for identity in target_resolution.identity_values]
    )
    return CapabilityId(
        "ucsc-binding-validation:"
        + _digest(
            [
                str(database_id),
                str(context_id),
                str(anchor_resource_id),
                str(resource_id),
                local_name,
                str(name_resolution.canonical_name),
                str(state),
                target_trace,
                *(str(source_id) for source_id in name_resolution.provider_source_ids),
                *(str(source_id) for source_id in target_resolution.provider_source_ids),
            ]
        )
    )


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
