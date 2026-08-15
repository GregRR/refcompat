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
from refcompat.inspectors.sequence_dictionary import (
    SequenceDictionaryComputationError,
    SequenceDictionaryError,
    SequenceDictionaryParseError,
    SequenceDictionaryUnreadableError,
    UnsupportedSequenceDictionaryResourceError,
    expected_sequence_dictionary_from_snapshot,
    read_sequence_dictionary,
)

__all__ = [
    "FastaIndexComputationError",
    "FastaIndexError",
    "FastaIndexParseError",
    "FastaIndexProviderIncompatibleError",
    "FastaIndexUnreadableError",
    "SequenceDictionaryComputationError",
    "SequenceDictionaryError",
    "SequenceDictionaryParseError",
    "SequenceDictionaryUnreadableError",
    "UnsupportedFastaIndexRepresentationError",
    "UnsupportedFastaIndexResourceError",
    "UnsupportedSequenceDictionaryResourceError",
    "compute_expected_fasta_index",
    "expected_sequence_dictionary_from_snapshot",
    "read_fasta_index",
    "read_sequence_dictionary",
]
