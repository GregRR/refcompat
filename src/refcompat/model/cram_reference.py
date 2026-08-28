"""Conservative offline reference policy for future CRAM record decoding.

The SAM header alone cannot establish whether every CRAM container/slice can be
restored without external reference content. These values therefore do not
claim that a reference is required. They record only whether RefCompat has a
safe, explicit local FASTA anchor it may pass to a future reference-dependent
CRAM decoder. The plan selects no ambient or network fallback; provider-level
isolation remains a responsibility of the future decoder adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from refcompat._compat import StrEnum
from refcompat.model.alignment_relationship import (
    AlignmentContentRelationship,
    AlignmentDictionaryRelationshipSummary,
    AlignmentMembershipRelationship,
    AlignmentNamingRelationship,
)
from refcompat.model.resources import ResourceId


class CramOfflineReferenceAction(StrEnum):
    """Permitted action for a future reference-dependent CRAM operation."""

    USE_EXPLICIT_LOCAL_ANCHOR = "use_explicit_local_anchor"
    DEFER_REFERENCE_DEPENDENT_DECODING = "defer_reference_dependent_decoding"


@dataclass(frozen=True, slots=True)
class CramOfflineReferencePlan:
    """Offline-safe reference plan derived from header and FASTA-anchor facts.

    This plan does not assert that CRAM record decoding actually requires an
    external reference. CRAM reference dependency is encoded below the SAM
    header (for example by the compression-header ``RR`` preservation flag and
    per-slice embedded-reference state), so header-only reasoning must not infer
    that property.
    """

    cram_resource_id: ResourceId
    anchor_resource_id: ResourceId
    action: CramOfflineReferenceAction
    anchor_path: Path
    anchor_path_readable: bool
    relationship: AlignmentDictionaryRelationshipSummary
    reference_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.cram_resource_id or not self.anchor_resource_id:
            raise ValueError("CRAM offline-reference resource IDs must not be empty")
        if self.relationship.alignment_resource_id != self.cram_resource_id:
            raise ValueError("CRAM offline-reference relationship must belong to the CRAM resource")
        if self.relationship.fasta_resource_id != self.anchor_resource_id:
            raise ValueError(
                "CRAM offline-reference relationship must use the selected FASTA anchor"
            )

        if self.action is CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR:
            if not self.anchor_path_readable:
                raise ValueError("explicit local CRAM reference requires a readable FASTA anchor")
            if self.reference_path != self.anchor_path:
                raise ValueError(
                    "explicit local CRAM reference must use the selected FASTA anchor path"
                )
            if self.relationship.membership not in {
                AlignmentMembershipRelationship.EXACT,
                AlignmentMembershipRelationship.ALIGNMENT_SUBSET,
            }:
                raise ValueError(
                    "explicit local CRAM reference requires exact or subset anchor membership"
                )
            if self.relationship.naming is not AlignmentNamingRelationship.EXACT:
                raise ValueError("explicit local CRAM reference requires exact sequence names")
            if self.relationship.content is not AlignmentContentRelationship.M5_VERIFIED:
                raise ValueError("explicit local CRAM reference requires complete M5 verification")
            if self.relationship.length_conflict_sequence_names:
                raise ValueError("explicit local CRAM reference forbids declared length conflicts")
            return

        if self.action is CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING:
            if self.reference_path is not None:
                raise ValueError("deferred CRAM record decoding cannot carry a reference path")
            return

        raise AssertionError(f"unhandled CRAM offline-reference action: {self.action!r}")
