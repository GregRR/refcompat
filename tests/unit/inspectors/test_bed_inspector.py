"""Unit tests for strict streaming standard BED inspection."""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import cast

import pytest

from refcompat.inspectors import (
    BedParseError,
    BedUnreadableError,
    UnsupportedBedLayoutError,
    UnsupportedBedResourceError,
    inspect_bed_context,
    iter_bed_features,
)
from refcompat.model import BedLayout
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(path: Path, kind: ResourceKind = ResourceKind.BED) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def test_inspect_bed_streams_native_sparse_usage(tmp_path: Path) -> None:
    path = tmp_path / "features.bed"
    path.write_text(
        "# standard BED3\nchr2\t20\t30\n\nchr1\t0\t0\nchr2\t5\t10\nchr1\t100\t100\n",
        encoding="ascii",
    )

    snapshot = inspect_bed_context(_resource(path), BedLayout.BED3)

    assert snapshot.layout is BedLayout.BED3
    assert snapshot.feature_count == 4
    assert snapshot.used_sequence_names == ("chr2", "chr1")
    assert [
        (
            item.chrom,
            item.feature_count,
            item.minimum_start,
            item.maximum_end,
            item.first_feature_line,
            item.zero_length_feature_count,
        )
        for item in snapshot.sequence_usage
    ] == [("chr2", 2, 5, 30, 2, 0), ("chr1", 2, 0, 100, 4, 2)]


def test_iter_bed_features_preserves_file_order_lines_and_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "features.bed"
    path.write_text("# comment\nchr1\t0\t1\n\t \nchr2\t8\t8\n", encoding="ascii")

    records = tuple(iter_bed_features(_resource(path), BedLayout.BED3))

    assert [
        (
            record.ordinal,
            record.line_number,
            record.chrom,
            record.chrom_start,
            record.chrom_end,
            record.is_zero_length,
        )
        for record in records
    ] == [(0, 2, "chr1", 0, 1, False), (1, 4, "chr2", 8, 8, True)]


@pytest.mark.parametrize(
    ("layout", "row"),
    [
        (BedLayout.BED3, "chr1\t0\t10"),
        (BedLayout.BED4, "chr1\t0\t10\tfeature name"),
        (BedLayout.BED5, "chr1\t0\t10\tfeature\t500"),
        (BedLayout.BED6, "chr1\t0\t10\tfeature\t500\t."),
        (BedLayout.BED7, "chr1\t0\t10\tfeature\t500\t+\t2"),
        (BedLayout.BED8, "chr1\t0\t10\tfeature\t500\t+\t2\t8"),
        (BedLayout.BED9, "chr1\t0\t10\tfeature\t500\t+\t2\t8\t1,2,3"),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tfeature\t500\t+\t2\t8\t1,2,3\t2\t4,3,\t0,7,",
        ),
    ],
)
def test_inspect_bed_accepts_each_supported_exact_layout(
    tmp_path: Path, layout: BedLayout, row: str
) -> None:
    path = tmp_path / f"{layout.value}.bed"
    path.write_text(f"{row}\n", encoding="ascii")

    record = next(iter_bed_features(_resource(path), layout))

    assert record.chrom_start == 0
    assert record.chrom_end == 10
    if layout.field_count >= 7:
        assert record.thick_start == 2
    if layout.field_count >= 8:
        assert record.thick_end == 8
    if layout is BedLayout.BED12:
        assert record.block_sizes == (4, 3)
        assert record.block_starts == (0, 7)


def test_inspect_bed_accepts_space_separators_when_fields_have_no_spaces(tmp_path: Path) -> None:
    path = tmp_path / "spaces.bed"
    path.write_text("chr1  0 10\n", encoding="ascii")

    snapshot = inspect_bed_context(_resource(path), BedLayout.BED3)

    assert snapshot.feature_count == 1


def test_inspect_bed_reads_gzip_by_content_magic(tmp_path: Path) -> None:
    path = tmp_path / "features.data"
    with gzip.open(path, "wt", encoding="ascii") as stream:
        stream.write("chr1\t0\t10\n")

    snapshot = inspect_bed_context(_resource(path), BedLayout.BED3)

    assert snapshot.feature_count == 1


def test_inspect_bed_does_not_trust_gzip_filename_suffix(tmp_path: Path) -> None:
    path = tmp_path / "plain.bed.gz"
    path.write_text("chr1\t0\t10\n", encoding="ascii")

    snapshot = inspect_bed_context(_resource(path), BedLayout.BED3)

    assert snapshot.feature_count == 1


def test_inspect_bed_accepts_empty_and_comment_only_input(tmp_path: Path) -> None:
    path = tmp_path / "empty.bed"
    path.write_text("# no features\n\t \n", encoding="ascii")

    snapshot = inspect_bed_context(_resource(path), BedLayout.BED12)

    assert snapshot.feature_count == 0
    assert snapshot.sequence_usage == ()


