"""Tests for format-neutral exhaustive coordinate-bounds contract types."""

import pytest

from refcompat.model.contracts import (
    CapabilityId,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
)
from refcompat.model.resources import ResourceId


def test_coordinate_bounds_requirement_allows_empty_coordinate_set() -> None:
    requirement = CoordinateBoundsRequirement(
        RequirementId("req"),
        ResourceId("annotation"),
        ResourceId("fasta"),
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        0,
    )

    assert requirement.anchor_resource_id == ResourceId("fasta")
    assert requirement.coordinate_count == 0


def test_coordinate_bounds_requirement_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="count must not be negative"):
        CoordinateBoundsRequirement(
            RequirementId("req"),
            ResourceId("annotation"),
            ResourceId("fasta"),
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            -1,
        )


def test_coordinate_bounds_requirement_requires_anchor_resource() -> None:
    with pytest.raises(ValueError, match="anchor resource ID must not be empty"):
        CoordinateBoundsRequirement(
            RequirementId("req"),
            ResourceId("annotation"),
            ResourceId(""),
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            1,
        )


def test_coordinate_bounds_capability_requires_complete_partition() -> None:
    with pytest.raises(ValueError, match="cover every checked record"):
        CoordinateBoundsValidationCapability(
            CapabilityId("cap"),
            ResourceId("fasta"),
            ResourceId("annotation"),
            checked_count=3,
            representable_count=1,
            conflict_count=1,
            unresolved_count=0,
        )


def test_coordinate_bounds_capability_preserves_subject_and_anchor() -> None:
    capability = CoordinateBoundsValidationCapability(
        CapabilityId("cap"),
        ResourceId("fasta"),
        ResourceId("annotation"),
        checked_count=3,
        representable_count=2,
        conflict_count=1,
        unresolved_count=0,
    )

    assert capability.resource_id == ResourceId("fasta")
    assert capability.subject_resource_id == ResourceId("annotation")
