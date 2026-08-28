"""Typed requirements, capabilities, and context-specific resource contracts.

Requirements describe what an evaluation context needs from a resource or
reference context. Capabilities describe facts that can satisfy those needs.
They remain typed so unrelated scientific questions cannot be compared merely
because their values happen to share a primitive representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType, TypeAlias

from refcompat._compat import StrEnum
from refcompat.model.identity import Md5Digest, RefgetSequenceId
from refcompat.model.observations import ObservationId
from refcompat.model.resources import ResourceId

RequirementId = NewType("RequirementId", str)
CapabilityId = NewType("CapabilityId", str)
SequenceIdentityValue: TypeAlias = RefgetSequenceId | Md5Digest


class SequenceIdentityProvenance(StrEnum):
    """How an identity value became available to the evaluator."""

    CONTENT_DERIVED = "content_derived"
    DECLARED_METADATA = "declared_metadata"


class RequirementOrigin(StrEnum):
    """Source of a compatibility requirement."""

    CORE_FORMAT = "core_format"
    PROFILE = "profile"
    USER_POLICY = "user_policy"


class RequirementLevel(StrEnum):
    """Whether failure to satisfy a requirement can block compatibility."""

    MANDATORY = "mandatory"
    ADVISORY = "advisory"


@dataclass(frozen=True, slots=True)
class SequencePresenceRequirement:
    """Require a resource-local sequence name to be available in context."""

    id: RequirementId
    resource_id: ResourceId
    origin: RequirementOrigin
    level: RequirementLevel
    sequence_name: str

    def __post_init__(self) -> None:
        _validate_requirement_header(self.id, self.resource_id)
        _validate_sequence_name(self.sequence_name)


@dataclass(frozen=True, slots=True)
class SequenceLengthRequirement:
    """Require a local sequence to have an exact length."""

    id: RequirementId
    resource_id: ResourceId
    origin: RequirementOrigin
    level: RequirementLevel
    sequence_name: str
    length: int

    def __post_init__(self) -> None:
        _validate_requirement_header(self.id, self.resource_id)
        _validate_sequence_name(self.sequence_name)
        if self.length < 0:
            raise ValueError("sequence-length requirement must not be negative")


@dataclass(frozen=True, slots=True)
class SequenceIdentityRequirement:
    """Require a local sequence to expose a specific content identity."""

    id: RequirementId
    resource_id: ResourceId
    origin: RequirementOrigin
    level: RequirementLevel
    sequence_name: str
    identity: SequenceIdentityValue

    def __post_init__(self) -> None:
        _validate_requirement_header(self.id, self.resource_id)
        _validate_sequence_name(self.sequence_name)


@dataclass(frozen=True, slots=True)
class SequenceOrderRequirement:
    """Require an exact ordered local sequence-name representation."""

    id: RequirementId
    resource_id: ResourceId
    origin: RequirementOrigin
    level: RequirementLevel
    sequence_names: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_requirement_header(self.id, self.resource_id)
        _validate_sequence_order(self.sequence_names, noun="requirement")


@dataclass(frozen=True, slots=True)
class SequencePresenceCapability:
    """Explicit evidence that a named sequence is present or absent.

    ``present=False`` is meaningful only when the producing context can prove
    absence, such as a complete authoritative reference snapshot. Omitting a
    capability is not equivalent to asserting absence.
    """

    id: CapabilityId
    resource_id: ResourceId
    sequence_name: str
    present: bool
    source_observation_ids: tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        _validate_capability_header(self.id, self.resource_id)
        _validate_sequence_name(self.sequence_name)
        _validate_source_observation_ids(self.source_observation_ids)


@dataclass(frozen=True, slots=True)
class SequenceLengthCapability:
    """Exact observed or standards-backed sequence length."""

    id: CapabilityId
    resource_id: ResourceId
    sequence_name: str
    length: int
    source_observation_ids: tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        _validate_capability_header(self.id, self.resource_id)
        _validate_sequence_name(self.sequence_name)
        _validate_source_observation_ids(self.source_observation_ids)
        if self.length < 0:
            raise ValueError("sequence-length capability must not be negative")


@dataclass(frozen=True, slots=True)
class SequenceIdentityCapability:
    """Sequence identity value with explicit derivation provenance.

    Only ``CONTENT_DERIVED`` identity capabilities may satisfy sequence-identity
    requirements. ``DECLARED_METADATA`` values are claims that may support
    conservative sequence binding but must not become reference authority.
    """

    id: CapabilityId
    resource_id: ResourceId
    sequence_name: str
    identity: SequenceIdentityValue
    provenance: SequenceIdentityProvenance
    source_observation_ids: tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        _validate_capability_header(self.id, self.resource_id)
        _validate_sequence_name(self.sequence_name)
        _validate_source_observation_ids(self.source_observation_ids)


@dataclass(frozen=True, slots=True)
class SequenceOrderCapability:
    """Exact ordered local sequence-name representation exposed by a resource."""

    id: CapabilityId
    resource_id: ResourceId
    sequence_names: tuple[str, ...]
    source_observation_ids: tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        _validate_capability_header(self.id, self.resource_id)
        _validate_sequence_order(self.sequence_names, noun="capability")
        _validate_source_observation_ids(self.source_observation_ids)


@dataclass(frozen=True, slots=True)
class CoordinateBoundsRequirement:
    """Require exhaustive coordinate statements to be representable on one anchor.

    ``anchor_resource_id`` names the selected reference authority against
    which coordinates must be checked. ``coordinate_count`` identifies the
    number of in-scope coordinate statements covered by the exhaustive direct
    validation. Format-specific local details remain in the producing
    validation result rather than becoming one generic requirement per record.
    """

    id: RequirementId
    resource_id: ResourceId
    anchor_resource_id: ResourceId
    origin: RequirementOrigin
    level: RequirementLevel
    coordinate_count: int

    def __post_init__(self) -> None:
        _validate_requirement_header(self.id, self.resource_id)
        if not self.anchor_resource_id:
            raise ValueError("coordinate-bounds requirement anchor resource ID must not be empty")
        if self.coordinate_count < 0:
            raise ValueError("coordinate-bounds requirement count must not be negative")


@dataclass(frozen=True, slots=True)
class CoordinateBoundsValidationCapability:
    """Exhaustive structural coordinate validation against one anchor.

    The capability belongs to the anchor resource and names the subject
    resource whose coordinate statements were checked. ``conflict_count``
    records statements proven not representable in the anchor coordinate
    context; ``unresolved_count`` records statements for which representability
    could not be established.
    """

    id: CapabilityId
    resource_id: ResourceId
    subject_resource_id: ResourceId
    checked_count: int
    representable_count: int
    conflict_count: int
    unresolved_count: int
    source_observation_ids: tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        _validate_capability_header(self.id, self.resource_id)
        if not self.subject_resource_id:
            raise ValueError("coordinate-bounds capability subject resource ID must not be empty")
        counts = (
            self.checked_count,
            self.representable_count,
            self.conflict_count,
            self.unresolved_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("coordinate-bounds capability counts must not be negative")
        if (
            self.representable_count + self.conflict_count + self.unresolved_count
            != self.checked_count
        ):
            raise ValueError(
                "coordinate-bounds capability outcomes must cover every checked record"
            )
        _validate_source_observation_ids(self.source_observation_ids)


@dataclass(frozen=True, slots=True)
class ReferenceBaseRequirement:
    """Require exhaustive reference-base assertions to agree with the anchor.

    ``anchor_resource_id`` names the selected reference authority against
    which the assertions must be checked. ``record_count`` identifies the
    number of format records covered by the exhaustive direct validation that
    must satisfy this requirement. The local per-record details remain in the
    format-specific validation result rather than being expanded into one
    contract object per record.
    """

    id: RequirementId
    resource_id: ResourceId
    anchor_resource_id: ResourceId
    origin: RequirementOrigin
    level: RequirementLevel
    record_count: int

    def __post_init__(self) -> None:
        _validate_requirement_header(self.id, self.resource_id)
        if not self.anchor_resource_id:
            raise ValueError("reference-base requirement anchor resource ID must not be empty")
        if self.record_count < 0:
            raise ValueError("reference-base requirement record count must not be negative")


@dataclass(frozen=True, slots=True)
class ReferenceBaseValidationCapability:
    """Exhaustive direct reference-base validation against one anchor.

    The capability belongs to the anchor resource that supplied the compared
    bases and names the resource whose reference-base assertions were checked.
    ``unresolved_count`` covers records for which direct equality or
    contradiction could not be established, such as unresolved sequence names
    or non-addressable reference spans.
    """

    id: CapabilityId
    resource_id: ResourceId
    subject_resource_id: ResourceId
    checked_count: int
    match_count: int
    mismatch_count: int
    unresolved_count: int
    source_observation_ids: tuple[ObservationId, ...] = ()

    def __post_init__(self) -> None:
        _validate_capability_header(self.id, self.resource_id)
        if not self.subject_resource_id:
            raise ValueError("reference-base capability subject resource ID must not be empty")
        counts = (
            self.checked_count,
            self.match_count,
            self.mismatch_count,
            self.unresolved_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("reference-base capability counts must not be negative")
        if self.match_count + self.mismatch_count + self.unresolved_count != self.checked_count:
            raise ValueError("reference-base capability outcomes must cover every checked record")
        _validate_source_observation_ids(self.source_observation_ids)


Requirement: TypeAlias = (
    SequencePresenceRequirement
    | SequenceLengthRequirement
    | SequenceIdentityRequirement
    | SequenceOrderRequirement
    | CoordinateBoundsRequirement
    | ReferenceBaseRequirement
)
Capability: TypeAlias = (
    SequencePresenceCapability
    | SequenceLengthCapability
    | SequenceIdentityCapability
    | SequenceOrderCapability
    | CoordinateBoundsValidationCapability
    | ReferenceBaseValidationCapability
)
SupplementalCapability: TypeAlias = (
    CoordinateBoundsValidationCapability | ReferenceBaseValidationCapability
)


@dataclass(frozen=True, slots=True)
class ResourceContract:
    """Typed requirements and capabilities for one resource in one context.

    A contract is evaluation-context output, not an intrinsic permanent
    property of the artifact. Profile or user-policy requirements may be
    attached to the affected resource while retaining their distinct origin.
    """

    resource_id: ResourceId
    requirements: tuple[Requirement, ...] = ()
    capabilities: tuple[Capability, ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("resource-contract resource ID must not be empty")
        if any(requirement.resource_id != self.resource_id for requirement in self.requirements):
            raise ValueError("resource-contract requirements must belong to the contract resource")
        if any(capability.resource_id != self.resource_id for capability in self.capabilities):
            raise ValueError("resource-contract capabilities must belong to the contract resource")

        requirement_ids = tuple(requirement.id for requirement in self.requirements)
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("resource-contract requirement IDs must be unique")
        capability_ids = tuple(capability.id for capability in self.capabilities)
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("resource-contract capability IDs must be unique")


def _validate_requirement_header(requirement_id: RequirementId, resource_id: ResourceId) -> None:
    if not requirement_id:
        raise ValueError("requirement ID must not be empty")
    if not resource_id:
        raise ValueError("requirement resource ID must not be empty")


def _validate_capability_header(capability_id: CapabilityId, resource_id: ResourceId) -> None:
    if not capability_id:
        raise ValueError("capability ID must not be empty")
    if not resource_id:
        raise ValueError("capability resource ID must not be empty")


def _validate_sequence_name(sequence_name: str) -> None:
    if not sequence_name:
        raise ValueError("sequence name must not be empty")


def _validate_sequence_order(sequence_names: tuple[str, ...], *, noun: str) -> None:
    if not sequence_names:
        raise ValueError(f"sequence-order {noun} must contain at least one sequence")
    if any(not sequence_name for sequence_name in sequence_names):
        raise ValueError(f"sequence-order {noun} names must not be empty")
    if len(set(sequence_names)) != len(sequence_names):
        raise ValueError(f"sequence-order {noun} names must be unique")


def _validate_source_observation_ids(observation_ids: tuple[ObservationId, ...]) -> None:
    if any(not observation_id for observation_id in observation_ids):
        raise ValueError("capability source observation IDs must not be empty")
    if len(set(observation_ids)) != len(observation_ids):
        raise ValueError("capability source observation IDs must be unique")
