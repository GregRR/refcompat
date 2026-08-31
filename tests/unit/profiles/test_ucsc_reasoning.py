"""Tests for conservative UCSC target-content and authoritative-name reasoning."""

from datetime import datetime, timezone
from pathlib import Path

from refcompat.model import (
    ArtifactIdentity,
    CollectionCompleteness,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ReferenceContext,
    RefgetSequenceId,
    Resource,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.profiles import (
    UcscDatabaseId,
    UcscNameResolutionMethod,
    UcscNameResolutionReason,
    UcscNameResolutionState,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
    UcscTargetResolutionReason,
    UcscTargetResolutionState,
    resolve_ucsc_sequence_name,
    resolve_ucsc_target,
)
from refcompat.reasoning import build_reference_context

_REFERENCE = ResourceId("reference")
_PEER = ResourceId("peer")
_DB = UcscDatabaseId("testDb")
_CONTEXT = UcscProviderContextId("testDb@fixture-v1")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_REFGET_A = RefgetSequenceId("SQ." + "A" * 32)
_REFGET_B = RefgetSequenceId("SQ." + "B" * 32)
_REFGET_C = RefgetSequenceId("SQ." + "C" * 32)
_MD5_A = Md5Digest("1" * 32)


def _source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
) -> UcscProviderSource:
    return UcscProviderSource(
        id=source_id,
        database_id=_DB,
        context_id=_CONTEXT,
        locator=f"fixture://{source_id}",
        acquired_at=_ACQUIRED_AT,
        dimensions=(dimension,),
    )


def _ucsc_sequence(
    name: str,
    length: int,
    *,
    refget_id: RefgetSequenceId | None = None,
    md5: Md5Digest | None = None,
) -> UcscSequence:
    return UcscSequence(
        canonical_name=name,
        length=length,
        catalog_source_ids=(_CATALOG_SOURCE,),
        refget_id=refget_id,
        md5=md5,
        identity_source_ids=(_IDENTITY_SOURCE,) if refget_id is not None or md5 is not None else (),
    )


def _snapshot(
    *,
    sequences: tuple[UcscSequence, ...],
    aliases: tuple[UcscSequenceAlias, ...] = (),
    alias_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    identity_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
) -> UcscProviderSnapshot:
    return UcscProviderSnapshot(
        database_id=_DB,
        context_id=_CONTEXT,
        sequences=sequences,
        aliases=aliases,
        catalog_completeness=UcscProviderCompleteness.COMPLETE,
        alias_completeness=alias_completeness,
        identity_completeness=identity_completeness,
        sources=(
            _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
            _source(_ALIAS_SOURCE, UcscProviderDimension.ALIASES),
            _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
        ),
    )


def _context(
    sequences: tuple[SnapshotSequence, ...],
    scope_names: tuple[str, ...] | None = None,
) -> ReferenceContext:
    resources = (
        Resource(_REFERENCE, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
        Resource(_PEER, ResourceKind.VCF, ArtifactIdentity(path=Path("peer.vcf"))),
    )
    request = EvaluationRequest(
        resources,
        _REFERENCE,
        EvaluationScope((_REFERENCE, _PEER), scope_names),
    )
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )
    return build_reference_context(request, snapshot)


def test_canonical_name_resolves_as_provider_naming_only() -> None:
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),))

    resolution = resolve_ucsc_sequence_name(snapshot, "chr1")

    assert resolution.state is UcscNameResolutionState.RESOLVED
    assert resolution.method is UcscNameResolutionMethod.CANONICAL_NAME
    assert resolution.reason is UcscNameResolutionReason.CANONICAL_NAME
    assert resolution.canonical_name == "chr1"
    assert resolution.provider_source_ids == (_CATALOG_SOURCE,)


