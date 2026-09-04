"""Report-owned relationship and provider/provenance context.

Milestone 7 keeps these DTOs deliberately separate from profile implementation
objects. They retain enough immutable trace to explain an already-derived
scientific result without making provider facts part of generic compatibility
reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NewType

from refcompat._compat import StrEnum
from refcompat.model.contracts import CapabilityId, RequirementId, SequenceIdentityValue
from refcompat.model.evaluation import ProfileId
from refcompat.model.reference_context import SequenceBindingId
from refcompat.model.resources import ResourceId

ProviderContextId = NewType("ProviderContextId", str)
ProviderSourceId = NewType("ProviderSourceId", str)


class ProfileContextKind(StrEnum):
    """Typed report-owned profile/provider context variants."""

    UCSC_PREFLIGHT = "ucsc_preflight"


class ProviderEvidenceDimension(StrEnum):
    """Report-owned provider-evidence dimensions currently exposed by M6."""

    SEQUENCE_CATALOG = "sequence_catalog"
    ALIASES = "aliases"
    CONTENT_IDENTITY = "content_identity"


class ProviderCompletenessState(StrEnum):
    """Completeness of one report-owned provider-evidence dimension."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ProfileNameResolutionState(StrEnum):
    """Whether provider naming resolved one resource-local sequence label."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class ProfileNameResolutionMethod(StrEnum):
    """Report-owned methods by which the current profile resolves a name."""

    CANONICAL_NAME = "canonical_name"
    AUTHORITATIVE_ALIAS = "authoritative_alias"


class ProfileNameResolutionReason(StrEnum):
    """Report-owned reasons for the current profile name-resolution result."""

    CANONICAL_NAME = "canonical_name"
    AUTHORITATIVE_ALIAS = "authoritative_alias"
    ALIAS_EVIDENCE_INCOMPLETE = "alias_evidence_incomplete"
    AMBIGUOUS_ALIAS = "ambiguous_alias"
    UNDECLARED_NAME = "undeclared_name"
    PROVIDER_EVIDENCE_UNAVAILABLE = "provider_evidence_unavailable"


class ProfileTargetResolutionState(StrEnum):
    """Whether one provider target was related to the selected FASTA anchor."""

    BOUND = "bound"
    PROVEN_ABSENT = "proven_absent"
    UNRESOLVED = "unresolved"


class ProfileTargetResolutionReason(StrEnum):
    """Report-owned reasons for current provider-target resolution."""

    CONTENT_BOUND = "content_bound"
    EXHAUSTIVE_CONTENT_ABSENCE = "exhaustive_content_absence"
    CONTENT_IDENTITY_UNAVAILABLE = "content_identity_unavailable"
    CONTENT_IDENTITY_UNRESOLVED = "content_identity_unresolved"
    PROVIDER_LENGTH_CONFLICT = "provider_length_conflict"


@dataclass(frozen=True, slots=True)
class ProviderDimensionCompleteness:
    """Completeness of one provider-evidence dimension in a fixed context."""

    dimension: ProviderEvidenceDimension
    state: ProviderCompletenessState

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, ProviderEvidenceDimension) or not isinstance(
            self.state, ProviderCompletenessState
        ):
            raise ValueError("provider completeness requires typed dimension/state")


@dataclass(frozen=True, slots=True)
class ProviderSourceProvenance:
    """Report-owned provenance for one provider source artifact or endpoint."""

    id: ProviderSourceId
    context_id: ProviderContextId
    locator: str
    acquired_at: datetime
    dimensions: tuple[ProviderEvidenceDimension, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.context_id:
            raise ValueError("provider source identifiers must not be empty")
        if not self.locator:
            raise ValueError("provider source locator must not be empty")
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError("provider source acquisition time must be timezone-aware")
        if not self.dimensions:
            raise ValueError("provider source dimensions must be non-empty")
        if any(
            not isinstance(dimension, ProviderEvidenceDimension) for dimension in self.dimensions
        ):
            raise ValueError("provider source dimensions must be typed")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("provider source dimensions must be unique")


@dataclass(frozen=True, slots=True)
class ProfileSequenceTrace:
    """Report-owned trace of one profile-origin sequence-binding requirement."""

    requirement_id: RequirementId
    resource_id: ResourceId
    local_sequence_name: str
    name_resolution_state: ProfileNameResolutionState
    name_resolution_reason: ProfileNameResolutionReason
    name_resolution_method: ProfileNameResolutionMethod | None = None
    provider_target_name: str | None = None
    target_resolution_state: ProfileTargetResolutionState | None = None
    target_resolution_reason: ProfileTargetResolutionReason | None = None
    target_binding_id: str | None = None
    target_anchor_sequence_name: str | None = None
    target_identity_values: tuple[SequenceIdentityValue, ...] = ()
    target_anchor_capability_ids: tuple[CapabilityId, ...] = ()
    name_provider_source_ids: tuple[ProviderSourceId, ...] = ()
    target_provider_source_ids: tuple[ProviderSourceId, ...] = ()
    sequence_binding_id: SequenceBindingId | None = None
    validation_capability_id: CapabilityId | None = None

    def __post_init__(self) -> None:
        if not self.requirement_id or not self.resource_id or not self.local_sequence_name:
            raise ValueError("profile sequence trace identifiers must not be empty")
        if not isinstance(self.name_resolution_state, ProfileNameResolutionState) or not isinstance(
            self.name_resolution_reason, ProfileNameResolutionReason
        ):
            raise ValueError("profile sequence trace requires typed name-resolution state/reason")
        if self.name_resolution_method is not None and not isinstance(
            self.name_resolution_method, ProfileNameResolutionMethod
        ):
            raise ValueError("profile sequence trace requires a typed name-resolution method")
        if self.target_resolution_state is not None and not isinstance(
            self.target_resolution_state, ProfileTargetResolutionState
        ):
            raise ValueError("profile sequence trace requires a typed target-resolution state")
        if self.target_resolution_reason is not None and not isinstance(
            self.target_resolution_reason, ProfileTargetResolutionReason
        ):
            raise ValueError("profile sequence trace requires a typed target-resolution reason")
        for value, noun in (
            (self.provider_target_name, "provider target name"),
            (self.target_binding_id, "target-binding ID"),
            (self.target_anchor_sequence_name, "target anchor sequence name"),
        ):
            if value is not None and not value:
                raise ValueError(f"profile sequence trace {noun} must not be empty")
        if self.target_resolution_state is None and (
            self.target_resolution_reason is not None
            or self.target_binding_id is not None
            or self.target_anchor_sequence_name is not None
            or self.target_identity_values
            or self.target_anchor_capability_ids
            or self.target_provider_source_ids
        ):
            raise ValueError("profile sequence trace target details require a target resolution")
        if self.target_resolution_state is not None and self.target_resolution_reason is None:
            raise ValueError("profile target resolution requires a reason")
        for values, noun in (
            (self.target_identity_values, "target identity values"),
            (self.target_anchor_capability_ids, "target anchor capability IDs"),
            (self.name_provider_source_ids, "name provider source IDs"),
            (self.target_provider_source_ids, "target provider source IDs"),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"profile sequence trace {noun} must be unique")

        if self.name_resolution_state is ProfileNameResolutionState.RESOLVED:
            if (
                self.name_resolution_method is None
                or self.provider_target_name is None
                or not self.name_provider_source_ids
            ):
                raise ValueError(
                    "resolved profile sequence name requires target, method, and provenance"
                )
            expected_reason = ProfileNameResolutionReason(self.name_resolution_method.value)
            if self.name_resolution_reason is not expected_reason:
                raise ValueError("resolved profile sequence name reason/method must agree")
        elif self.name_resolution_state is ProfileNameResolutionState.UNRESOLVED:
            if self.name_resolution_method is not None or self.provider_target_name is not None:
                raise ValueError("unresolved profile sequence name cannot identify a target")
            if self.target_resolution_state is not None:
                raise ValueError("unresolved profile sequence name cannot resolve a target")
            if self.sequence_binding_id is not None or self.validation_capability_id is not None:
                raise ValueError("unresolved profile sequence name cannot carry binding validation")
            if self.name_resolution_reason in (
                ProfileNameResolutionReason.CANONICAL_NAME,
                ProfileNameResolutionReason.AUTHORITATIVE_ALIAS,
            ):
                raise ValueError("unresolved profile sequence name requires an unresolved reason")

        if self.target_resolution_state is ProfileTargetResolutionState.BOUND:
            if self.target_resolution_reason is not ProfileTargetResolutionReason.CONTENT_BOUND:
                raise ValueError("bound profile target requires content-bound reason")
            if (
                self.target_binding_id is None
                or self.target_anchor_sequence_name is None
                or not self.target_identity_values
                or not self.target_anchor_capability_ids
                or not self.target_provider_source_ids
            ):
                raise ValueError("bound profile target requires complete content-binding trace")
        elif self.target_resolution_state is ProfileTargetResolutionState.PROVEN_ABSENT:
            if (
                self.target_resolution_reason
                is not ProfileTargetResolutionReason.EXHAUSTIVE_CONTENT_ABSENCE
            ):
                raise ValueError("proven-absent profile target requires absence reason")
            if (
                self.target_binding_id is not None
                or self.target_anchor_sequence_name is not None
                or self.target_anchor_capability_ids
                or not self.target_identity_values
                or not self.target_provider_source_ids
            ):
                raise ValueError("proven-absent profile target requires absence provenance")
            if self.sequence_binding_id is not None or self.validation_capability_id is None:
                raise ValueError("proven-absent profile target requires validation without binding")
        elif self.target_resolution_state is ProfileTargetResolutionState.UNRESOLVED:
            if self.target_resolution_reason not in (
                ProfileTargetResolutionReason.CONTENT_IDENTITY_UNAVAILABLE,
                ProfileTargetResolutionReason.CONTENT_IDENTITY_UNRESOLVED,
                ProfileTargetResolutionReason.PROVIDER_LENGTH_CONFLICT,
            ):
                raise ValueError("unresolved profile target requires an unresolved reason")
            if (
                self.target_binding_id is not None
                or self.target_anchor_sequence_name is not None
                or self.target_anchor_capability_ids
                or self.target_identity_values
            ):
                raise ValueError("unresolved profile target cannot carry content proof")
            if self.sequence_binding_id is not None or self.validation_capability_id is not None:
                raise ValueError("unresolved profile target cannot carry binding validation")


@dataclass(frozen=True, slots=True)
class ProfileProvenanceContext:
    """Provider/profile context retained for traceable report interpretation.

    ``provider_context_id`` is absent when provider evidence was unavailable.
    In that case no provider source/completeness facts may be present, while the
    per-sequence traces can still explain the unresolved profile requirements.
    """

    kind: ProfileContextKind
    profile_id: ProfileId
    provider: str
    target: str
    provider_context_id: ProviderContextId | None
    completeness: tuple[ProviderDimensionCompleteness, ...] = ()
    sources: tuple[ProviderSourceProvenance, ...] = ()
    sequence_traces: tuple[ProfileSequenceTrace, ...] = ()

    def __post_init__(self) -> None:
        if not self.profile_id or not self.provider or not self.target:
            raise ValueError("profile provenance context identifiers must not be empty")
        if not isinstance(self.kind, ProfileContextKind):
            raise ValueError("profile provenance context kind must be typed")
        dimensions = tuple(item.dimension for item in self.completeness)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("profile provenance completeness dimensions must be unique")
        source_ids = tuple(source.id for source in self.sources)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("profile provenance source IDs must be unique")
        requirement_ids = tuple(trace.requirement_id for trace in self.sequence_traces)
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("profile provenance requirement traces must be unique")

        if self.provider_context_id is None:
            if self.completeness or self.sources:
                raise ValueError(
                    "unavailable provider context cannot carry completeness or source provenance"
                )
            if any(
                trace.name_provider_source_ids or trace.target_provider_source_ids
                for trace in self.sequence_traces
            ):
                raise ValueError("unavailable provider context cannot be cited by source IDs")
            if any(
                trace.name_resolution_reason
                is not ProfileNameResolutionReason.PROVIDER_EVIDENCE_UNAVAILABLE
                for trace in self.sequence_traces
            ):
                raise ValueError(
                    "unavailable provider context requires unavailable-provider trace reasons"
                )
            return

        expected_dimensions = set(ProviderEvidenceDimension)
        if set(dimensions) != expected_dimensions:
            raise ValueError(
                "available profile provenance requires all provider completeness dimensions"
            )
        if not self.sources:
            raise ValueError("available profile provenance requires provider sources")

        if any(source.context_id != self.provider_context_id for source in self.sources):
            raise ValueError("profile provenance sources must belong to the provider context")
        known_source_ids = set(source_ids)
        cited_source_ids = {
            source_id
            for trace in self.sequence_traces
            for source_id in (*trace.name_provider_source_ids, *trace.target_provider_source_ids)
        }
        if not cited_source_ids.issubset(known_source_ids):
            raise ValueError("profile sequence trace cites an unknown provider source")
