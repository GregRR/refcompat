"""Tests for the stable RefCompat identity-provider port."""

from contextlib import suppress
from pathlib import Path

import pytest

from refcompat.identity import (
    Ga4ghRefgetIdentityProvider,
    ReferenceIdentityProvider,
    UnsupportedResourceKindError,
)
from refcompat.model.identity import SequenceCollectionSnapshot
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


class _ProviderStub:
    def inspect_fasta(self, resource: Resource) -> SequenceCollectionSnapshot:
        raise NotImplementedError


def test_provider_protocol_is_structurally_implementable() -> None:
    provider: ReferenceIdentityProvider = _ProviderStub()
    resource = Resource(
        id=ResourceId("reference"),
        kind=ResourceKind.FASTA,
        artifact=ArtifactIdentity(Path("reference.fa")),
    )
    with suppress(NotImplementedError):
        provider.inspect_fasta(resource)


def test_refget_adapter_rejects_non_fasta_resource_as_unsupported_usage() -> None:
    resource = Resource(
        id=ResourceId("not-fasta"),
        kind=ResourceKind.VCF,
        artifact=ArtifactIdentity(Path("variants.vcf")),
    )
    with pytest.raises(UnsupportedResourceKindError, match="cannot inspect resource kind"):
        Ga4ghRefgetIdentityProvider().inspect_fasta(resource)
