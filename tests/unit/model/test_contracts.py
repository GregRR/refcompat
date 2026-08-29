"""Unit tests for typed Milestone 2 requirements, capabilities, and contracts."""

from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, signature

import pytest

from refcompat.model.contracts import (
    CapabilityId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    ResourceContract,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.identity import Md5Digest, RefgetSequenceId
from refcompat.model.observations import ObservationId
from refcompat.model.resources import ResourceId

_RESOURCE = ResourceId("reference")
_MD5 = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_REFGET = RefgetSequenceId("SQ.01234567890123456789012345678901")


def test_typed_contract_keeps_requirement_and_capability_kinds_distinct() -> None:
    presence = SequencePresenceRequirement(
        id=RequirementId("req-presence"),
        resource_id=_RESOURCE,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
    )
    length = SequenceLengthCapability(
        id=CapabilityId("cap-length"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        length=4,
    )

    contract = ResourceContract(
        resource_id=_RESOURCE,
        requirements=(presence,),
        capabilities=(length,),
    )

    assert isinstance(contract.requirements[0], SequencePresenceRequirement)
    assert isinstance(contract.capabilities[0], SequenceLengthCapability)


def test_presence_capability_can_explicitly_prove_absence() -> None:
    capability = SequencePresenceCapability(
        id=CapabilityId("cap-absent"),
        resource_id=_RESOURCE,
        sequence_name="chrX",
        present=False,
    )

    assert capability.present is False


def test_sequence_identity_absence_capability_enforces_pair_identity() -> None:
    with pytest.raises(ValueError, match="subject must differ"):
        SequenceIdentityAbsenceCapability(
            id=CapabilityId("absence"),
            resource_id=_RESOURCE,
            subject_resource_id=_RESOURCE,
            sequence_name="chr1",
            identity_values=(_MD5,),
            source_identity_capability_ids=(CapabilityId("source"),),
        )

    with pytest.raises(ValueError, match="at least one identity value"):
        SequenceIdentityAbsenceCapability(
            id=CapabilityId("absence"),
            resource_id=_RESOURCE,
            subject_resource_id=ResourceId("consumer"),
            sequence_name="chr1",
            identity_values=(),
            source_identity_capability_ids=(CapabilityId("source"),),
        )


def test_resource_contract_rejects_reasoner_owned_identity_absence() -> None:
    absence = SequenceIdentityAbsenceCapability(
        id=CapabilityId("absence"),
        resource_id=_RESOURCE,
        subject_resource_id=ResourceId("consumer"),
        sequence_name="chr1",
        identity_values=(_MD5,),
        source_identity_capability_ids=(CapabilityId("source"),),
    )

    with pytest.raises(ValueError, match="reasoner-derived"):
        ResourceContract(_RESOURCE, capabilities=(absence,))


def test_identity_types_remain_algorithm_specific() -> None:
    md5_requirement = SequenceIdentityRequirement(
        id=RequirementId("req-md5"),
        resource_id=_RESOURCE,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        identity=_MD5,
    )
    refget_capability = SequenceIdentityCapability(
        id=CapabilityId("cap-refget"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        identity=_REFGET,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    assert isinstance(md5_requirement.identity, Md5Digest)
    assert isinstance(refget_capability.identity, RefgetSequenceId)


def test_identity_capability_requires_explicit_provenance() -> None:
    provenance = signature(SequenceIdentityCapability).parameters["provenance"]
    assert provenance.default is Parameter.empty


def test_identity_capability_tracks_claim_vs_content_provenance() -> None:
    derived = SequenceIdentityCapability(
        id=CapabilityId("derived"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        identity=_MD5,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    declared = SequenceIdentityCapability(
        id=CapabilityId("declared"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        identity=_MD5,
        provenance=SequenceIdentityProvenance.DECLARED_METADATA,
    )

    assert derived.provenance is SequenceIdentityProvenance.CONTENT_DERIVED
    assert declared.provenance is SequenceIdentityProvenance.DECLARED_METADATA


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SequencePresenceRequirement(
            RequirementId(""),
            _RESOURCE,
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            "chr1",
        ),
        lambda: SequenceLengthRequirement(
            RequirementId("length"),
            _RESOURCE,
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            "chr1",
            -1,
        ),
        lambda: SequenceOrderRequirement(
            RequirementId("order"),
            _RESOURCE,
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            ("chr1", "chr1"),
        ),
        lambda: SequenceLengthCapability(CapabilityId("length"), _RESOURCE, "chr1", -1),
        lambda: SequenceOrderCapability(CapabilityId("order"), _RESOURCE, ("chr1", "chr1")),
    ],
)
def test_contract_values_reject_invalid_invariants(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


def test_resource_contract_rejects_foreign_members_and_duplicate_ids() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req"),
        resource_id=ResourceId("other"),
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    with pytest.raises(ValueError, match="requirements must belong"):
        ResourceContract(resource_id=_RESOURCE, requirements=(requirement,))

    capability = SequenceLengthCapability(
        id=CapabilityId("same"), resource_id=_RESOURCE, sequence_name="chr1", length=4
    )
    duplicate = SequencePresenceCapability(
        id=CapabilityId("same"), resource_id=_RESOURCE, sequence_name="chr1", present=True
    )
    with pytest.raises(ValueError, match="capability IDs must be unique"):
        ResourceContract(resource_id=_RESOURCE, capabilities=(capability, duplicate))


def test_capability_preserves_source_observation_trace() -> None:
    capability = SequenceLengthCapability(
        id=CapabilityId("cap-length-traced"),
        resource_id=_RESOURCE,
        sequence_name="chr1",
        length=4,
        source_observation_ids=(ObservationId("obs-length"),),
    )

    assert capability.source_observation_ids == (ObservationId("obs-length"),)


def test_capability_rejects_duplicate_source_observation_ids() -> None:
    with pytest.raises(ValueError, match="observation IDs must be unique"):
        SequenceLengthCapability(
            id=CapabilityId("cap-length-traced"),
            resource_id=_RESOURCE,
            sequence_name="chr1",
            length=4,
            source_observation_ids=(ObservationId("same"), ObservationId("same")),
        )
