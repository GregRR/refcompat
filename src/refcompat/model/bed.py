"""BED-specific immutable model values."""

from __future__ import annotations

from refcompat._compat import StrEnum


class BedLayout(StrEnum):
    """Explicit standard BED layouts supported by the Milestone 9 contract.

    BED has no in-band schema marker, so callers must select one of these
    layouts rather than asking an inspector to infer standard field meaning
    from a row's column count. BED10 and BED11 are intentionally absent because
    BEDv1 permits block fields only as the complete BED12 group.
    """

    BED3 = "bed3"
    BED4 = "bed4"
    BED5 = "bed5"
    BED6 = "bed6"
    BED7 = "bed7"
    BED8 = "bed8"
    BED9 = "bed9"
    BED12 = "bed12"

    @property
    def field_count(self) -> int:
        """Return the exact number of standard fields in this layout."""

        return int(self.value.removeprefix("bed"))
