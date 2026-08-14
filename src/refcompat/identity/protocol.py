"""Stable sequence-identity port owned by RefCompat."""

from __future__ import annotations

from typing import Protocol

from refcompat.model.identity import SequenceCollectionSnapshot
from refcompat.model.resources import Resource


class ReferenceIdentityProvider(Protocol):
    """Provide deterministic local biological identity for reference resources."""

    def inspect_fasta(self, resource: Resource) -> SequenceCollectionSnapshot:
        """Inspect a FASTA resource and return RefCompat-owned identity values."""
        ...
