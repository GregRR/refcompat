"""Tests for deterministic frozen/materialized UCSC provider snapshots."""

from dataclasses import replace
from datetime import timedelta, timezone
from pathlib import Path

import pytest

from refcompat.profiles import (
    UCSC_PROVIDER_SNAPSHOT_SCHEMA,
    load_ucsc_provider_snapshot,
    parse_ucsc_provider_snapshot,
    render_ucsc_provider_snapshot,
    ucsc_provider_snapshot_sha256,
)

_FIXTURE = Path("tests/fixtures/milestone6/ucsc-provider-snapshot.json")
_FIXTURE_SHA256 = "974b22d81a8e760fbfec6f5300b3c4e64c30b04985f2dadb0d7f335c8fd4d98a"


def test_frozen_snapshot_loads_with_exact_artifact_digest() -> None:
    snapshot = load_ucsc_provider_snapshot(_FIXTURE, expected_sha256=_FIXTURE_SHA256)

    assert snapshot.database_id == "testDb"
    assert snapshot.context_id == "testDb@frozen-v1"
    assert snapshot.sequence("chr1") is not None
    assert snapshot.alias_targets("1") == ("chr1",)


def test_rendered_snapshot_is_canonical_and_round_trips() -> None:
    snapshot = load_ucsc_provider_snapshot(_FIXTURE)
    rendered = render_ucsc_provider_snapshot(snapshot)

    assert rendered == _FIXTURE.read_text(encoding="utf-8")
    assert parse_ucsc_provider_snapshot(rendered) == snapshot
    assert ucsc_provider_snapshot_sha256(rendered) == _FIXTURE_SHA256


def test_rendering_is_stable_when_input_fact_order_differs() -> None:
    snapshot = load_ucsc_provider_snapshot(_FIXTURE)
    reordered = replace(snapshot, sources=tuple(reversed(snapshot.sources)))

    assert render_ucsc_provider_snapshot(reordered) == render_ucsc_provider_snapshot(snapshot)


def test_rendering_normalizes_equal_acquisition_instants_to_utc() -> None:
    snapshot = load_ucsc_provider_snapshot(_FIXTURE)
    source = snapshot.sources[0]
    equivalent_time = source.acquired_at.astimezone(timezone(timedelta(hours=-7)))
    shifted = replace(
        snapshot,
        sources=(replace(source, acquired_at=equivalent_time), *snapshot.sources[1:]),
    )

    assert shifted == snapshot
    assert render_ucsc_provider_snapshot(shifted) == render_ucsc_provider_snapshot(snapshot)


def test_snapshot_parser_rejects_unknown_schema() -> None:
    text = _FIXTURE.read_text(encoding="utf-8").replace(
        UCSC_PROVIDER_SNAPSHOT_SCHEMA,
        "refcompat.ucsc-provider-snapshot.v999",
    )

    with pytest.raises(ValueError, match="unsupported UCSC provider snapshot schema"):
        parse_ucsc_provider_snapshot(text)


def test_snapshot_parser_rejects_unknown_fields() -> None:
    text = _FIXTURE.read_text(encoding="utf-8").replace(
        '  "schema":',
        '  "unexpected": true,\n  "schema":',
    )

    with pytest.raises(ValueError, match="unexpected: unexpected"):
        parse_ucsc_provider_snapshot(text)


def test_snapshot_parser_rejects_duplicate_json_keys() -> None:
    text = _FIXTURE.read_text(encoding="utf-8").replace(
        '  "database_id": "testDb",',
        '  "database_id": "testDb",\n  "database_id": "otherDb",',
    )

    with pytest.raises(ValueError, match="duplicate key"):
        parse_ucsc_provider_snapshot(text)


def test_snapshot_parser_reapplies_provider_context_invariants() -> None:
    text = _FIXTURE.read_text(encoding="utf-8").replace(
        '  "context_id": "testDb@frozen-v1",',
        '  "context_id": "testDb@other-context",',
        1,
    )

    with pytest.raises(ValueError, match="one provider context"):
        parse_ucsc_provider_snapshot(text)


def test_snapshot_loader_rejects_artifact_digest_mismatch() -> None:
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_ucsc_provider_snapshot(_FIXTURE, expected_sha256="0" * 64)


def test_snapshot_loader_rejects_invalid_expected_digest() -> None:
    with pytest.raises(ValueError, match="64 hexadecimal digits"):
        load_ucsc_provider_snapshot(_FIXTURE, expected_sha256="not-a-digest")
