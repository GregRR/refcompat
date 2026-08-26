"""BAM/CRAM header observations owned by RefCompat.

Alignment headers reuse SAM ``@SQ`` sequence-dictionary semantics while keeping
header metadata and processing provenance observational. A declared ``M5`` is a
metadata claim until compared with independently derived anchor sequence
identity.

References:
- SAM v1 specification: https://samtools.github.io/hts-specs/SAMv1.pdf
- CRAM v3 specification: https://samtools.github.io/hts-specs/CRAMv3.pdf
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat.model.resources import ResourceId, ResourceKind
from refcompat.model.sequence_dictionary import SequenceDictionaryRecord


@dataclass(frozen=True, slots=True)
class AlignmentProgramRecord:
    """One normalized SAM ``@PG`` provenance record."""

    id: str
    name: str | None = None
    command_line: str | None = None
    previous_id: str | None = None
    description: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("alignment @PG ID must not be empty")
        for field_name, value in (
            ("PN", self.name),
            ("CL", self.command_line),
            ("PP", self.previous_id),
            ("DS", self.description),
            ("VN", self.version),
        ):
            if value is not None and not value:
                raise ValueError(f"alignment @PG {field_name} value must not be empty")


@dataclass(frozen=True, slots=True)
class AlignmentHeaderData:
    """Reference-relevant SAM header data exposed by a BAM or CRAM resource.

    ``sequences`` preserves ``@SQ`` file order. Empty sequence dictionaries are
    permitted at this observation boundary so an unmapped-only alignment file
    can still be inspected without inventing reference requirements.
    """

    sequences: tuple[SequenceDictionaryRecord, ...] = ()
    sam_version: str | None = None
    sort_order: str | None = None
    group_order: str | None = None
    subsort: str | None = None
    programs: tuple[AlignmentProgramRecord, ...] = ()

    def __post_init__(self) -> None:
        for field_name, value in (
            ("VN", self.sam_version),
            ("SO", self.sort_order),
            ("GO", self.group_order),
            ("SS", self.subsort),
        ):
            if value is not None and not value:
                raise ValueError(f"alignment @HD {field_name} value must not be empty")

        all_sequence_names: list[str] = []
        for record in self.sequences:
            all_sequence_names.append(record.name)
            all_sequence_names.extend(record.alternate_names)
        if len(set(all_sequence_names)) != len(all_sequence_names):
            raise ValueError("alignment @SQ SN and AN names must be globally distinct")

        program_ids = tuple(program.id for program in self.programs)
        if len(set(program_ids)) != len(program_ids):
            raise ValueError("alignment @PG IDs must be unique")


@dataclass(frozen=True, slots=True)
class AlignmentHeaderSnapshot:
    """Header-only reference-context observations from one BAM or CRAM resource.

    Header inspection does not scan alignment records. In particular, a
    declared ``@SQ`` sequence is not evidence that any read actually uses that
    sequence.
    """

    resource_id: ResourceId
    resource_kind: ResourceKind
    header: AlignmentHeaderData

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("alignment snapshot resource ID must not be empty")
        if self.resource_kind not in {ResourceKind.BAM, ResourceKind.CRAM}:
            raise ValueError("alignment snapshot resource kind must be BAM or CRAM")

    @property
    def declared_sequence_names(self) -> tuple[str, ...]:
        """Primary ``@SQ SN`` names in declared header order."""

        return tuple(record.name for record in self.header.sequences)
