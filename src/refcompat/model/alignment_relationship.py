"""Descriptive BAM/CRAM header-dictionary relationships to a FASTA anchor.

These values summarize what can be established from the declared SAM ``@SQ``
dictionary plus already-verified sequence bindings. They describe header
relationships only; they do not claim that reads use every declared sequence
and they do not replace the generic compatibility verdict machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import StrEnum, assert_never
from refcompat.model.reference_context import SequenceBindingId
from refcompat.model.resources import ResourceId


class AlignmentNameResolutionMethod(StrEnum):
    """Mechanism used to relate one alignment-local ``SN`` to the anchor."""

    EXACT_NAME = "exact_name"
    AUTHORITATIVE_NAME_BINDING = "authoritative_name_binding"
    VERIFIED_M5_BINDING = "verified_m5_binding"


class AlignmentMembershipRelationship(StrEnum):
    """Declared sequence-membership relationship to the selected anchor scope."""

    EXACT = "exact"
    ALIGNMENT_SUBSET = "alignment_subset"
    ALIGNMENT_SUPERSET = "alignment_superset"
    OVERLAP = "overlap"
    DISJOINT = "disjoint"
    UNRESOLVED = "unresolved"


class AlignmentNamingRelationship(StrEnum):
    """How shared alignment-local names relate to anchor-local names."""

    EXACT = "exact"
    VERIFIED_DIFFERENCE = "verified_difference"
    UNRESOLVED = "unresolved"


class AlignmentOrderRelationship(StrEnum):
    """Relative order of resolved shared sequences."""

    CONSISTENT = "consistent"
    DIFFERENT = "different"
    UNRESOLVED = "unresolved"


class AlignmentContentRelationship(StrEnum):
    """M5-backed content relationship for sequences resolved to the anchor."""

    M5_VERIFIED = "m5_verified"
    M5_CONFLICT = "m5_conflict"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class AlignmentSequenceResolution:
    """One alignment-local ``SN`` resolved to one selected anchor sequence."""

    local_sequence_name: str
    anchor_sequence_name: str
    method: AlignmentNameResolutionMethod
    sequence_binding_id: SequenceBindingId | None = None

    def __post_init__(self) -> None:
        if not self.local_sequence_name or not self.anchor_sequence_name:
            raise ValueError("alignment sequence-resolution names must not be empty")
        if self.method is AlignmentNameResolutionMethod.EXACT_NAME:
            if self.local_sequence_name != self.anchor_sequence_name:
                raise ValueError("exact-name alignment resolution requires identical names")
            if self.sequence_binding_id is not None:
                raise ValueError("exact-name alignment resolution cannot cite a sequence binding")
            return
        if self.method is AlignmentNameResolutionMethod.VERIFIED_M5_BINDING:
            if self.local_sequence_name == self.anchor_sequence_name:
                raise ValueError("verified M5 alignment resolution requires a cross-name mapping")
            if self.sequence_binding_id is None:
                raise ValueError("verified M5 alignment resolution requires a sequence-binding ID")
            return
        if self.method is AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING:
            if self.local_sequence_name == self.anchor_sequence_name:
                raise ValueError(
                    "authoritative-name alignment resolution requires a cross-name mapping"
                )
            if self.sequence_binding_id is None:
                raise ValueError(
                    "authoritative-name alignment resolution requires a sequence-binding ID"
                )
            return
        assert_never(self.method)


@dataclass(frozen=True, slots=True)
class AlignmentDictionaryRelationshipSummary:
    """Conservative relationship summary for one BAM/CRAM ``@SQ`` dictionary.

    Membership and order describe the *declared header dictionary* relative to
    the selected FASTA anchor scope. ``m5_distinct_extra_sequence_names`` contains
    only records whose declared M5 does not match any content-derived M5 in the
    complete FASTA anchor. That supports a declared-dictionary relationship; it
    is not independent validation of the alignment-local sequence content.
    """

    alignment_resource_id: ResourceId
    fasta_resource_id: ResourceId
    membership: AlignmentMembershipRelationship
    naming: AlignmentNamingRelationship
    order: AlignmentOrderRelationship
    content: AlignmentContentRelationship
    resolutions: tuple[AlignmentSequenceResolution, ...] = ()
    unresolved_sequence_names: tuple[str, ...] = ()
    m5_distinct_extra_sequence_names: tuple[str, ...] = ()
    duplicate_anchor_target_names: tuple[str, ...] = ()
    length_conflict_sequence_names: tuple[str, ...] = ()
    identity_conflict_sequence_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.alignment_resource_id or not self.fasta_resource_id:
            raise ValueError("alignment relationship resource IDs must not be empty")

        local_names = tuple(item.local_sequence_name for item in self.resolutions)
        if len(set(local_names)) != len(local_names):
            raise ValueError("alignment relationship resolutions must have unique local names")

        for values, noun in (
            (self.unresolved_sequence_names, "unresolved sequence names"),
            (self.m5_distinct_extra_sequence_names, "M5-distinct extra sequence names"),
            (self.duplicate_anchor_target_names, "duplicate anchor target names"),
            (self.length_conflict_sequence_names, "length-conflict sequence names"),
            (self.identity_conflict_sequence_names, "identity-conflict sequence names"),
        ):
            if any(not value for value in values):
                raise ValueError(f"alignment relationship {noun} must not be empty")
            if len(set(values)) != len(values):
                raise ValueError(f"alignment relationship {noun} must be unique")

        resolved_local_names = set(local_names)
        unresolved_names = set(self.unresolved_sequence_names)
        extra_names = set(self.m5_distinct_extra_sequence_names)
        anchor_target_counts: dict[str, int] = {}
        for resolution in self.resolutions:
            anchor_target_counts[resolution.anchor_sequence_name] = (
                anchor_target_counts.get(resolution.anchor_sequence_name, 0) + 1
            )
        actual_duplicate_targets = {
            name for name, count in anchor_target_counts.items() if count > 1
        }
        if set(self.duplicate_anchor_target_names) != actual_duplicate_targets:
            raise ValueError(
                "alignment duplicate anchor targets must exactly match the resolutions"
            )
        if resolved_local_names & unresolved_names:
            raise ValueError("alignment sequences cannot be both resolved and unresolved")
        if resolved_local_names & extra_names:
            raise ValueError("alignment sequences cannot be both resolved and M5-distinct extra")
        if unresolved_names & extra_names:
            raise ValueError("alignment sequences cannot be both unresolved and M5-distinct extra")
        if not set(self.length_conflict_sequence_names).issubset(resolved_local_names) or not set(
            self.identity_conflict_sequence_names
        ).issubset(resolved_local_names):
            raise ValueError("alignment conflicts must name resolved local sequences")
        if (
            self.unresolved_sequence_names
            and self.membership is not AlignmentMembershipRelationship.UNRESOLVED
        ):
            raise ValueError("unresolved alignment sequences require unresolved membership")
        if (
            self.identity_conflict_sequence_names
            and self.content is not AlignmentContentRelationship.M5_CONFLICT
        ):
            raise ValueError("alignment identity conflicts require content=M5_CONFLICT")
        if (
            self.content is AlignmentContentRelationship.M5_CONFLICT
            and not self.identity_conflict_sequence_names
        ):
            raise ValueError("alignment content=M5_CONFLICT requires an identity conflict")
        if (
            self.duplicate_anchor_target_names
            and self.membership is not AlignmentMembershipRelationship.UNRESOLVED
        ):
            raise ValueError("duplicate anchor targets require unresolved membership")

        has_resolution_uncertainty = bool(
            self.unresolved_sequence_names or self.duplicate_anchor_target_names
        )
        if has_resolution_uncertainty or not self.resolutions:
            if self.naming is not AlignmentNamingRelationship.UNRESOLVED:
                raise ValueError(
                    "unresolved or absent alignment resolutions require unresolved naming"
                )
        else:
            has_verified_difference = any(
                resolution.method is not AlignmentNameResolutionMethod.EXACT_NAME
                for resolution in self.resolutions
            )
            expected_naming = (
                AlignmentNamingRelationship.VERIFIED_DIFFERENCE
                if has_verified_difference
                else AlignmentNamingRelationship.EXACT
            )
            if self.naming is not expected_naming:
                raise ValueError("alignment naming relationship must match the resolution methods")

        if self.membership is AlignmentMembershipRelationship.EXACT and extra_names:
            raise ValueError("exact alignment membership cannot include M5-distinct extras")
        if self.membership is AlignmentMembershipRelationship.ALIGNMENT_SUBSET and extra_names:
            raise ValueError("alignment subset membership cannot include M5-distinct extras")
        if (
            self.membership
            in {
                AlignmentMembershipRelationship.ALIGNMENT_SUPERSET,
                AlignmentMembershipRelationship.OVERLAP,
                AlignmentMembershipRelationship.DISJOINT,
            }
            and not extra_names
        ):
            raise ValueError(
                "alignment superset/overlap/disjoint membership requires M5-distinct extras"
            )
        if self.membership is AlignmentMembershipRelationship.DISJOINT and self.resolutions:
            raise ValueError("disjoint alignment membership cannot include resolved sequences")

        order_requires_uncertainty = bool(
            not self.resolutions
            or self.unresolved_sequence_names
            or self.duplicate_anchor_target_names
        )
        if order_requires_uncertainty:
            if self.order is not AlignmentOrderRelationship.UNRESOLVED:
                raise ValueError(
                    "unresolved or absent alignment resolutions require unresolved order"
                )
        elif self.order is AlignmentOrderRelationship.UNRESOLVED:
            raise ValueError(
                "fully resolved alignment mappings require a resolved order relationship"
            )

        if not self.resolutions and self.content is not AlignmentContentRelationship.UNRESOLVED:
            raise ValueError("absent alignment resolutions require unresolved M5 content")
        if (
            self.unresolved_sequence_names
            and self.content is AlignmentContentRelationship.M5_VERIFIED
        ):
            raise ValueError(
                "unresolved alignment sequences cannot claim fully verified M5 content"
            )

        if (
            self.membership
            in {
                AlignmentMembershipRelationship.EXACT,
                AlignmentMembershipRelationship.ALIGNMENT_SUPERSET,
                AlignmentMembershipRelationship.OVERLAP,
            }
            and not self.resolutions
        ):
            raise ValueError(
                "exact/superset/overlap alignment membership requires resolved sequences"
            )

    @property
    def exact_identity(self) -> bool:
        """Whether the declared dictionary is fully M5-verified and exactly aligned."""

        return (
            self.membership is AlignmentMembershipRelationship.EXACT
            and self.naming is AlignmentNamingRelationship.EXACT
            and self.order is AlignmentOrderRelationship.CONSISTENT
            and self.content is AlignmentContentRelationship.M5_VERIFIED
            and not self.length_conflict_sequence_names
        )

    @property
    def verified_naming_only_difference(self) -> bool:
        """Whether verified names are the only difference from the anchor dictionary."""

        return (
            self.membership is AlignmentMembershipRelationship.EXACT
            and self.naming is AlignmentNamingRelationship.VERIFIED_DIFFERENCE
            and self.order is AlignmentOrderRelationship.CONSISTENT
            and self.content is AlignmentContentRelationship.M5_VERIFIED
            and not self.length_conflict_sequence_names
        )
