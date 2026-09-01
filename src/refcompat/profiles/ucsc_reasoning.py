"""Conservative UCSC target-content and authoritative-name reasoning.

This module reasons only over a fixed :class:`UcscProviderSnapshot` and the
selected FASTA :class:`ReferenceContext`. It performs no network acquisition and
does not create resource-local ``SequenceBinding`` values; profile projection
combines these provider relationships with peer-resource requirements later.
"""

from __future__ import annotations

import hashlib
import json

from refcompat.model.contracts import SequenceIdentityValue
from refcompat.model.reference_context import (
    AnchorIdentityResolutionState,
    ReferenceContext,
)
from refcompat.profiles.ucsc import (
    UcscNameResolution,
    UcscNameResolutionMethod,
    UcscNameResolutionReason,
    UcscNameResolutionState,
    UcscProviderCompleteness,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
    UcscTargetBinding,
    UcscTargetBindingId,
    UcscTargetResolution,
    UcscTargetResolutionReason,
    UcscTargetResolutionState,
)
from refcompat.reasoning.reference_context import resolve_anchor_sequence_identity


def resolve_ucsc_target(
    snapshot: UcscProviderSnapshot,
    context: ReferenceContext,
    canonical_name: str,
) -> UcscTargetResolution:
    """Resolve one represented UCSC target against the complete FASTA anchor.

    Exact UCSC naming is intentionally irrelevant to this content step. The
    provider target must establish a unique content-derived relationship through
    a complete anchor identity scheme, or exhaustive absence through the same
    full-anchor standard. A matching target outside explicit scope remains
    unresolved rather than becoming usable through scope reduction.
    """

    sequence = snapshot.sequence(canonical_name)
    if sequence is None:
        raise ValueError("UCSC target resolution requires a canonical sequence in the snapshot")

    provider_source_ids = _target_source_ids(sequence)
    identities = tuple(
        identity for identity in (sequence.refget_id, sequence.md5) if identity is not None
    )
    if not identities:
        return UcscTargetResolution(
            canonical_name,
            UcscTargetResolutionState.UNRESOLVED,
            UcscTargetResolutionReason.CONTENT_IDENTITY_UNAVAILABLE,
            provider_source_ids=provider_source_ids,
        )

    anchor_resolution = resolve_anchor_sequence_identity(context, identities)
    if anchor_resolution.state is AnchorIdentityResolutionState.MATCHED:
        assert anchor_resolution.anchor_sequence_name is not None
        anchor_sequence = next(
            anchor
            for anchor in context.anchor_snapshot.sequences
            if anchor.local_name == anchor_resolution.anchor_sequence_name
        )
        if anchor_sequence.length != sequence.length:
            return UcscTargetResolution(
                canonical_name,
                UcscTargetResolutionState.UNRESOLVED,
                UcscTargetResolutionReason.PROVIDER_LENGTH_CONFLICT,
                provider_source_ids=provider_source_ids,
            )

        binding = UcscTargetBinding(
            id=_target_binding_id(
                snapshot,
                sequence,
                context,
                anchor_resolution.anchor_sequence_name,
                anchor_resolution.supporting_identity_values,
            ),
            database_id=snapshot.database_id,
            context_id=snapshot.context_id,
            canonical_name=canonical_name,
            anchor_resource_id=context.anchor_resource_id,
            anchor_sequence_name=anchor_resolution.anchor_sequence_name,
            identity_values=anchor_resolution.supporting_identity_values,
            provider_source_ids=provider_source_ids,
            anchor_capability_ids=anchor_resolution.anchor_capability_ids,
        )
        return UcscTargetResolution(
            canonical_name,
            UcscTargetResolutionState.BOUND,
            UcscTargetResolutionReason.CONTENT_BOUND,
            binding=binding,
        )

    if anchor_resolution.state is AnchorIdentityResolutionState.PROVEN_ABSENT:
        return UcscTargetResolution(
            canonical_name,
            UcscTargetResolutionState.PROVEN_ABSENT,
            UcscTargetResolutionReason.EXHAUSTIVE_CONTENT_ABSENCE,
            identity_values=anchor_resolution.supporting_identity_values,
            provider_source_ids=provider_source_ids,
        )

    return UcscTargetResolution(
        canonical_name,
        UcscTargetResolutionState.UNRESOLVED,
        UcscTargetResolutionReason.CONTENT_IDENTITY_UNRESOLVED,
        provider_source_ids=provider_source_ids,
    )


