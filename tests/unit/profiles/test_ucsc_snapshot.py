"""Tests for immutable UCSC provider-snapshot invariants."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from refcompat.model import Md5Digest, RefgetSequenceId
from refcompat.profiles import (
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

_DB = UcscDatabaseId("testDb")
_CONTEXT = UcscProviderContextId("testDb:coherent-fixture")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_REFGET = RefgetSequenceId("SQ." + "A" * 32)
_MD5 = Md5Digest("1" * 32)


def _source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
    *,
    database_id: UcscDatabaseId = _DB,
    context_id: UcscProviderContextId = _CONTEXT,
) -> UcscProviderSource:
    return UcscProviderSource(
        id=source_id,
        database_id=database_id,
        context_id=context_id,
        locator=f"fixture://{source_id}",
        acquired_at=_ACQUIRED_AT,
        dimensions=(dimension,),
    )


def _sequence(
    name: str = "chr1",
    *,
    refget_id: RefgetSequenceId | None = _REFGET,
    md5: Md5Digest | None = _MD5,
) -> UcscSequence:
    return UcscSequence(
        canonical_name=name,
        length=100,
        catalog_source_ids=(_CATALOG_SOURCE,),
        refget_id=refget_id,
        md5=md5,
        identity_source_ids=(_IDENTITY_SOURCE,) if refget_id is not None or md5 is not None else (),
    )


def _snapshot(
    *,
    sequences: tuple[UcscSequence, ...] | None = None,
    aliases: tuple[UcscSequenceAlias, ...] = (),
    catalog_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    alias_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    identity_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    sources: tuple[UcscProviderSource, ...] | None = None,
) -> UcscProviderSnapshot:
    if sequences is None:
        sequences = (_sequence(),)
    if sources is None:
        sources = (
            _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
            _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
            _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
        )
    return UcscProviderSnapshot(
        database_id=_DB,
        context_id=_CONTEXT,
        sequences=sequences,
        aliases=aliases,
        catalog_completeness=catalog_completeness,
        alias_completeness=alias_completeness,
        identity_completeness=identity_completeness,
        sources=sources,
    )


def test_provider_snapshot_is_immutable_and_retains_dimensional_completeness() -> None:
    snapshot = _snapshot()

    assert snapshot.catalog_completeness is UcscProviderCompleteness.COMPLETE
    assert snapshot.alias_completeness is UcscProviderCompleteness.COMPLETE
    assert snapshot.identity_completeness is UcscProviderCompleteness.COMPLETE
    with pytest.raises(FrozenInstanceError):
        snapshot.database_id = UcscDatabaseId("otherDb")  # type: ignore[misc]


def test_provider_source_requires_timezone_aware_acquisition_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        UcscProviderSource(
            id=_CATALOG_SOURCE,
            database_id=_DB,
            context_id=_CONTEXT,
            locator="fixture://catalog",
            acquired_at=datetime(2026, 8, 30, 12, 0),
            dimensions=(UcscProviderDimension.SEQUENCE_CATALOG,),
        )


def test_snapshot_rejects_cross_wired_provider_source_database() -> None:
    sources = (
        _source(
            _CATALOG_SOURCE,
            UcscProviderDimension.SEQUENCE_CATALOG,
            database_id=UcscDatabaseId("otherDb"),
        ),
        _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
        _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
    )

    with pytest.raises(ValueError, match="selected database"):
        _snapshot(sources=sources)


def test_snapshot_rejects_cross_wired_provider_source_context() -> None:
    sources = (
        _source(
            _CATALOG_SOURCE,
            UcscProviderDimension.SEQUENCE_CATALOG,
            context_id=UcscProviderContextId("testDb:other-context"),
        ),
        _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
        _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
    )

    with pytest.raises(ValueError, match="one provider context"):
        _snapshot(sources=sources)


def test_snapshot_rejects_duplicate_canonical_sequence_names() -> None:
    with pytest.raises(ValueError, match="canonical sequence names must be unique"):
        _snapshot(sequences=(_sequence("chr1"), _sequence("chr1")))


def test_snapshot_preserves_duplicate_content_under_distinct_names() -> None:
    snapshot = _snapshot(sequences=(_sequence("chr1"), _sequence("chr1_copy")))

    assert snapshot.sequences[0].refget_id == snapshot.sequences[1].refget_id
    assert snapshot.sequences[0].md5 == snapshot.sequences[1].md5


def test_alias_target_must_exist_in_same_snapshot_catalog() -> None:
    alias = UcscSequenceAlias(
        alias="1",
        canonical_name="chr2",
        source_ids=(_ALIAS_SOURCE,),
        authority="ensembl",
    )

    with pytest.raises(ValueError, match="alias target must exist"):
        _snapshot(aliases=(alias,))


def test_alias_cannot_reuse_a_different_canonical_sequence_name() -> None:
    alias = UcscSequenceAlias(
        alias="chr1",
        canonical_name="chr2",
        source_ids=(_ALIAS_SOURCE,),
    )

    with pytest.raises(ValueError, match="reuse another canonical sequence name"):
        _snapshot(
            sequences=(_sequence("chr1"), _sequence("chr2")),
            aliases=(alias,),
        )


def test_ambiguous_alias_targets_are_preserved_for_later_reasoning() -> None:
    aliases = (
        UcscSequenceAlias("shared", "chr1", (_ALIAS_SOURCE,), "authority-a"),
        UcscSequenceAlias("shared", "chr2", (_ALIAS_SOURCE,), "authority-b"),
    )
    snapshot = _snapshot(
        sequences=(_sequence("chr1"), _sequence("chr2")),
        aliases=aliases,
    )

    assert snapshot.alias_targets("shared") == ("chr1", "chr2")


def test_same_alias_target_from_multiple_authorities_remains_unique_target() -> None:
    aliases = (
        UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), "ensembl"),
        UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), "genbank"),
    )
    snapshot = _snapshot(aliases=aliases)

    assert snapshot.alias_targets("1") == ("chr1",)


def test_snapshot_rejects_exact_duplicate_alias_records() -> None:
    alias = UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), "ensembl")

    with pytest.raises(ValueError, match="alias records must be unique"):
        _snapshot(aliases=(alias, alias))


def test_sequence_catalog_fact_requires_catalog_dimension_source() -> None:
    wrong_source = UcscProviderSource(
        id=_CATALOG_SOURCE,
        database_id=_DB,
        context_id=_CONTEXT,
        locator="fixture://wrong",
        acquired_at=_ACQUIRED_AT,
        dimensions=(UcscProviderDimension.ALIASES,),
    )
    sources = (
        wrong_source,
        _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
        _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
    )

    with pytest.raises(ValueError, match="required evidence dimension"):
        _snapshot(sources=sources)


def test_snapshot_rejects_unknown_fact_source_id() -> None:
    sequence = UcscSequence(
        canonical_name="chr1",
        length=100,
        catalog_source_ids=(UcscProviderSourceId("missing"),),
    )

    with pytest.raises(ValueError, match="unknown provider source"):
        _snapshot(
            sequences=(sequence,),
            identity_completeness=UcscProviderCompleteness.UNKNOWN,
        )


def test_sequence_without_identity_rejects_identity_provenance() -> None:
    with pytest.raises(ValueError, match="without content identity"):
        UcscSequence(
            canonical_name="chr1",
            length=100,
            catalog_source_ids=(_CATALOG_SOURCE,),
            identity_source_ids=(_IDENTITY_SOURCE,),
        )


def test_sequence_identity_fact_requires_identity_dimension_source() -> None:
    wrong_source = UcscProviderSource(
        id=_IDENTITY_SOURCE,
        database_id=_DB,
        context_id=_CONTEXT,
        locator="fixture://wrong",
        acquired_at=_ACQUIRED_AT,
        dimensions=(UcscProviderDimension.SEQUENCE_CATALOG,),
    )
    sources = (
        _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
        _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
        wrong_source,
    )

    with pytest.raises(ValueError, match="required evidence dimension"):
        _snapshot(sources=sources)


def test_alias_fact_requires_alias_dimension_source() -> None:
    alias = UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), "ensembl")
    wrong_source = UcscProviderSource(
        id=_ALIAS_SOURCE,
        database_id=_DB,
        context_id=_CONTEXT,
        locator="fixture://wrong",
        acquired_at=_ACQUIRED_AT,
        dimensions=(UcscProviderDimension.SEQUENCE_CATALOG,),
    )
    sources = (
        _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
        wrong_source,
        _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
    )

    with pytest.raises(ValueError, match="required evidence dimension"):
        _snapshot(aliases=(alias,), sources=sources)


def test_known_alias_completeness_requires_alias_evidence_source() -> None:
    sources = (
        _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
        _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
    )

    with pytest.raises(ValueError, match="alias completeness requires"):
        _snapshot(sources=sources)

    snapshot = _snapshot(
        alias_completeness=UcscProviderCompleteness.UNKNOWN,
        sources=sources,
    )
    assert snapshot.alias_completeness is UcscProviderCompleteness.UNKNOWN


def test_alias_completeness_remains_independent_from_catalog_completeness() -> None:
    snapshot = _snapshot(
        catalog_completeness=UcscProviderCompleteness.PARTIAL,
        alias_completeness=UcscProviderCompleteness.COMPLETE,
        identity_completeness=UcscProviderCompleteness.UNKNOWN,
    )

    assert snapshot.catalog_completeness is UcscProviderCompleteness.PARTIAL
    assert snapshot.alias_completeness is UcscProviderCompleteness.COMPLETE


def test_complete_identity_coverage_requires_identity_for_every_sequence() -> None:
    sequences = (_sequence("chr1"), _sequence("chr2", refget_id=None, md5=None))

    with pytest.raises(ValueError, match="identity for every sequence"):
        _snapshot(sequences=sequences)


def test_partial_identity_coverage_requires_some_but_not_complete_coverage() -> None:
    no_identity = (_sequence("chr1", refget_id=None, md5=None),)
    with pytest.raises(ValueError, match="requires at least one identity"):
        _snapshot(
            sequences=no_identity,
            identity_completeness=UcscProviderCompleteness.PARTIAL,
        )

    all_identity = (_sequence("chr1"),)
    with pytest.raises(ValueError, match="cannot cover every sequence"):
        _snapshot(
            sequences=all_identity,
            identity_completeness=UcscProviderCompleteness.PARTIAL,
        )


def test_unknown_identity_completeness_can_preserve_available_identity() -> None:
    snapshot = _snapshot(identity_completeness=UcscProviderCompleteness.UNKNOWN)

    assert snapshot.sequences[0].has_content_identity
    assert snapshot.identity_completeness is UcscProviderCompleteness.UNKNOWN


def test_partial_catalog_can_preserve_partial_alias_evidence_without_proving_completeness() -> None:
    snapshot = _snapshot(
        catalog_completeness=UcscProviderCompleteness.PARTIAL,
        alias_completeness=UcscProviderCompleteness.PARTIAL,
        identity_completeness=UcscProviderCompleteness.UNKNOWN,
    )

    assert snapshot.catalog_completeness is UcscProviderCompleteness.PARTIAL
    assert snapshot.alias_completeness is UcscProviderCompleteness.PARTIAL


def test_sequence_lookup_does_not_interpret_aliases() -> None:
    alias = UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), "ensembl")
    snapshot = _snapshot(aliases=(alias,))

    assert snapshot.sequence("chr1") is not None
    assert snapshot.sequence("1") is None
    assert snapshot.alias_targets("1") == ("chr1",)
