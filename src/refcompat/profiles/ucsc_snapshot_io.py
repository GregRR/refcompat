"""Deterministic file boundary for UCSC provider snapshots.

This module serializes already-materialized provider evidence. It does not fetch
UCSC services and does not participate in compatibility reasoning.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from refcompat.model import Md5Digest, RefgetSequenceId
from refcompat.profiles.ucsc import (
    UcscDatabaseId,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
)

UCSC_PROVIDER_SNAPSHOT_SCHEMA = "refcompat.ucsc-provider-snapshot.v1"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def render_ucsc_provider_snapshot(snapshot: UcscProviderSnapshot) -> str:
    """Render one provider snapshot as deterministic, human-readable JSON."""

    payload = {
        "schema": UCSC_PROVIDER_SNAPSHOT_SCHEMA,
        "database_id": str(snapshot.database_id),
        "context_id": str(snapshot.context_id),
        "completeness": {
            "sequence_catalog": snapshot.catalog_completeness.value,
            "aliases": snapshot.alias_completeness.value,
            "content_identity": snapshot.identity_completeness.value,
        },
        "sources": [
            {
                "id": str(source.id),
                "database_id": str(source.database_id),
                "context_id": str(source.context_id),
                "locator": source.locator,
                "acquired_at": source.acquired_at.astimezone(timezone.utc).isoformat(),
                "dimensions": sorted(dimension.value for dimension in source.dimensions),
            }
            for source in sorted(snapshot.sources, key=lambda item: str(item.id))
        ],
        "sequences": [
            {
                "canonical_name": sequence.canonical_name,
                "length": sequence.length,
                "catalog_source_ids": sorted(str(item) for item in sequence.catalog_source_ids),
                "refget_id": sequence.refget_id.value if sequence.refget_id is not None else None,
                "md5": sequence.md5.value if sequence.md5 is not None else None,
                "identity_source_ids": sorted(str(item) for item in sequence.identity_source_ids),
            }
            for sequence in sorted(snapshot.sequences, key=lambda item: item.canonical_name)
        ],
        "aliases": [
            {
                "alias": alias.alias,
                "canonical_name": alias.canonical_name,
                "source_ids": sorted(str(item) for item in alias.source_ids),
                "authority": alias.authority,
            }
            for alias in sorted(
                snapshot.aliases,
                key=lambda item: (item.alias, item.canonical_name, item.authority or ""),
            )
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def parse_ucsc_provider_snapshot(text: str) -> UcscProviderSnapshot:
    """Parse one strict versioned UCSC provider-snapshot JSON document."""

    try:
        raw: object = json.loads(text, object_pairs_hook=_reject_duplicate_object_keys)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid UCSC provider snapshot JSON") from exc

    root = _mapping(raw, noun="UCSC provider snapshot")
    _require_keys(
        root,
        {
            "schema",
            "database_id",
            "context_id",
            "completeness",
            "sources",
            "sequences",
            "aliases",
        },
        noun="UCSC provider snapshot",
    )
    schema = _string(root["schema"], noun="UCSC provider snapshot schema")
    if schema != UCSC_PROVIDER_SNAPSHOT_SCHEMA:
        raise ValueError("unsupported UCSC provider snapshot schema")

    completeness = _mapping(root["completeness"], noun="UCSC provider completeness")
    _require_keys(
        completeness,
        {"sequence_catalog", "aliases", "content_identity"},
        noun="UCSC provider completeness",
    )

    return UcscProviderSnapshot(
        database_id=UcscDatabaseId(_string(root["database_id"], noun="UCSC database ID")),
        context_id=UcscProviderContextId(_string(root["context_id"], noun="UCSC context ID")),
        sequences=tuple(_sequence(item) for item in _list(root["sequences"], noun="sequences")),
        aliases=tuple(_alias(item) for item in _list(root["aliases"], noun="aliases")),
        catalog_completeness=UcscProviderCompleteness(
            _string(completeness["sequence_catalog"], noun="catalog completeness")
        ),
        alias_completeness=UcscProviderCompleteness(
            _string(completeness["aliases"], noun="alias completeness")
        ),
        identity_completeness=UcscProviderCompleteness(
            _string(completeness["content_identity"], noun="identity completeness")
        ),
        sources=tuple(_source(item) for item in _list(root["sources"], noun="sources")),
    )


def load_ucsc_provider_snapshot(
    path: Path,
    *,
    expected_sha256: str | None = None,
) -> UcscProviderSnapshot:
    """Load a frozen/materialized snapshot, optionally verifying exact file bytes."""

    data = path.read_bytes()
    if expected_sha256 is not None:
        if _SHA256_RE.fullmatch(expected_sha256) is None:
            raise ValueError(
                "expected UCSC provider snapshot SHA-256 must be 64 hexadecimal digits"
            )
        observed = hashlib.sha256(data).hexdigest()
        if observed != expected_sha256.lower():
            raise ValueError("UCSC provider snapshot SHA-256 mismatch")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("UCSC provider snapshot must be UTF-8 JSON") from exc
    return parse_ucsc_provider_snapshot(text)


def ucsc_provider_snapshot_sha256(text: str) -> str:
    """Return the exact UTF-8 artifact digest for rendered snapshot text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source(value: object) -> UcscProviderSource:
    item = _mapping(value, noun="UCSC provider source")
    _require_keys(
        item,
        {"id", "database_id", "context_id", "locator", "acquired_at", "dimensions"},
        noun="UCSC provider source",
    )
    acquired_at_text = _string(item["acquired_at"], noun="provider acquisition time")
    if acquired_at_text.endswith("Z"):
        acquired_at_text = acquired_at_text[:-1] + "+00:00"
    try:
        acquired_at = datetime.fromisoformat(acquired_at_text)
    except ValueError as exc:
        raise ValueError("invalid UCSC provider source acquisition time") from exc
    return UcscProviderSource(
        id=UcscProviderSourceId(_string(item["id"], noun="provider source ID")),
        database_id=UcscDatabaseId(
            _string(item["database_id"], noun="provider source database ID")
        ),
        context_id=UcscProviderContextId(
            _string(item["context_id"], noun="provider source context ID")
        ),
        locator=_string(item["locator"], noun="provider source locator"),
        acquired_at=acquired_at,
        dimensions=tuple(
            UcscProviderDimension(_string(raw_dimension, noun="provider source dimension"))
            for raw_dimension in _list(item["dimensions"], noun="provider source dimensions")
        ),
    )


