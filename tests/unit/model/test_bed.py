"""Unit tests for immutable native-coordinate BED observations."""

from __future__ import annotations

from typing import cast

import pytest

from refcompat.model import (
    BedContextSnapshot,
    BedFeatureRecord,
    BedLayout,
    BedSequenceUsage,
)
from refcompat.model.resources import ResourceId, ResourceKind


def _record(**overrides: object) -> BedFeatureRecord:
    values: dict[str, object] = {
        "resource_id": ResourceId("bed"),
        "ordinal": 0,
        "line_number": 1,
        "chrom": "chr1",
        "chrom_start": 0,
        "chrom_end": 10,
    }
    values.update(overrides)
    return BedFeatureRecord(
        resource_id=values["resource_id"],  # type: ignore[arg-type]
        ordinal=values["ordinal"],  # type: ignore[arg-type]
        line_number=values["line_number"],  # type: ignore[arg-type]
        chrom=values["chrom"],  # type: ignore[arg-type]
        chrom_start=values["chrom_start"],  # type: ignore[arg-type]
        chrom_end=values["chrom_end"],  # type: ignore[arg-type]
        thick_start=values.get("thick_start"),  # type: ignore[arg-type]
        thick_end=values.get("thick_end"),  # type: ignore[arg-type]
        block_sizes=values.get("block_sizes", ()),  # type: ignore[arg-type]
        block_starts=values.get("block_starts", ()),  # type: ignore[arg-type]
    )


def test_bed_feature_preserves_zero_length_boundary() -> None:
    record = _record(chrom_start=10, chrom_end=10)

    assert record.is_zero_length
    assert (record.chrom_start, record.chrom_end) == (10, 10)


def test_bed12_feature_preserves_coordinate_structure() -> None:
    record = _record(
        thick_start=2,
        thick_end=8,
        block_sizes=(4, 3),
        block_starts=(0, 7),
    )

    assert record.block_count == 2
    assert record.block_sizes == (4, 3)
    assert record.block_starts == (0, 7)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ordinal": -1}, "ordinal"),
        ({"line_number": 0}, "line number"),
        ({"chrom": ""}, "chrom"),
        ({"chrom_start": -1}, "negative"),
        ({"chrom_end": 1 << 64}, "unsigned 64-bit"),
        ({"chrom_start": 11}, "start"),
        ({"thick_start": 11}, "thick start"),
        ({"thick_end": 8}, "requires thick start"),
        ({"thick_start": 8, "thick_end": 7}, "thick end"),
        ({"block_sizes": (10,)}, "supplied together"),
        ({"block_sizes": (5,), "block_starts": (0, 5)}, "equal lengths"),
        ({"block_sizes": (4, 3), "block_starts": (1, 7)}, "first BED block"),
        ({"block_sizes": (8, 3), "block_starts": (0, 7)}, "non-overlapping"),
        ({"block_sizes": (4, 2), "block_starts": (0, 7)}, "last BED block"),
    ],
)
def test_bed_feature_rejects_inconsistent_observations(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _record(**overrides)


def test_bed_snapshot_retains_first_observed_chrom_order() -> None:
    snapshot = BedContextSnapshot(
        resource_id=ResourceId("bed"),
        resource_kind=ResourceKind.BED,
        layout=BedLayout.BED3,
        feature_count=3,
        sequence_usage=(
            BedSequenceUsage("chr2", 2, 0, 20, 1, 1),
            BedSequenceUsage("chr1", 1, 5, 10, 2),
        ),
    )

    assert snapshot.used_sequence_names == ("chr2", "chr1")


def test_bed_snapshot_rejects_non_bed_resource_kind() -> None:
    with pytest.raises(ValueError, match="BED resource kind"):
        BedContextSnapshot(
            resource_id=ResourceId("bed"),
            resource_kind=ResourceKind.GTF,
            layout=BedLayout.BED3,
            feature_count=0,
        )


def test_bed_snapshot_rejects_non_enum_layout() -> None:
    with pytest.raises(ValueError, match="explicit supported layout"):
        BedContextSnapshot(
            resource_id=ResourceId("bed"),
            resource_kind=ResourceKind.BED,
            layout=cast(BedLayout, "bed10"),
            feature_count=0,
        )


def test_bed_snapshot_rejects_usage_count_mismatch() -> None:
    with pytest.raises(ValueError, match="sum to feature count"):
        BedContextSnapshot(
            resource_id=ResourceId("bed"),
            resource_kind=ResourceKind.BED,
            layout=BedLayout.BED3,
            feature_count=2,
            sequence_usage=(BedSequenceUsage("chr1", 1, 0, 1, 1),),
        )
