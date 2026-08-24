"""Tests for format-neutral exhaustive reference-base contract types."""

import pytest

from refcompat.model.contracts import (
    CapabilityId,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
)
from refcompat.model.resources import ResourceId


def test_reference_base_requirement_allows_empty_resource_record_set() -> None:
    requirement = ReferenceBaseRequirement(
        RequirementId("req"),
        ResourceId("variants"),
        ResourceId("fasta"),
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        0,
    )
    assert requirement.anchor_resource_id == ResourceId("fasta")
    assert requirement.record_count == 0


def test_reference_base_requirement_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="record count must not be negative"):
        ReferenceBaseRequirement(
            RequirementId("req"),
            ResourceId("variants"),
            ResourceId("fasta"),
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            -1,
        )


def test_reference_base_requirement_requires_anchor_resource() -> None:
    with pytest.raises(ValueError, match="anchor resource ID must not be empty"):
        ReferenceBaseRequirement(
            RequirementId("req"),
            ResourceId("variants"),
            ResourceId(""),
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            1,
        )


def test_reference_base_capability_requires_complete_partition() -> None:
    with pytest.raises(ValueError, match="cover every checked record"):
        ReferenceBaseValidationCapability(
            CapabilityId("cap"),
            ResourceId("fasta"),
            ResourceId("variants"),
            checked_count=3,
            match_count=1,
            mismatch_count=1,
            unresolved_count=0,
        )


def test_reference_base_capability_preserves_subject_and_anchor() -> None:
    capability = ReferenceBaseValidationCapability(
        CapabilityId("cap"),
        ResourceId("fasta"),
        ResourceId("variants"),
        checked_count=3,
        match_count=2,
        mismatch_count=1,
        unresolved_count=0,
    )
    assert capability.resource_id == ResourceId("fasta")
    assert capability.subject_resource_id == ResourceId("variants")