@pytest.mark.parametrize("prefix", ["track name=peaks", "browser position chr1:1-10"])
def test_inspect_bed_rejects_track_and_browser_lines(tmp_path: Path, prefix: str) -> None:
    path = tmp_path / "track.bed"
    path.write_text(f"{prefix}\nchr1\t0\t10\n", encoding="ascii")

    with pytest.raises(BedParseError, match="track/browser"):
        inspect_bed_context(_resource(path), BedLayout.BED3)


@pytest.mark.parametrize(
    ("layout", "row", "message"),
    [
        (BedLayout.BED3, "chr1\t0", "exactly 3 fields"),
        (BedLayout.BED3, "chr1\t0\t10\textra", "exactly 3 fields"),
        (BedLayout.BED3, " chr1\t0\t10", "leading or trailing"),
        (BedLayout.BED3, "chr1\t0\t10 ", "leading or trailing"),
        (BedLayout.BED3, "chr-1\t0\t10", "BED chrom"),
        (BedLayout.BED3, "chr1\t-1\t10", "chromStart is not an unsigned"),
        (BedLayout.BED3, f"chr1\t{1 << 64}\t{1 << 64}", "unsigned 64-bit"),
        (BedLayout.BED3, f"chr1\t{'9' * 5000}\t10", "unsigned 64-bit"),
        (BedLayout.BED3, "chr1\t11\t10", "chromStart exceeds"),
        (BedLayout.BED4, f"chr1\t0\t10\t{'x' * 256}", "1-255"),
        (BedLayout.BED5, "chr1\t0\t10\tfeature\t1001", "score exceeds"),
        (BedLayout.BED6, "chr1\t0\t10\tfeature\t0\t?", "strand"),
        (BedLayout.BED7, "chr1\t0\t10\tfeature\t0\t+\t11", "thickStart"),
        (BedLayout.BED8, "chr1\t0\t10\tfeature\t0\t+\t8\t7", "thickEnd"),
        (BedLayout.BED9, "chr1\t0\t10\tfeature\t0\t+\t0\t10\t1", "itemRgb"),
        (BedLayout.BED9, "chr1\t0\t10\tfeature\t0\t+\t0\t10\t0,0,256", "255"),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t0\t10\t0",
            "blockCount must be positive",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t2\tf\t0\t+\t0\t2\t0\t3\t1,1,0\t0,1,2",
            "blockCount exceeds",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t2\t4,3\t0",
            "list lengths",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t2\t4,3\t1,7",
            "first BED block",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t2\t8,3\t0,7",
            "overlapping",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t2\t4,4\t0,7",
            "outside",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t2\t4,2\t0,7",
            "last BED block",
        ),
        (
            BedLayout.BED12,
            "chr1\t0\t10\tf\t0\t+\t0\t10\t0\t2\t4, 3\t0,7",
            "blockSizes is invalid",
        ),
    ],
)
def test_inspect_bed_rejects_invalid_standard_structure(
    tmp_path: Path, layout: BedLayout, row: str, message: str
) -> None:
    path = tmp_path / "invalid.bed"
    path.write_text(f"{row}\n", encoding="ascii")

    with pytest.raises(BedParseError, match=message):
        inspect_bed_context(_resource(path), layout)


def test_inspect_bed_rejects_non_ascii_input(tmp_path: Path) -> None:
    path = tmp_path / "non-ascii.bed"
    path.write_bytes("chr1\t0\t10\tnaïve\n".encode())

    with pytest.raises(BedParseError, match="7-bit ASCII"):
        inspect_bed_context(_resource(path), BedLayout.BED4)


def test_inspect_bed_rejects_invalid_gzip(tmp_path: Path) -> None:
    path = tmp_path / "broken.data"
    path.write_bytes(b"\x1f\x8bnot-a-gzip-stream")

    with pytest.raises(BedParseError, match="gzip stream is invalid"):
        inspect_bed_context(_resource(path), BedLayout.BED3)


def test_inspect_bed_normalizes_unreadable_input(tmp_path: Path) -> None:
    path = tmp_path / "missing.bed"

    with pytest.raises(BedUnreadableError, match="cannot read BED"):
        inspect_bed_context(_resource(path), BedLayout.BED3)


def test_inspect_bed_rejects_non_bed_resource(tmp_path: Path) -> None:
    path = tmp_path / "features.bed"
    path.write_text("chr1\t0\t10\n", encoding="ascii")

    with pytest.raises(UnsupportedBedResourceError, match="requires a BED resource"):
        inspect_bed_context(_resource(path, ResourceKind.GTF), BedLayout.BED3)


def test_inspect_bed_rejects_non_enum_layout(tmp_path: Path) -> None:
    path = tmp_path / "features.bed"
    path.write_text("chr1\t0\t10\n", encoding="ascii")

    with pytest.raises(UnsupportedBedLayoutError, match="explicit supported BedLayout"):
        inspect_bed_context(_resource(path), cast(BedLayout, "bed10"))