def test_unique_authoritative_alias_requires_complete_alias_evidence() -> None:
    alias = UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="ensembl")
    snapshot = _snapshot(
        sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),),
        aliases=(alias,),
        alias_completeness=UcscProviderCompleteness.PARTIAL,
    )

    resolution = resolve_ucsc_sequence_name(snapshot, "1")

    assert resolution.state is UcscNameResolutionState.UNRESOLVED
    assert resolution.reason is UcscNameResolutionReason.ALIAS_EVIDENCE_INCOMPLETE
    assert resolution.canonical_name is None


def test_complete_unique_authoritative_alias_resolves() -> None:
    alias = UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="ensembl")
    snapshot = _snapshot(
        sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),),
        aliases=(alias,),
    )

    resolution = resolve_ucsc_sequence_name(snapshot, "1")

    assert resolution.state is UcscNameResolutionState.RESOLVED
    assert resolution.method is UcscNameResolutionMethod.AUTHORITATIVE_ALIAS
    assert resolution.reason is UcscNameResolutionReason.AUTHORITATIVE_ALIAS
    assert resolution.canonical_name == "chr1"
    assert resolution.provider_source_ids == (_ALIAS_SOURCE,)


def test_alias_repeated_by_multiple_authorities_can_resolve_same_target() -> None:
    aliases = (
        UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="ensembl"),
        UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,), authority="refseq"),
    )
    snapshot = _snapshot(
        sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),),
        aliases=aliases,
    )

    resolution = resolve_ucsc_sequence_name(snapshot, "1")

    assert resolution.state is UcscNameResolutionState.RESOLVED
    assert resolution.canonical_name == "chr1"


def test_ambiguous_authoritative_alias_remains_unresolved() -> None:
    snapshot = _snapshot(
        sequences=(
            _ucsc_sequence("chr1", 10, refget_id=_REFGET_A),
            _ucsc_sequence("chr2", 20, refget_id=_REFGET_B),
        ),
        aliases=(
            UcscSequenceAlias("shared", "chr1", (_ALIAS_SOURCE,)),
            UcscSequenceAlias("shared", "chr2", (_ALIAS_SOURCE,)),
        ),
    )

    resolution = resolve_ucsc_sequence_name(snapshot, "shared")

    assert resolution.state is UcscNameResolutionState.UNRESOLVED
    assert resolution.reason is UcscNameResolutionReason.AMBIGUOUS_ALIAS


def test_familiar_but_undeclared_name_remains_unresolved() -> None:
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),))

    resolution = resolve_ucsc_sequence_name(snapshot, "1")

    assert resolution.state is UcscNameResolutionState.UNRESOLVED
    assert resolution.reason is UcscNameResolutionReason.UNDECLARED_NAME


def test_target_content_binds_independently_of_canonical_name() -> None:
    context = _context((SnapshotSequence("NC_1", 10, 0, _REFGET_A),))
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),))

    resolution = resolve_ucsc_target(snapshot, context, "chr1")

    assert resolution.state is UcscTargetResolutionState.BOUND
    assert resolution.reason is UcscTargetResolutionReason.CONTENT_BOUND
    assert resolution.binding is not None
    assert resolution.binding.canonical_name == "chr1"
    assert resolution.binding.anchor_sequence_name == "NC_1"
    assert resolution.binding.identity_values == (_REFGET_A,)
    assert resolution.binding.provider_source_ids == (_CATALOG_SOURCE, _IDENTITY_SOURCE)
    assert resolution.binding.anchor_capability_ids


def test_exact_name_wrong_content_can_bind_differently_named_matching_anchor() -> None:
    context = _context(
        (
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("alternate", 20, 1, _REFGET_B),
        )
    )
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 20, refget_id=_REFGET_B),))

    resolution = resolve_ucsc_target(snapshot, context, "chr1")

    assert resolution.state is UcscTargetResolutionState.BOUND
    assert resolution.binding is not None
    assert resolution.binding.anchor_sequence_name == "alternate"


