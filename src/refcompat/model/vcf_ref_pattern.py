"""VCF-specific interpretation of proven REF conflict distribution."""

from __future__ import annotations

from dataclasses import dataclass

from refcompat._compat import StrEnum, assert_never
from refcompat.model.resources import ResourceId


class VcfRefConflictPattern(StrEnum):
    """Observed distribution of proven VCF REF conflicts."""

    NONE = "none"
    ISOLATED = "isolated"
    LOCALIZED = "localized"
    DISTRIBUTED = "distributed"
    SYSTEMATIC = "systematic"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True, slots=True)
class VcfRefConflictPatternSummary:
    """Threshold-free interpretation of exhaustive VCF REF outcomes.

    ``UNCLASSIFIED`` means unresolved-sequence or out-of-bounds records prevent
    a complete statement about the distribution. It does not erase any proven
    REF mismatch and does not change whole-bundle compatibility truth.
    """

    vcf_resource_id: ResourceId
    fasta_resource_id: ResourceId
    pattern: VcfRefConflictPattern
    record_count: int
    directly_compared_count: int
    mismatch_count: int
    unresolved_count: int
    compared_sequence_names: tuple[str, ...] = ()
    affected_sequence_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.vcf_resource_id or not self.fasta_resource_id:
            raise ValueError("VCF REF conflict pattern resource IDs must not be empty")
        counts = (
            self.record_count,
            self.directly_compared_count,
            self.mismatch_count,
            self.unresolved_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("VCF REF conflict pattern counts must not be negative")
        if self.directly_compared_count + self.unresolved_count != self.record_count:
            raise ValueError("VCF REF conflict pattern counts must cover every record")
        if self.mismatch_count > self.directly_compared_count:
            raise ValueError("VCF REF conflict mismatches cannot exceed compared records")

        compared = self.compared_sequence_names
        affected = self.affected_sequence_names
        if any(not name for name in (*compared, *affected)):
            raise ValueError("VCF REF conflict pattern sequence names must not be empty")
        if compared != tuple(sorted(set(compared))):
            raise ValueError("VCF REF compared sequence names must be unique and sorted")
        if affected != tuple(sorted(set(affected))):
            raise ValueError("VCF REF affected sequence names must be unique and sorted")
        if not set(affected).issubset(compared):
            raise ValueError("VCF REF affected sequences must be directly comparable")
        if (self.directly_compared_count == 0) != (not compared):
            raise ValueError("VCF REF compared sequences must agree with compared record count")
        if (self.mismatch_count == 0) != (not affected):
            raise ValueError("VCF REF affected sequences must agree with mismatch count")

        if self.pattern is VcfRefConflictPattern.UNCLASSIFIED:
            if self.unresolved_count == 0:
                raise ValueError("unclassified VCF REF pattern requires incomplete comparison")
            return
        if self.unresolved_count != 0:
            raise ValueError("classified VCF REF pattern requires complete direct comparison")

        if self.pattern is VcfRefConflictPattern.NONE:
            if self.mismatch_count != 0:
                raise ValueError("NONE VCF REF pattern cannot contain mismatches")
            return
        if self.pattern is VcfRefConflictPattern.ISOLATED:
            if self.mismatch_count != 1 or len(affected) != 1:
                raise ValueError("ISOLATED VCF REF pattern requires exactly one mismatch")
            return
        if self.pattern is VcfRefConflictPattern.LOCALIZED:
            if self.mismatch_count <= 1:
                raise ValueError("LOCALIZED VCF REF pattern requires multiple mismatches")
            if not affected:
                raise ValueError("LOCALIZED VCF REF pattern requires affected sequences")
            if len(affected) >= 2 and set(affected) == set(compared):
                raise ValueError(
                    "multi-sequence scope-wide VCF REF conflicts must be DISTRIBUTED or SYSTEMATIC"
                )
            return
        if self.pattern is VcfRefConflictPattern.DISTRIBUTED:
            if self.mismatch_count <= 1:
                raise ValueError("DISTRIBUTED VCF REF pattern requires multiple mismatches")
            if len(compared) < 2 or set(affected) != set(compared):
                raise ValueError(
                    "DISTRIBUTED VCF REF pattern requires every sequence in a multi-sequence scope"
                )
            if self.mismatch_count >= self.directly_compared_count:
                raise ValueError("all-record VCF REF conflict must be SYSTEMATIC")
            return
        if self.pattern is VcfRefConflictPattern.SYSTEMATIC:
            if self.mismatch_count <= 1:
                raise ValueError("SYSTEMATIC VCF REF pattern requires multiple mismatches")
            if len(compared) < 2 or set(affected) != set(compared):
                raise ValueError(
                    "SYSTEMATIC VCF REF pattern requires every sequence in a multi-sequence scope"
                )
            if self.mismatch_count != self.directly_compared_count:
                raise ValueError(
                    "SYSTEMATIC VCF REF pattern requires every compared record to mismatch"
                )
            return
        assert_never(self.pattern)
