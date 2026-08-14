"""Tests for resource and byte-level artifact identity invariants."""

from pathlib import Path

import pytest

from refcompat.model.resources import ArtifactDigest, ArtifactDigestAlgorithm, ArtifactIdentity


def test_artifact_digest_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        ArtifactDigest(ArtifactDigestAlgorithm.SHA256, "")


def test_artifact_identity_rejects_negative_byte_size() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ArtifactIdentity(Path("reference.fa"), byte_size=-1)
