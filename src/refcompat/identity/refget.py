"""GA4GH refget/SeqCol identity adapter.

The external ``refget`` package currently delegates local FASTA digestion to
``gtars.refget``. RefCompat deliberately copies the resulting standards-backed
values into its own immutable model at this boundary so upstream pre-1.0 Python
object layouts cannot leak into compatibility reasoning.

References:
- GA4GH Refget Sequence Collections v1.0.0: https://ga4gh.github.io/refget/seqcols/
- refget 0.12 local API: https://github.com/refgenie/refget/tree/v0.12.0
- gtars refget Python API: https://docs.bedbase.org/gtars/python/refget-api/
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from os import PathLike
from pathlib import Path
from typing import Protocol, cast

from refcompat.identity.protocol import ReferenceIdentityProvider
from refcompat.model.identity import (
    CollectionCompleteness,
    IdentityProviderInfo,
    Md5Digest,
    RefgetSequenceId,
    SeqColAttributeDigest,
    SeqColDigest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.resources import Resource, ResourceKind


class ReferenceIdentityError(Exception):
    """Base class for normalized local reference-identity failures."""


class ReferenceUnreadableError(ReferenceIdentityError):
    """The supplied reference artifact cannot be read locally."""


class ReferenceParseError(ReferenceIdentityError):
    """The supplied reference artifact cannot be parsed as the requested format."""


class IdentityComputationError(ReferenceIdentityError):
    """Identity computation failed after the resource was successfully opened."""


class IdentityProviderIncompatibleError(ReferenceIdentityError):
    """The configured provider is unavailable or exposes an unsupported API shape."""


class UnsupportedResourceKindError(ReferenceIdentityError):
    """The requested identity operation does not support this resource kind."""


class _ExternalSequenceMetadata(Protocol):
    name: object
    length: object
    sha512t24u: object
    md5: object


class _ExternalSequenceRecord(Protocol):
    metadata: _ExternalSequenceMetadata


class _ExternalSeqColLevel1(Protocol):
    names_digest: object
    lengths_digest: object
    sequences_digest: object


class _ExternalSequenceCollection(Protocol):
    sequences: Sequence[_ExternalSequenceRecord]
    digest: object
    lvl1: _ExternalSeqColLevel1


class _RefgetModule(Protocol):
    __version__: object

    def digest_fasta(self, fasta: str | PathLike[str]) -> object: ...


@dataclass(frozen=True, slots=True)
class _SequenceValues:
    """Primitive values copied from one upstream sequence record."""

    name: str
    length: int
    sha512t24u: str
    md5: str


@dataclass(frozen=True, slots=True)
class _CollectionValues:
    """Primitive values copied from the upstream collection before domain wrapping."""

    sequences: tuple[_SequenceValues, ...]
    digest: str
    names_digest: str
    lengths_digest: str
    sequences_digest: str


def _load_refget() -> _RefgetModule:
    """Load the required provider without exposing its module type elsewhere."""
    try:
        module = import_module("refget")
    except ImportError as exc:  # pragma: no cover - required dependency in normal installs
        raise IdentityProviderIncompatibleError("refget is not importable") from exc
    return cast(_RefgetModule, module)


def _require_readable(path: Path) -> None:
    """Verify that a local path can currently be opened for reading."""
    try:
        with path.open("rb"):
            pass
    except OSError as exc:
        raise ReferenceUnreadableError(f"cannot read FASTA: {path}") from exc


def _extract_collection_values(external: _ExternalSequenceCollection) -> _CollectionValues:
    """Copy the documented upstream result shape into primitive local values."""
    try:
        external_sequences = tuple(external.sequences)
        digest = external.digest
        names_digest = external.lvl1.names_digest
        lengths_digest = external.lvl1.lengths_digest
        sequences_digest = external.lvl1.sequences_digest
    except (AttributeError, TypeError) as exc:
        raise IdentityProviderIncompatibleError(
            "refget returned an unsupported FASTA identity result"
        ) from exc

    collection_digests = (digest, names_digest, lengths_digest, sequences_digest)
    if not all(isinstance(value, str) for value in collection_digests):
        raise IdentityProviderIncompatibleError(
            "refget returned non-string collection identity metadata"
        )

    sequences: list[_SequenceValues] = []
    for external_sequence in external_sequences:
        try:
            metadata = external_sequence.metadata
            name = metadata.name
            length = metadata.length
            sha512t24u = metadata.sha512t24u
            md5 = metadata.md5
        except (AttributeError, TypeError) as exc:
            raise IdentityProviderIncompatibleError(
                "refget returned an unsupported FASTA sequence result"
            ) from exc

        if not isinstance(name, str):
            raise IdentityProviderIncompatibleError("refget returned a non-string sequence name")
        if not isinstance(length, int) or isinstance(length, bool):
            raise IdentityProviderIncompatibleError("refget returned a non-integer sequence length")
        if length < 0:
            raise IdentityProviderIncompatibleError("refget returned a negative sequence length")
        if not isinstance(sha512t24u, str) or not isinstance(md5, str):
            raise IdentityProviderIncompatibleError(
                "refget returned non-string sequence identity metadata"
            )

        sequences.append(
            _SequenceValues(
                name=name,
                length=length,
                sha512t24u=sha512t24u,
                md5=md5,
            )
        )

    return _CollectionValues(
        sequences=tuple(sequences),
        digest=cast(str, digest),
        names_digest=cast(str, names_digest),
        lengths_digest=cast(str, lengths_digest),
        sequences_digest=cast(str, sequences_digest),
    )


def _validate_fasta_records(values: _CollectionValues, path: Path) -> None:
    """Reject input-derived records that cannot form an unambiguous FASTA anchor."""
    if not values.sequences:
        raise ReferenceParseError(f"FASTA contains no sequence records: {path}")

    names = tuple(sequence.name for sequence in values.sequences)
    if any(not name for name in names):
        raise ReferenceParseError(f"FASTA contains a sequence without a local name: {path}")

    seen: set[str] = set()
    duplicate_names: set[str] = set()
    for name in names:
        if name in seen:
            duplicate_names.add(name)
        seen.add(name)
    if duplicate_names:
        duplicates = ", ".join(repr(name) for name in sorted(duplicate_names))
        raise ReferenceParseError(f"FASTA contains duplicate sequence name(s) {duplicates}: {path}")


def _snapshot_sequences(values: _CollectionValues) -> tuple[SnapshotSequence, ...]:
    """Create RefCompat sequence values after input-level FASTA validation."""
    result: list[SnapshotSequence] = []
    for ordinal, sequence in enumerate(values.sequences):
        try:
            refget_id = RefgetSequenceId(f"SQ.{sequence.sha512t24u}")
            md5 = Md5Digest(sequence.md5)
        except ValueError as exc:
            # Sequence digests are provider-computed metadata. If their shape is
            # invalid, the provider boundary is incompatible rather than the FASTA
            # itself being biologically incompatible.
            raise IdentityProviderIncompatibleError(
                "refget returned invalid sequence identity metadata"
            ) from exc

        result.append(
            SnapshotSequence(
                local_name=sequence.name,
                length=sequence.length,
                ordinal=ordinal,
                refget_id=refget_id,
                md5=md5,
            )
        )
    return tuple(result)


def _snapshot_collection_digests(
    values: _CollectionValues,
) -> tuple[SeqColDigest, SeqColAttributeDigest, SeqColAttributeDigest, SeqColAttributeDigest]:
    """Wrap provider-computed collection digests without redefining SeqCol semantics."""
    try:
        return (
            SeqColDigest(values.digest),
            SeqColAttributeDigest(values.names_digest),
            SeqColAttributeDigest(values.lengths_digest),
            SeqColAttributeDigest(values.sequences_digest),
        )
    except ValueError as exc:
        raise IdentityProviderIncompatibleError(
            "refget returned invalid collection identity metadata"
        ) from exc


class Ga4ghRefgetIdentityProvider(ReferenceIdentityProvider):
    """Use the installed refget implementation for local FASTA identity."""

    def inspect_fasta(self, resource: Resource) -> SequenceCollectionSnapshot:
        """Digest a complete FASTA without network access or remote metadata lookup."""
        if resource.kind is not ResourceKind.FASTA:
            raise UnsupportedResourceKindError(
                f"FASTA identity provider cannot inspect resource kind {resource.kind.value!r}"
            )

        path = resource.artifact.path
        _require_readable(path)

        refget_module = _load_refget()
        try:
            external = cast(_ExternalSequenceCollection, refget_module.digest_fasta(path))
        except OSError as exc:
            # refget 0.12 reports both local I/O failures and some parse failures as
            # OSError. Rechecking readability closes the common deletion/permission
            # race without parsing provider-specific exception strings. A narrower
            # race remains because the upstream API accepts a path, not our already-
            # opened file handle.
            try:
                _require_readable(path)
            except ReferenceUnreadableError as unreadable:
                raise unreadable from exc
            raise ReferenceParseError(f"cannot parse FASTA: {path}") from exc
        except (RuntimeError, ValueError) as exc:
            raise IdentityComputationError(f"cannot compute FASTA identity: {path}") from exc

        values = _extract_collection_values(external)
        _validate_fasta_records(values, path)
        sequences = _snapshot_sequences(values)
        collection_digest, names_digest, lengths_digest, sequences_digest = (
            _snapshot_collection_digests(values)
        )

        version = refget_module.__version__
        if not isinstance(version, str) or not version:
            raise IdentityProviderIncompatibleError("refget returned an invalid provider version")

        return SequenceCollectionSnapshot(
            resource_id=resource.id,
            completeness=CollectionCompleteness.COMPLETE,
            collection_digest=collection_digest,
            names_digest=names_digest,
            lengths_digest=lengths_digest,
            sequences_digest=sequences_digest,
            sequences=sequences,
            provider=IdentityProviderInfo(name="refget", version=version),
        )
