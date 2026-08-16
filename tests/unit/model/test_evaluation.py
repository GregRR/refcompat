"""Unit tests for explicit Milestone 2 evaluation requests and scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from refcompat.model.evaluation import (
    EvaluationPolicyId,
    EvaluationRequest,
    EvaluationScope,
    ProfileId,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(resource_id: str, kind: ResourceKind) -> Resource:
    return Resource(
        id=ResourceId(resource_id),
        kind=kind,
        artifact=ArtifactIdentity(path=Path(f"/{resource_id}")),
    )


def test_evaluation_request_accepts_explicit_anchor_scope_profiles_and_policy() -> None:
    fasta = _resource("reference", ResourceKind.FASTA)
    dictionary = _resource("dictionary", ResourceKind.SEQUENCE_DICTIONARY)
    scope = EvaluationScope(
        resource_ids=(fasta.id, dictionary.id),
        anchor_sequence_names=("chr1", "chr2"),
    )

    request = EvaluationRequest(
        resources=(fasta, dictionary),
        anchor_resource_id=fasta.id,
        scope=scope,
        active_profiles=(ProfileId("ucsc-preflight"),),
        policy_id=EvaluationPolicyId("authoritative"),
    )

    assert request.anchor_resource_id == ResourceId("reference")
    assert request.scope.anchor_sequence_names == ("chr1", "chr2")


def test_sequence_scope_none_means_not_narrowed() -> None:
    scope = EvaluationScope(resource_ids=(ResourceId("reference"),))

    assert scope.anchor_sequence_names is None


@pytest.mark.parametrize(
    "resource_ids,anchor_sequence_names",
    [
        ((), None),
        ((ResourceId(""),), None),
        ((ResourceId("reference"), ResourceId("reference")), None),
        ((ResourceId("reference"),), ()),
        ((ResourceId("reference"),), ("",)),
        ((ResourceId("reference"),), ("chr1", "chr1")),
    ],
)
def test_scope_rejects_invalid_or_ambiguous_boundaries(
    resource_ids: tuple[ResourceId, ...],
    anchor_sequence_names: tuple[str, ...] | None,
) -> None:
    with pytest.raises(ValueError):
        EvaluationScope(resource_ids=resource_ids, anchor_sequence_names=anchor_sequence_names)


def test_request_rejects_anchor_not_supplied() -> None:
    fasta = _resource("reference", ResourceKind.FASTA)

    with pytest.raises(ValueError, match="anchor must identify a supplied resource"):
        EvaluationRequest(
            resources=(fasta,),
            anchor_resource_id=ResourceId("other"),
            scope=EvaluationScope(resource_ids=(fasta.id,)),
        )


def test_request_rejects_non_fasta_anchor() -> None:
    dictionary = _resource("dictionary", ResourceKind.SEQUENCE_DICTIONARY)

    with pytest.raises(ValueError, match="anchor must be a FASTA"):
        EvaluationRequest(
            resources=(dictionary,),
            anchor_resource_id=dictionary.id,
            scope=EvaluationScope(resource_ids=(dictionary.id,)),
        )


def test_request_rejects_scope_outside_supplied_resources() -> None:
    fasta = _resource("reference", ResourceKind.FASTA)

    with pytest.raises(ValueError, match="only supplied resources"):
        EvaluationRequest(
            resources=(fasta,),
            anchor_resource_id=fasta.id,
            scope=EvaluationScope(resource_ids=(fasta.id, ResourceId("missing"))),
        )


def test_request_requires_anchor_in_scope() -> None:
    fasta = _resource("reference", ResourceKind.FASTA)
    dictionary = _resource("dictionary", ResourceKind.SEQUENCE_DICTIONARY)

    with pytest.raises(ValueError, match="scope must include the FASTA anchor"):
        EvaluationRequest(
            resources=(fasta, dictionary),
            anchor_resource_id=fasta.id,
            scope=EvaluationScope(resource_ids=(dictionary.id,)),
        )


def test_request_rejects_duplicate_resource_and_profile_ids() -> None:
    fasta = _resource("reference", ResourceKind.FASTA)

    with pytest.raises(ValueError, match="resource IDs must be unique"):
        EvaluationRequest(
            resources=(fasta, fasta),
            anchor_resource_id=fasta.id,
            scope=EvaluationScope(resource_ids=(fasta.id,)),
        )

    with pytest.raises(ValueError, match="profile IDs must be unique"):
        EvaluationRequest(
            resources=(fasta,),
            anchor_resource_id=fasta.id,
            scope=EvaluationScope(resource_ids=(fasta.id,)),
            active_profiles=(ProfileId("same"), ProfileId("same")),
        )
