"""Read authoritative FASTA slices without trusting a supplied adjacent index.

Random access uses pysam/HTSlib, but the required FAI geometry is computed from
the supplied FASTA itself with RefCompat's existing FAI calculator and written
to a temporary index. A stale user-supplied ``.fai`` therefore cannot influence
base-level compatibility evidence.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Protocol, cast

from refcompat.inspectors.fasta_index import compute_expected_fasta_index
from refcompat.model.fasta_index import ComputedFastaIndex
from refcompat.model.resources import Resource, ResourceId, ResourceKind


class FastaSequenceAccessError(Exception):
    """Base class for normalized FASTA random-access failures."""


class UnsupportedFastaSequenceResourceError(FastaSequenceAccessError):
    """Random-access FASTA reading does not apply to the supplied resource kind."""


class FastaSequenceProviderIncompatibleError(FastaSequenceAccessError):
    """The installed pysam provider exposes an unsupported FASTA API/result shape."""


class FastaSequenceFetchError(FastaSequenceAccessError):
    """An expected in-bounds FASTA slice could not be read."""


class _FastaFile(Protocol):
    def fetch(self, reference: str, start: int, end: int) -> object: ...

    def close(self) -> object: ...


class _FastaFileFactory(Protocol):
    def __call__(self, filename: str, *, filepath_index: str) -> _FastaFile: ...


class _PysamFastaModule(Protocol):
    FastaFile: _FastaFileFactory


class PysamFastaSequenceReader:
    """Context-managed exact-name FASTA accessor backed by a computed temporary FAI."""

    def __init__(
        self,
        resource: Resource,
        computed_index: ComputedFastaIndex,
        handle: _FastaFile,
        temporary_directory: TemporaryDirectory[str],
    ) -> None:
        self._resource_id = resource.id
        self._lengths = {record.name: record.length for record in computed_index.records}
        self._handle = handle
        self._temporary_directory = temporary_directory
        self._closed = False

    @property
    def resource_id(self) -> ResourceId:
        """FASTA resource whose actual representation backs this accessor."""

        return self._resource_id

    def sequence_length(self, sequence_name: str) -> int | None:
        """Return the exact-name FASTA sequence length, or ``None`` if absent."""

        return self._lengths.get(sequence_name)

    def fetch(self, sequence_name: str, start: int, end: int) -> str:
        """Fetch a zero-based half-open FASTA slice already known to be in bounds."""

        if self._closed:
            raise FastaSequenceFetchError("FASTA sequence reader is closed")
        try:
            value = self._handle.fetch(sequence_name, start, end)
        except (IndexError, OSError, TypeError, ValueError) as exc:
            raise FastaSequenceFetchError(
                f"cannot fetch FASTA sequence {sequence_name}:{start}-{end}"
            ) from exc
        if not isinstance(value, str):
            raise FastaSequenceProviderIncompatibleError(
                "pysam returned a non-string FASTA sequence slice"
            )
        if len(value) != end - start:
            raise FastaSequenceProviderIncompatibleError(
                "pysam returned a FASTA sequence slice with unexpected length"
            )
        return value

    def close(self) -> None:
        """Close the HTSlib handle and remove the temporary FAI."""

        if self._closed:
            return
        self._closed = True
        try:
            self._handle.close()
        finally:
            self._temporary_directory.cleanup()

    def __enter__(self) -> PysamFastaSequenceReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def open_fasta_sequence_reader(resource: Resource) -> PysamFastaSequenceReader:
    """Open authoritative random access using FAI geometry computed from ``resource`` itself.

    The existing FAI calculator currently limits this path to uncompressed FASTA.
    Its normalized errors remain visible to callers because they describe the
    prerequisite computation itself rather than pysam random access.
    """

    if resource.kind is not ResourceKind.FASTA:
        raise UnsupportedFastaSequenceResourceError(
            f"FASTA sequence access requires a FASTA resource, got {resource.kind.value}"
        )

    computed = compute_expected_fasta_index(resource)
    if computed.fasta_resource_id != resource.id:
        raise FastaSequenceProviderIncompatibleError(
            "computed FASTA index belongs to a different resource"
        )
    pysam_module = _load_pysam_fasta()
    temporary_directory = TemporaryDirectory(prefix="refcompat-fasta-")
    index_path = Path(temporary_directory.name) / "reference.fai"
    try:
        index_path.write_text(_render_fai(computed), encoding="utf-8")
        handle = pysam_module.FastaFile(
            str(resource.artifact.path),
            filepath_index=str(index_path),
        )
    except (OSError, TypeError, ValueError) as exc:
        temporary_directory.cleanup()
        raise FastaSequenceFetchError(
            f"cannot open FASTA for indexed sequence access: {resource.artifact.path}"
        ) from exc

    return PysamFastaSequenceReader(resource, computed, handle, temporary_directory)


def _load_pysam_fasta() -> _PysamFastaModule:
    try:
        module = import_module("pysam")
    except ImportError as exc:  # pragma: no cover - required dependency in normal installs
        raise FastaSequenceProviderIncompatibleError("pysam is not importable") from exc
    return cast(_PysamFastaModule, module)


def _render_fai(computed: ComputedFastaIndex) -> str:
    return "".join(
        f"{record.name}\t{record.length}\t{record.offset}\t"
        f"{record.line_bases}\t{record.line_bytes}\n"
        for record in computed.records
    )