def test_matching_name_and_length_without_identity_remains_unresolved() -> None:
    context = _context((SnapshotSequence("chr1", 10, 0, _REFGET_A),))
    snapshot = _snapshot(
        sequences=(_ucsc_sequence("chr1", 10),),
        identity_completeness=UcscProviderCompleteness.UNKNOWN,
    )

    resolution = resolve_ucsc_target(snapshot, context, "chr1")

    assert resolution.state is UcscTargetResolutionState.UNRESOLVED
    assert resolution.reason is UcscTargetResolutionReason.CONTENT_IDENTITY_UNAVAILABLE


def test_duplicate_anchor_content_does_not_create_ucsc_target_binding() -> None:
    context = _context(
        (
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chrDup", 10, 1, _REFGET_A),
        )
    )
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),))

    resolution = resolve_ucsc_target(snapshot, context, "chr1")

    assert resolution.state is UcscTargetResolutionState.UNRESOLVED
    assert resolution.reason is UcscTargetResolutionReason.CONTENT_IDENTITY_UNRESOLVED


def test_scope_cannot_make_duplicate_target_content_unique() -> None:
    context = _context(
        (
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chrDup", 10, 1, _REFGET_A),
        ),
        ("chr1",),
    )
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 10, refget_id=_REFGET_A),))

    resolution = resolve_ucsc_target(snapshot, context, "chr1")

    assert resolution.state is UcscTargetResolutionState.UNRESOLVED


def test_unique_target_outside_scope_remains_unresolved() -> None:
    context = _context(
        (
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chr2", 20, 1, _REFGET_B),
        ),
        ("chr1",),
    )
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr2", 20, refget_id=_REFGET_B),))

    resolution = resolve_ucsc_target(snapshot, context, "chr2")

    assert resolution.state is UcscTargetResolutionState.UNRESOLVED
    assert resolution.reason is UcscTargetResolutionReason.CONTENT_IDENTITY_UNRESOLVED


def test_complete_anchor_identity_can_prove_ucsc_target_absent() -> None:
    context = _context(
        (
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chr2", 20, 1, _REFGET_B),
        )
    )
    snapshot = _snapshot(sequences=(_ucsc_sequence("chrMissing", 30, refget_id=_REFGET_C),))

    resolution = resolve_ucsc_target(snapshot, context, "chrMissing")

    assert resolution.state is UcscTargetResolutionState.PROVEN_ABSENT
    assert resolution.reason is UcscTargetResolutionReason.EXHAUSTIVE_CONTENT_ABSENCE
    assert resolution.identity_values == (_REFGET_C,)
    assert resolution.provider_source_ids == (_CATALOG_SOURCE, _IDENTITY_SOURCE)


def test_incomplete_scheme_positive_match_blocks_false_target_absence() -> None:
    context = _context(
        (
            SnapshotSequence("chr1", 10, 0, _REFGET_A, _MD5_A),
            SnapshotSequence("chr2", 20, 1, _REFGET_B),
        )
    )
    snapshot = _snapshot(sequences=(_ucsc_sequence("chrX", 10, refget_id=_REFGET_C, md5=_MD5_A),))

    resolution = resolve_ucsc_target(snapshot, context, "chrX")

    assert resolution.state is UcscTargetResolutionState.UNRESOLVED
    assert resolution.reason is UcscTargetResolutionReason.CONTENT_IDENTITY_UNRESOLVED


def test_provider_length_conflict_blocks_target_binding_without_proving_absence() -> None:
    context = _context((SnapshotSequence("chr1", 10, 0, _REFGET_A),))
    snapshot = _snapshot(sequences=(_ucsc_sequence("chr1", 11, refget_id=_REFGET_A),))

    resolution = resolve_ucsc_target(snapshot, context, "chr1")

    assert resolution.state is UcscTargetResolutionState.UNRESOLVED
    assert resolution.reason is UcscTargetResolutionReason.PROVIDER_LENGTH_CONFLICT
    assert resolution.binding is None
