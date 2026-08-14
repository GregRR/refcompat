"""Format-specific observation extraction."""

from refcompat.inspectors.fasta_index import (
    FastaIndexComputationError,
    FastaIndexError,
    FastaIndexParseError,
    FastaIndexProviderIncompatibleError,
    FastaIndexUnreadableError,
    UnsupportedFastaIndexRepresentationError,
    UnsupportedFastaIndexResourceError,
    compute_expected_fasta_index,
    read_fasta_index,
)

__all__ = [
    "FastaIndexComputationError",
    "FastaIndexError",
    "FastaIndexParseError",
    "FastaIndexProviderIncompatibleError",
    "FastaIndexUnreadableError",
    "UnsupportedFastaIndexRepresentationError",
    "UnsupportedFastaIndexResourceError",
    "compute_expected_fasta_index",
    "read_fasta_index",
]