def resolve_ucsc_sequence_name(
    snapshot: UcscProviderSnapshot,
    local_name: str,
) -> UcscNameResolution:
    """Resolve one label to a canonical UCSC target without claiming identity.

    A represented canonical name is direct provider naming evidence. Alternate
    names require a complete canonical catalog, a complete alias dimension, and
    one unique target in that full provider naming context. Missing, partial, or
    ambiguous alias evidence remains unresolved and never implies biological
    absence.
    """

    if not local_name:
        raise ValueError("UCSC sequence-name resolution requires a non-empty local name")

    canonical = snapshot.sequence(local_name)
    if canonical is not None:
        return UcscNameResolution(
            local_name,
            UcscNameResolutionState.RESOLVED,
            UcscNameResolutionReason.CANONICAL_NAME,
            canonical_name=canonical.canonical_name,
            method=UcscNameResolutionMethod.CANONICAL_NAME,
            provider_source_ids=canonical.catalog_source_ids,
        )

    matching_aliases = tuple(alias for alias in snapshot.aliases if alias.alias == local_name)
    naming_source_ids = _alias_naming_source_ids(snapshot, matching_aliases)
    if (
        snapshot.catalog_completeness is not UcscProviderCompleteness.COMPLETE
        or snapshot.alias_completeness is not UcscProviderCompleteness.COMPLETE
    ):
        return UcscNameResolution(
            local_name,
            UcscNameResolutionState.UNRESOLVED,
            UcscNameResolutionReason.ALIAS_EVIDENCE_INCOMPLETE,
            provider_source_ids=naming_source_ids,
        )

    targets = tuple(dict.fromkeys(alias.canonical_name for alias in matching_aliases))
    if not targets:
        return UcscNameResolution(
            local_name,
            UcscNameResolutionState.UNRESOLVED,
            UcscNameResolutionReason.UNDECLARED_NAME,
            provider_source_ids=naming_source_ids,
        )
    if len(targets) != 1:
        return UcscNameResolution(
            local_name,
            UcscNameResolutionState.UNRESOLVED,
            UcscNameResolutionReason.AMBIGUOUS_ALIAS,
            provider_source_ids=naming_source_ids,
        )

    return UcscNameResolution(
        local_name,
        UcscNameResolutionState.RESOLVED,
        UcscNameResolutionReason.AUTHORITATIVE_ALIAS,
        canonical_name=targets[0],
        method=UcscNameResolutionMethod.AUTHORITATIVE_ALIAS,
        provider_source_ids=naming_source_ids,
    )


def _target_source_ids(sequence: UcscSequence) -> tuple[UcscProviderSourceId, ...]:
    return tuple(
        sorted(
            {*sequence.catalog_source_ids, *sequence.identity_source_ids},
            key=str,
        )
    )


def _alias_naming_source_ids(
    snapshot: UcscProviderSnapshot,
    matching_aliases: tuple[UcscSequenceAlias, ...],
) -> tuple[UcscProviderSourceId, ...]:
    return tuple(
        sorted(
            {
                *(
                    source.id
                    for source in snapshot.sources
                    if UcscProviderDimension.SEQUENCE_CATALOG in source.dimensions
                ),
                *_alias_source_ids(snapshot, matching_aliases),
            },
            key=str,
        )
    )


def _alias_source_ids(
    snapshot: UcscProviderSnapshot,
    matching_aliases: tuple[UcscSequenceAlias, ...],
) -> tuple[UcscProviderSourceId, ...]:
    if matching_aliases:
        return tuple(
            sorted(
                {source_id for alias in matching_aliases for source_id in alias.source_ids},
                key=str,
            )
        )
    return tuple(
        sorted(
            {
                source.id
                for source in snapshot.sources
                if UcscProviderDimension.ALIASES in source.dimensions
            },
            key=str,
        )
    )


def _target_binding_id(
    snapshot: UcscProviderSnapshot,
    sequence: UcscSequence,
    context: ReferenceContext,
    anchor_sequence_name: str,
    identities: tuple[SequenceIdentityValue, ...],
) -> UcscTargetBindingId:
    payload = json.dumps(
        [
            str(snapshot.database_id),
            str(snapshot.context_id),
            sequence.canonical_name,
            str(context.anchor_resource_id),
            anchor_sequence_name,
            *sorted(identity.value for identity in identities),
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return UcscTargetBindingId(f"ucsc-target-binding:{hashlib.sha256(payload).hexdigest()}")
