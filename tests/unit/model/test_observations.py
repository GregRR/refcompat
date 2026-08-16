"""Tests for directly observed resource facts and source-location invariants."""

import pytest

from refcompat.model.observations import (
    ObservationId,
    ObservationKind,
    ResourceObservation,
    SourceLocation,
)
from refcompat.model.resources import ResourceId


def test_source_location_preserves_traceable_components() -> None:
    location = SourceLocation(line_number=7, record_index=2, field="LN", locator="@SQ chr1")

    assert location.line_number == 7
    assert location.record_index == 2
    assert location.field == "LN"
    assert location.locator == "@SQ chr1"


@pytest.mark.parametrize(
    "location",
    [
        SourceLocation(line_number=1),
        SourceLocation(record_index=0),
        SourceLocation(field="M5"),
        SourceLocation(locator="FASTA record chr1"),
    ],
)
def test_source_location_accepts_independent_locator_forms(location: SourceLocation) -> None:
    assert any(
        value is not None
        for value in (
            location.line_number,
            location.record_index,
            location.field,
            location.locator,
        )
    )


def test_source_location_rejects_empty_location() -> None:
    with pytest.raises(ValueError, match="at least one"):
        SourceLocation()


def test_source_location_rejects_nonpositive_line() -> None:
    with pytest.raises(ValueError, match="line number"):
        SourceLocation(line_number=0)


def test_source_location_rejects_negative_record_index() -> None:
    with pytest.raises(ValueError, match="record index"):
        SourceLocation(record_index=-1)


def test_source_location_rejects_empty_field() -> None:
    with pytest.raises(ValueError, match="field"):
        SourceLocation(field="")


def test_source_location_rejects_empty_locator() -> None:
    with pytest.raises(ValueError, match="locator"):
        SourceLocation(locator="")


def test_resource_observation_preserves_fact_and_source_trace() -> None:
    location = SourceLocation(line_number=2, record_index=0, field="LN")
    observation = ResourceObservation(
        id=ObservationId("dict:2:LN"),
        resource_id=ResourceId("reference.dict"),
        kind=ObservationKind("sequence_dictionary.length"),
        value=248956422,
        source_location=location,
    )

    assert observation.value == 248956422
    assert observation.source_location == location


@pytest.mark.parametrize(
    ("observation_id", "resource_id", "kind", "match"),
    [
        ("", "reference", "sequence.length", "observation ID"),
        ("obs-1", "", "sequence.length", "resource ID"),
        ("obs-1", "reference", "", "kind"),
    ],
)
def test_resource_observation_requires_nonempty_identity_and_kind(
    observation_id: str,
    resource_id: str,
    kind: str,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        ResourceObservation(
            id=ObservationId(observation_id),
            resource_id=ResourceId(resource_id),
            kind=ObservationKind(kind),
            value="chr1",
        )
