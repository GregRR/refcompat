"""Immutable provider facts for the UCSC preflight profile.

The values in this module describe one fixed provider snapshot. They do not
select a reference, establish a FASTA binding, or make compatibility claims.
Network/file acquisition belongs outside this model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NewType

from refcompat._compat import StrEnum
from refcompat.model.identity import Md5Digest, RefgetSequenceId

UcscDatabaseId = NewType("UcscDatabaseId", str)
UcscProviderContextId = NewType("UcscProviderContextId", str)
UcscProviderSourceId = NewType("UcscProviderSourceId", str)


class UcscProviderDimension(StrEnum):
    """Independent provider-evidence dimensions retained by one snapshot."""

    SEQUENCE_CATALOG = "sequence_catalog"
    ALIASES = "aliases"
    CONTENT_IDENTITY = "content_identity"


class UcscProviderCompleteness(StrEnum):
    """How completely one provider-evidence dimension covers the selected db."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class UcscProviderSource:
    """Provenance for one source consulted while constructing a snapshot."""

    id: UcscProviderSourceId
    database_id: UcscDatabaseId
    context_id: UcscProviderContextId
    locator: str
    acquired_at: datetime
    dimensions: tuple[UcscProviderDimension, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("UCSC provider source ID must not be empty")
        if not self.database_id:
            raise ValueError("UCSC provider source database ID must not be empty")
        if not self.context_id:
            raise ValueError("UCSC provider source context ID must not be empty")
        if not self.locator:
            raise ValueError("UCSC provider source locator must not be empty")
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError("UCSC provider source acquisition time must be timezone-aware")
        if not self.dimensions:
            raise ValueError("UCSC provider source must identify at least one evidence dimension")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("UCSC provider source dimensions must be unique")


@dataclass(frozen=True, slots=True)
class UcscSequence:
    """Canonical UCSC target sequence facts from one provider snapshot."""

    canonical_name: str
    length: int
    catalog_source_ids: tuple[UcscProviderSourceId, ...]
    refget_id: RefgetSequenceId | None = None
    md5: Md5Digest | None = None
    identity_source_ids: tuple[UcscProviderSourceId, ...] = ()

    def __post_init__(self) -> None:
        if not self.canonical_name:
            raise ValueError("UCSC canonical sequence name must not be empty")
        if self.length < 0:
            raise ValueError("UCSC canonical sequence length must not be negative")
        _validate_source_ids(
            self.catalog_source_ids,
            noun="UCSC sequence catalog source IDs",
            required=True,
        )
        has_identity = self.refget_id is not None or self.md5 is not None
        _validate_source_ids(
            self.identity_source_ids,
            noun="UCSC sequence identity source IDs",
            required=has_identity,
        )
        if not has_identity and self.identity_source_ids:
            raise ValueError("UCSC sequence without content identity cannot cite identity sources")

    @property
    def has_content_identity(self) -> bool:
        """Return whether at least one independently comparable identity is present."""

        return self.refget_id is not None or self.md5 is not None


@dataclass(frozen=True, slots=True)
class UcscSequenceAlias:
    """One provider-declared alternate name for a canonical UCSC sequence."""

    alias: str
    canonical_name: str
    source_ids: tuple[UcscProviderSourceId, ...]
    authority: str | None = None

    def __post_init__(self) -> None:
        if not self.alias:
            raise ValueError("UCSC sequence alias must not be empty")
        if not self.canonical_name:
            raise ValueError("UCSC alias canonical sequence name must not be empty")
        if self.authority is not None and not self.authority:
            raise ValueError("UCSC alias authority must not be empty when provided")
        _validate_source_ids(
            self.source_ids,
            noun="UCSC alias source IDs",
            required=True,
        )


@dataclass(frozen=True, slots=True)
class UcscProviderSnapshot:
    """Deterministic provider facts for one explicitly selected UCSC database.

    The three completeness values are intentionally independent. ``COMPLETE``
    means complete for the selected native UCSC database context, not merely
    complete for the rows returned by one partial request.

    Ambiguous aliases are preserved as evidence. Later binding logic must prove
    unique resolution in this complete provider context rather than relying on
    this model to discard competing mappings.
    """

    database_id: UcscDatabaseId
    context_id: UcscProviderContextId
    sequences: tuple[UcscSequence, ...]
    aliases: tuple[UcscSequenceAlias, ...]
    catalog_completeness: UcscProviderCompleteness
    alias_completeness: UcscProviderCompleteness
    identity_completeness: UcscProviderCompleteness
    sources: tuple[UcscProviderSource, ...]

    def __post_init__(self) -> None:
        if not self.database_id:
            raise ValueError("UCSC provider snapshot database ID must not be empty")
        if not self.context_id:
            raise ValueError("UCSC provider snapshot context ID must not be empty")
        if not self.sequences:
            raise ValueError("UCSC provider snapshot must contain at least one sequence")
        if not self.sources:
            raise ValueError("UCSC provider snapshot must contain provider provenance")

        canonical_names = tuple(sequence.canonical_name for sequence in self.sequences)
        if len(set(canonical_names)) != len(canonical_names):
            raise ValueError("UCSC provider snapshot canonical sequence names must be unique")

        source_ids = tuple(source.id for source in self.sources)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("UCSC provider snapshot source IDs must be unique")
        source_by_id = {source.id: source for source in self.sources}
        if any(source.database_id != self.database_id for source in self.sources):
            raise ValueError("UCSC provider snapshot sources must belong to the selected database")
        if any(source.context_id != self.context_id for source in self.sources):
            raise ValueError("UCSC provider snapshot sources must belong to one provider context")

        for sequence in self.sequences:
            _validate_source_dimension(
                sequence.catalog_source_ids,
                source_by_id,
                UcscProviderDimension.SEQUENCE_CATALOG,
                noun=f"UCSC sequence {sequence.canonical_name!r} catalog",
            )
            _validate_source_dimension(
                sequence.identity_source_ids,
                source_by_id,
                UcscProviderDimension.CONTENT_IDENTITY,
                noun=f"UCSC sequence {sequence.canonical_name!r} identity",
            )

        canonical_name_set = set(canonical_names)
        alias_keys: list[tuple[str, str, str | None]] = []
        for alias in self.aliases:
            if alias.canonical_name not in canonical_name_set:
                raise ValueError("UCSC alias target must exist in the snapshot sequence catalog")
            if alias.alias in canonical_name_set and alias.alias != alias.canonical_name:
                raise ValueError("UCSC alias cannot reuse another canonical sequence name")
            _validate_source_dimension(
                alias.source_ids,
                source_by_id,
                UcscProviderDimension.ALIASES,
                noun=f"UCSC alias {alias.alias!r}",
            )
            alias_keys.append((alias.alias, alias.canonical_name, alias.authority))
        if len(set(alias_keys)) != len(alias_keys):
            raise ValueError("UCSC provider snapshot alias records must be unique")

        if self.alias_completeness is not UcscProviderCompleteness.UNKNOWN and not any(
            UcscProviderDimension.ALIASES in source.dimensions for source in self.sources
        ):
            raise ValueError(
                "known UCSC alias completeness requires an alias-evidence provider source"
            )

        identities_present = tuple(sequence.has_content_identity for sequence in self.sequences)
        if self.identity_completeness is UcscProviderCompleteness.COMPLETE:
            if self.catalog_completeness is not UcscProviderCompleteness.COMPLETE:
                raise ValueError(
                    "complete UCSC identity coverage requires a complete sequence catalog"
                )
            if not all(identities_present):
                raise ValueError(
                    "complete UCSC identity coverage requires content identity for every sequence"
                )
        if self.identity_completeness is UcscProviderCompleteness.PARTIAL:
            if not any(identities_present):
                raise ValueError("partial UCSC identity coverage requires at least one identity")
            if all(identities_present) and (
                self.catalog_completeness is UcscProviderCompleteness.COMPLETE
            ):
                raise ValueError(
                    "partial UCSC identity coverage cannot cover every sequence "
                    "in a complete catalog"
                )

    def sequence(self, canonical_name: str) -> UcscSequence | None:
        """Return one canonical sequence without interpreting aliases."""

        return next(
            (sequence for sequence in self.sequences if sequence.canonical_name == canonical_name),
            None,
        )

    def alias_targets(self, alias_name: str) -> tuple[str, ...]:
        """Return distinct canonical targets for one provider-declared alias.

        Multiple authority columns may repeat the same relationship; distinct
        targets are preserved so later reasoning can detect real ambiguity.
        """

        targets: list[str] = []
        for alias in self.aliases:
            if alias.alias == alias_name and alias.canonical_name not in targets:
                targets.append(alias.canonical_name)
        return tuple(targets)


def _validate_source_ids(
    source_ids: tuple[UcscProviderSourceId, ...],
    *,
    noun: str,
    required: bool,
) -> None:
    if required and not source_ids:
        raise ValueError(f"{noun} must not be empty")
    if any(not source_id for source_id in source_ids):
        raise ValueError(f"{noun} must not contain empty IDs")
    if len(set(source_ids)) != len(source_ids):
        raise ValueError(f"{noun} must be unique")


def _validate_source_dimension(
    source_ids: tuple[UcscProviderSourceId, ...],
    source_by_id: dict[UcscProviderSourceId, UcscProviderSource],
    dimension: UcscProviderDimension,
    *,
    noun: str,
) -> None:
    for source_id in source_ids:
        source = source_by_id.get(source_id)
        if source is None:
            raise ValueError(f"{noun} references an unknown provider source")
        if dimension not in source.dimensions:
            raise ValueError(f"{noun} source does not provide the required evidence dimension")
