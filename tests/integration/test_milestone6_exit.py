"""Milestone 6 exit coverage for the conservative UCSC preflight profile."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    CapabilityId,
    CollectionCompleteness,
    CompatibilityVerdict,
    EvaluationRequest,
    EvaluationScope,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceBindingMethod,
    SequenceCollectionSnapshot,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequencePresenceRequirement,
    SnapshotSequence,
)
from refcompat.profiles import (
    UCSC_PREFLIGHT_PROFILE_ID,
    UcscDatabaseId,
    UcscNameResolutionReason,
    UcscPreflightProjection,
    UcscPreflightTarget,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
    load_ucsc_provider_snapshot,
    parse_ucsc_provider_snapshot,
    project_ucsc_preflight,
)
from refcompat.reasoning import aggregate_bundle_verdict, build_reference_context, reason_bundle

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "milestone6"
_FASTA = ResourceId("reference")
_PEER = ResourceId("peer")
_DB = UcscDatabaseId("testDb")
_OTHER_DB = UcscDatabaseId("otherDb")
_CONTEXT = UcscProviderContextId("testDb@exit-v1")
_CATALOG_SOURCE = UcscProviderSourceId("catalog")
_ALIAS_SOURCE = UcscProviderSourceId("aliases")
_IDENTITY_SOURCE = UcscProviderSourceId("identity")
_ACQUIRED_AT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
_REFGET_A = RefgetSequenceId("SQ." + "A" * 32)
_REFGET_B = RefgetSequenceId("SQ." + "B" * 32)
_REFGET_C = RefgetSequenceId("SQ." + "C" * 32)


def _source(
    source_id: UcscProviderSourceId,
    dimension: UcscProviderDimension,
    *,
    database_id: UcscDatabaseId = _DB,
    context_id: UcscProviderContextId = _CONTEXT,
) -> UcscProviderSource:
    return UcscProviderSource(
        source_id,
        database_id,
        context_id,
        f"fixture://milestone6/{source_id}",
        _ACQUIRED_AT,
        (dimension,),
    )


def _provider_snapshot(
    *,
    sequences: tuple[tuple[str, RefgetSequenceId | None], ...] = (("chr1", _REFGET_A),),
    aliases: tuple[tuple[str, str], ...] = (("1", "chr1"),),
    catalog_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    alias_completeness: UcscProviderCompleteness = UcscProviderCompleteness.COMPLETE,
    identity_completeness: UcscProviderCompleteness | None = None,
    database_id: UcscDatabaseId = _DB,
    context_id: UcscProviderContextId = _CONTEXT,
) -> UcscProviderSnapshot:
    if identity_completeness is None:
        if all(identity is not None for _name, identity in sequences):
            identity_completeness = (
                UcscProviderCompleteness.COMPLETE
                if catalog_completeness is UcscProviderCompleteness.COMPLETE
                else UcscProviderCompleteness.PARTIAL
            )
        else:
            identity_completeness = UcscProviderCompleteness.UNKNOWN
    return UcscProviderSnapshot(
        database_id=database_id,
        context_id=context_id,
        sequences=tuple(
            UcscSequence(
                canonical_name=name,
                length=4,
                catalog_source_ids=(_CATALOG_SOURCE,),
                refget_id=identity,
                identity_source_ids=(_IDENTITY_SOURCE,) if identity is not None else (),
            )
            for name, identity in sequences
        ),
        aliases=tuple(
            UcscSequenceAlias(alias, target, (_ALIAS_SOURCE,), authority="fixture-authority")
            for alias, target in aliases
        ),
        catalog_completeness=catalog_completeness,
        alias_completeness=alias_completeness,
        identity_completeness=identity_completeness,
        sources=(
            _source(
                _CATALOG_SOURCE,
                UcscProviderDimension.SEQUENCE_CATALOG,
                database_id=database_id,
                context_id=context_id,
            ),
            _source(
                _ALIAS_SOURCE,
                UcscProviderDimension.ALIASES,
                database_id=database_id,
                context_id=context_id,
            ),
            _source(
                _IDENTITY_SOURCE,
                UcscProviderDimension.CONTENT_IDENTITY,
                database_id=database_id,
                context_id=context_id,
            ),
        ),
    )


def _request(
    *,
    kind: ResourceKind = ResourceKind.VCF,
    anchor_scope: tuple[str, ...] | None = None,
) -> EvaluationRequest:
    suffix = kind.value
    return EvaluationRequest(
        resources=(
            Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("reference.fa"))),
            Resource(_PEER, kind, ArtifactIdentity(path=Path(f"peer.{suffix}"))),
        ),
        anchor_resource_id=_FASTA,
        scope=EvaluationScope((_FASTA, _PEER), anchor_sequence_names=anchor_scope),
        active_profiles=(UCSC_PREFLIGHT_PROFILE_ID,),
    )


def _anchor(*sequences: SnapshotSequence) -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )


def _peer_contract(
    local_name: str,
    *,
    identity_capabilities: tuple[SequenceIdentityCapability, ...] = (),
    identity_requirement: RefgetSequenceId | None = None,
) -> ResourceContract:
    requirements: list[SequencePresenceRequirement | SequenceIdentityRequirement] = [
        SequencePresenceRequirement(
            RequirementId(f"presence:{local_name}"),
            _PEER,
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            local_name,
        )
    ]
    if identity_requirement is not None:
        requirements.append(
            SequenceIdentityRequirement(
                RequirementId(f"identity:{local_name}"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                local_name,
                identity_requirement,
            )
        )
    return ResourceContract(
        _PEER,
        requirements=tuple(requirements),
        capabilities=identity_capabilities,
    )


def _reason(
    provider_snapshot: UcscProviderSnapshot | None,
    anchor: SequenceCollectionSnapshot,
    peer_contract: ResourceContract,
    *,
    request: EvaluationRequest | None = None,
    target: UcscPreflightTarget | None = None,
) -> tuple[UcscPreflightProjection, CompatibilityVerdict]:
    if request is None:
        request = _request()
    if target is None:
        target = UcscPreflightTarget(_DB)
    context = build_reference_context(request, anchor)
    projection = project_ucsc_preflight(
        request,
        target,
        provider_snapshot,
        context,
        (ResourceContract(_FASTA), peer_contract),
    )
    bundle = reason_bundle(
        request,
        anchor,
        projection.contracts,
        supplemental_capabilities=projection.binding_capabilities,
        supplemental_sequence_bindings=projection.supplemental_sequence_bindings,
    )
    return projection, aggregate_bundle_verdict(bundle).verdict


def _identity_capability(local_name: str, identity: RefgetSequenceId) -> SequenceIdentityCapability:
    return SequenceIdentityCapability(
        CapabilityId(f"peer-identity:{local_name}:{identity.value}"),
        _PEER,
        local_name,
        identity,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )


def test_explicit_target_rejects_provider_snapshot_from_another_database() -> None:
    provider = _provider_snapshot(database_id=_OTHER_DB, context_id=UcscProviderContextId("other"))
    request = _request()
    anchor = _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A))
    context = build_reference_context(request, anchor)

    with pytest.raises(ValueError, match="selected UCSC database must match the provider snapshot"):
        project_ucsc_preflight(
            request,
            UcscPreflightTarget(_DB),
            provider,
            context,
            (ResourceContract(_FASTA), _peer_contract("chr1")),
        )


def test_cross_wired_alias_source_is_rejected_as_provider_input() -> None:
    with pytest.raises(ValueError, match="sources must belong to the selected database"):
        UcscProviderSnapshot(
            database_id=_DB,
            context_id=_CONTEXT,
            sequences=(
                UcscSequence("chr1", 4, (_CATALOG_SOURCE,), _REFGET_A, None, (_IDENTITY_SOURCE,)),
            ),
            aliases=(UcscSequenceAlias("1", "chr1", (_ALIAS_SOURCE,)),),
            catalog_completeness=UcscProviderCompleteness.COMPLETE,
            alias_completeness=UcscProviderCompleteness.COMPLETE,
            identity_completeness=UcscProviderCompleteness.COMPLETE,
            sources=(
                _source(_CATALOG_SOURCE, UcscProviderDimension.SEQUENCE_CATALOG),
                _source(
                    _ALIAS_SOURCE,
                    UcscProviderDimension.ALIASES,
                    database_id=_OTHER_DB,
                ),
                _source(_IDENTITY_SOURCE, UcscProviderDimension.CONTENT_IDENTITY),
            ),
        )


def test_exact_ucsc_name_requires_verified_target_content() -> None:
    projection, verdict = _reason(
        _provider_snapshot(aliases=()),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("chr1"),
    )

    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert projection.sequence_projections[0].sequence_binding is not None


def test_exact_name_and_length_do_not_override_different_content_target() -> None:
    provider = _provider_snapshot(sequences=(("chr1", _REFGET_B),), aliases=())
    projection, verdict = _reason(
        provider,
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("alternate", 4, 1, _REFGET_B),
        ),
        _peer_contract("chr1"),
    )

    binding = projection.sequence_projections[0].sequence_binding
    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert binding is not None
    assert binding.method is SequenceBindingMethod.AUTHORITATIVE_NAME
    assert binding.local_sequence_name == "chr1"
    assert binding.anchor_sequence_name == "alternate"


def test_exhaustive_target_content_absence_is_incompatible() -> None:
    projection, verdict = _reason(
        _provider_snapshot(sequences=(("chr1", _REFGET_C),), aliases=()),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("alternate", 4, 1, _REFGET_B),
        ),
        _peer_contract("chr1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.validation_capability is not None
    assert trace.sequence_binding is None
    assert verdict is CompatibilityVerdict.INCOMPATIBLE


def test_authoritative_cross_name_alias_with_content_bridge_is_compatible() -> None:
    projection, verdict = _reason(
        _provider_snapshot(),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.AUTHORITATIVE_ALIAS
    assert trace.sequence_binding is not None
    assert trace.sequence_binding.anchor_sequence_name == "chr1"
    assert verdict is CompatibilityVerdict.COMPATIBLE


def test_familiar_cross_name_without_provider_alias_is_indeterminate() -> None:
    projection, verdict = _reason(
        _provider_snapshot(aliases=()),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.UNDECLARED_NAME
    assert trace.sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_ambiguous_authoritative_alias_is_indeterminate() -> None:
    projection, verdict = _reason(
        _provider_snapshot(
            sequences=(("chr1", _REFGET_A), ("chrAlt", _REFGET_B)),
            aliases=(("1", "chr1"), ("1", "chrAlt")),
        ),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("chrAlt", 4, 1, _REFGET_B),
        ),
        _peer_contract("1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.AMBIGUOUS_ALIAS
    assert trace.sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_incomplete_alias_context_cannot_manufacture_binding() -> None:
    projection, verdict = _reason(
        _provider_snapshot(alias_completeness=UcscProviderCompleteness.PARTIAL),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.ALIAS_EVIDENCE_INCOMPLETE
    assert trace.sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_complete_alias_rows_with_partial_catalog_cannot_manufacture_binding() -> None:
    projection, verdict = _reason(
        _provider_snapshot(
            catalog_completeness=UcscProviderCompleteness.PARTIAL,
            alias_completeness=UcscProviderCompleteness.COMPLETE,
        ),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.ALIAS_EVIDENCE_INCOMPLETE
    assert trace.sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_distinct_ucsc_canonical_targets_cannot_collapse_to_one_anchor_axis() -> None:
    provider = _provider_snapshot(
        sequences=(("chr1", _REFGET_A), ("chr2", _REFGET_A)),
        aliases=(),
    )
    peer = ResourceContract(
        _PEER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId("presence:chr1"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                "chr1",
            ),
            SequencePresenceRequirement(
                RequirementId("presence:chr2"),
                _PEER,
                RequirementOrigin.CORE_FORMAT,
                RequirementLevel.MANDATORY,
                "chr2",
            ),
        ),
    )

    projection, verdict = _reason(
        provider,
        _anchor(SnapshotSequence("chrShared", 4, 0, _REFGET_A)),
        peer,
    )

    assert len(projection.sequence_projections) == 2
    assert all(trace.sequence_binding is None for trace in projection.sequence_projections)
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_missing_provider_target_identity_is_indeterminate_even_for_exact_name() -> None:
    projection, verdict = _reason(
        _provider_snapshot(
            sequences=(("chr1", None),),
            aliases=(),
            identity_completeness=UcscProviderCompleteness.UNKNOWN,
        ),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("chr1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.CANONICAL_NAME
    assert trace.target_resolution is not None
    assert trace.sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_duplicate_target_content_in_complete_anchor_remains_indeterminate() -> None:
    projection, verdict = _reason(
        _provider_snapshot(aliases=()),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("chrDup", 4, 1, _REFGET_A),
        ),
        _peer_contract("chr1"),
    )

    assert projection.sequence_projections[0].sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_scope_cannot_hide_duplicate_target_content_to_manufacture_uniqueness() -> None:
    request = _request(anchor_scope=("chr1",))
    projection, verdict = _reason(
        _provider_snapshot(aliases=()),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("chrDup", 4, 1, _REFGET_A),
        ),
        _peer_contract("chr1"),
        request=request,
    )

    assert projection.sequence_projections[0].sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_unique_target_hidden_outside_scope_remains_indeterminate() -> None:
    request = _request(anchor_scope=("chr1",))
    projection, verdict = _reason(
        _provider_snapshot(sequences=(("chrAlt", _REFGET_B),), aliases=(("1", "chrAlt"),)),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("chrAlt", 4, 1, _REFGET_B),
        ),
        _peer_contract("1"),
        request=request,
    )

    assert projection.sequence_projections[0].sequence_binding is None
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_explicit_scope_only_qualifies_an_otherwise_positive_profile_result() -> None:
    request = _request(anchor_scope=("chr1",))
    projection, verdict = _reason(
        _provider_snapshot(),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("chr2", 4, 1, _REFGET_B),
        ),
        _peer_contract("1"),
        request=request,
    )

    assert projection.sequence_projections[0].sequence_binding is not None
    assert verdict is CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS


def test_stronger_peer_content_binding_overrides_reassuring_provider_alias() -> None:
    peer_identity = _identity_capability("1", _REFGET_B)
    projection, verdict = _reason(
        _provider_snapshot(),
        _anchor(
            SnapshotSequence("chr1", 4, 0, _REFGET_A),
            SnapshotSequence("chrAlt", 4, 1, _REFGET_B),
        ),
        _peer_contract("1", identity_capabilities=(peer_identity,)),
    )

    trace = projection.sequence_projections[0]
    assert trace.sequence_binding is not None
    assert trace.sequence_binding.method is SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY
    assert trace.sequence_binding.anchor_sequence_name == "chrAlt"
    assert trace.validation_capability is not None
    assert verdict is CompatibilityVerdict.INCOMPATIBLE


def test_fixed_snapshot_has_same_exit_result_from_file_or_materialized_document() -> None:
    fixture = _FIXTURES / "ucsc-provider-snapshot.json"
    offline = load_ucsc_provider_snapshot(fixture)
    materialized = parse_ucsc_provider_snapshot(fixture.read_text(encoding="utf-8"))
    anchor = _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A))
    peer = _peer_contract("1")

    offline_projection, offline_verdict = _reason(offline, anchor, peer)
    materialized_projection, materialized_verdict = _reason(materialized, anchor, peer)

    assert offline == materialized
    assert offline_projection == materialized_projection
    assert offline_verdict is CompatibilityVerdict.COMPATIBLE
    assert materialized_verdict is offline_verdict


def test_complete_provider_unavailability_is_indeterminate() -> None:
    projection, verdict = _reason(
        None,
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("chr1"),
    )

    trace = projection.sequence_projections[0]
    assert trace.name_resolution.reason is UcscNameResolutionReason.PROVIDER_EVIDENCE_UNAVAILABLE
    assert projection.binding_capabilities == ()
    assert verdict is CompatibilityVerdict.INDETERMINATE


def test_hard_core_conflict_dominates_unrelated_unresolved_provider_evidence() -> None:
    projection, verdict = _reason(
        None,
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("chr1", identity_requirement=_REFGET_B),
    )

    assert projection.binding_capabilities == ()
    assert verdict is CompatibilityVerdict.INCOMPATIBLE


def test_reference_compatibility_does_not_claim_ucsc_hub_validity() -> None:
    hub_fixture = (_FIXTURES / "invalid-hub.txt").read_text(encoding="utf-8")
    observed_fields = {
        line.split(maxsplit=1)[0]
        for line in hub_fixture.splitlines()
        if line and not line.startswith("#")
    }
    assert "hub" not in observed_fields

    _projection, verdict = _reason(
        _provider_snapshot(),
        _anchor(SnapshotSequence("chr1", 4, 0, _REFGET_A)),
        _peer_contract("1"),
    )

    assert verdict is CompatibilityVerdict.COMPATIBLE