def _sequence(value: object) -> UcscSequence:
    item = _mapping(value, noun="UCSC sequence")
    _require_keys(
        item,
        {
            "canonical_name",
            "length",
            "catalog_source_ids",
            "refget_id",
            "md5",
            "identity_source_ids",
        },
        noun="UCSC sequence",
    )
    refget_text = _optional_string(item["refget_id"], noun="UCSC refget ID")
    md5_text = _optional_string(item["md5"], noun="UCSC MD5")
    return UcscSequence(
        canonical_name=_string(item["canonical_name"], noun="UCSC canonical sequence name"),
        length=_integer(item["length"], noun="UCSC sequence length"),
        catalog_source_ids=tuple(
            UcscProviderSourceId(_string(raw_id, noun="catalog source ID"))
            for raw_id in _list(item["catalog_source_ids"], noun="catalog source IDs")
        ),
        refget_id=RefgetSequenceId(refget_text) if refget_text is not None else None,
        md5=Md5Digest(md5_text) if md5_text is not None else None,
        identity_source_ids=tuple(
            UcscProviderSourceId(_string(raw_id, noun="identity source ID"))
            for raw_id in _list(item["identity_source_ids"], noun="identity source IDs")
        ),
    )


def _alias(value: object) -> UcscSequenceAlias:
    item = _mapping(value, noun="UCSC alias")
    _require_keys(
        item,
        {"alias", "canonical_name", "source_ids", "authority"},
        noun="UCSC alias",
    )
    return UcscSequenceAlias(
        alias=_string(item["alias"], noun="UCSC alias name"),
        canonical_name=_string(item["canonical_name"], noun="UCSC alias target"),
        source_ids=tuple(
            UcscProviderSourceId(_string(raw_id, noun="alias source ID"))
            for raw_id in _list(item["source_ids"], noun="alias source IDs")
        ),
        authority=_optional_string(item["authority"], noun="alias authority"),
    )


def _reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key in UCSC provider snapshot JSON: {key}")
        result[key] = value
    return result


def _mapping(value: object, *, noun: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{noun} must be a JSON object")
    return cast(dict[str, object], value)


def _list(value: object, *, noun: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{noun} must be a JSON array")
    return cast(list[object], value)


def _string(value: object, *, noun: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{noun} must be a non-empty string")
    return value


def _optional_string(value: object, *, noun: str) -> str | None:
    if value is None:
        return None
    return _string(value, noun=noun)


def _integer(value: object, *, noun: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{noun} must be an integer")
    return value


def _require_keys(value: dict[str, object], expected: set[str], *, noun: str) -> None:
    observed = set(value)
    if observed == expected:
        return
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    details: list[str] = []
    if missing:
        details.append("missing: " + ", ".join(missing))
    if extra:
        details.append("unexpected: " + ", ".join(extra))
    raise ValueError(f"{noun} has invalid fields ({'; '.join(details)})")
