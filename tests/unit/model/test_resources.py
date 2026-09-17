"""Tests for resource and byte-level artifact identity invariants."""

from pathlib import Path

import pytest

from refcompat.model import BedLayout
from refcompat.model.resources import (
    ArtifactDigest,
    ArtifactDigestAlgorithm,
    ArtifactIdentity,
    ResourceKind,
)


def test_bed_layouts_are_explicit_and_exclude_prohibited_partial_block_layouts() -> None:
    assert [(layout.value, layout.field_count) for layout in BedLayout] == [
        ("bed3", 3),
        ("bed4", 4),
        ("bed5", 5),
        ("bed6", 6),
        ("bed7", 7),
        ("bed8", 8),
        ("bed9", 9),
        ("bed12", 12),
    ]
    assert "bed10" not in {layout.value for layout in BedLayout}
    assert "bed11" not in {layout.value for layout in BedLayout}


def test_bed_is_a_distinct_resource_kind() -> None:
    assert ResourceKind.BED.value == "bed"


def test_artifact_digest_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        ArtifactDigest(ArtifactDigestAlgorithm.SHA256, "")


def test_artifact_identity_rejects_negative_byte_size() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ArtifactIdentity(Path("reference.fa"), byte_size=-1)
