"""End-to-end FASTA snapshot to SAM/Picard sequence-dictionary integrity tests."""

from __future__ import annotations

from pathlib import Path

from refcompat.identity import Ga4ghRefgetIdentityProvider
from refcompat.inspectors.sequence_dictionary import (
    expected_sequence_dictionary_from_snapshot,
    read_sequence_dictionary,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.reasoning.sequence_dictionary import evaluate_sequence_dictionary_integrity

_FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_ga4gh_known_answer_dictionary_matches_fasta_identity_snapshot() -> None:
    """Use the already-pinned GA4GH refget M5 values as independent content answers."""

    fasta = Resource(
        id=ResourceId("reference"),
        kind=ResourceKind.FASTA,
        artifact=ArtifactIdentity(_FIXTURES / "fasta" / "ga4gh_base.fa"),
    )
    dictionary = Resource(
        id=ResourceId("dictionary"),
        kind=ResourceKind.SEQUENCE_DICTIONARY,
        artifact=ArtifactIdentity(_FIXTURES / "dict" / "ga4gh_base.dict"),
    )

    snapshot = Ga4ghRefgetIdentityProvider().inspect_fasta(fasta)
    expected = expected_sequence_dictionary_from_snapshot(snapshot)
    observed = read_sequence_dictionary(dictionary)
    result = evaluate_sequence_dictionary_integrity(expected=expected, observed=observed)

    assert result.exact_companion_verified
    assert result.differences == ()
    assert result.missing_m5_sequences == ()
    assert observed.records[0].alternate_names == ("X",)
    assert observed.records[0].assembly == "synthetic"
