"""Provisional human and JSON diagnostics for Milestone 1 checks.

These renderers expose facts already established by RefCompat's identity and
integrity models. They intentionally do not invent the whole-bundle verdict,
constraint, finding, or stable report-schema concepts reserved for later
reasoning milestones.
"""

from __future__ import annotations

import json
from typing import Protocol

from refcompat.model.fasta_index import FastaIndexDifference, FastaIndexIntegrityResult
from refcompat.model.identity import SequenceCollectionSnapshot, SnapshotSequence
from refcompat.model.sequence_dictionary import (
    SequenceDictionaryCrossNameM5LengthInconsistency,
    SequenceDictionaryDifference,
    SequenceDictionaryIntegrityResult,
)


class _StringValue(Protocol):
    @property
    def value(self) -> str:
        """Return the wrapped string value."""
        ...


def sequence_collection_snapshot_payload(snapshot: SequenceCollectionSnapshot) -> dict[str, object]:
    """Return a minimal machine-readable view of one sequence-identity snapshot."""

    provider: dict[str, object] | None = None
    if snapshot.provider is not None:
        provider = {
            "name": snapshot.provider.name,
            "version": snapshot.provider.version,
        }

    return {
        "type": "sequence_collection_snapshot",
        "resource_id": str(snapshot.resource_id),
        "completeness": snapshot.completeness.value,
        "collection_digest": _optional_value(snapshot.collection_digest),
        "attribute_digests": {
            "names": _optional_value(snapshot.names_digest),
            "lengths": _optional_value(snapshot.lengths_digest),
            "sequences": _optional_value(snapshot.sequences_digest),
        },
        "provider": provider,
        "sequences": [_snapshot_sequence_payload(sequence) for sequence in snapshot.sequences],
    }


def fasta_index_integrity_payload(result: FastaIndexIntegrityResult) -> dict[str, object]:
    """Return a minimal machine-readable view of one FASTA/FAI integrity result."""

    return {
        "type": "fasta_index_integrity",
        "fasta_resource_id": str(result.fasta_resource_id),
        "index_resource_id": str(result.index_resource_id),
        "verified": result.verified,
        "evidence_strength": result.evidence_strength.value,
        "evidence_polarity": result.evidence_polarity.value,
        "differences": [_fasta_index_difference_payload(item) for item in result.differences],
    }


def sequence_dictionary_integrity_payload(
    result: SequenceDictionaryIntegrityResult,
) -> dict[str, object]:
    """Return a minimal machine-readable view of one FASTA/dictionary result."""

    return {
        "type": "sequence_dictionary_integrity",
        "fasta_resource_id": str(result.fasta_resource_id),
        "dictionary_resource_id": str(result.dictionary_resource_id),
        "structurally_verified": result.structurally_verified,
        "content_verified": result.content_verified,
        "exact_companion_verified": result.exact_companion_verified,
        "has_conflict": result.has_conflict,
        "differences": [
            _sequence_dictionary_difference_payload(item) for item in result.differences
        ],
        "missing_m5_sequences": list(result.missing_m5_sequences),
        "renamed_identity_matches": [
            {
                "expected_name": item.expected_name,
                "observed_name": item.observed_name,
                "md5": item.md5.value,
                "evidence_strength": item.evidence_strength.value,
                "evidence_polarity": item.evidence_polarity.value,
            }
            for item in result.renamed_identity_matches
        ],
        "cross_name_m5_length_inconsistencies": [
            _m5_length_inconsistency_payload(item)
            for item in result.cross_name_m5_length_inconsistencies
        ],
    }


def render_json(payload: dict[str, object]) -> str:
    """Render one provisional diagnostic payload as deterministic pretty JSON."""

    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_sequence_collection_snapshot(snapshot: SequenceCollectionSnapshot) -> str:
    """Render human-readable standards-backed FASTA identity facts."""

    lines = [
        "FASTA sequence identity",
        f"resource: {snapshot.resource_id}",
        f"completeness: {snapshot.completeness.value}",
        f"sequence count: {len(snapshot.sequences)}",
        f"SeqCol digest: {_display_optional(snapshot.collection_digest)}",
        f"names digest: {_display_optional(snapshot.names_digest)}",
        f"lengths digest: {_display_optional(snapshot.lengths_digest)}",
        f"sequences digest: {_display_optional(snapshot.sequences_digest)}",
    ]
    if snapshot.provider is None:
        lines.append("identity provider: unavailable")
    else:
        lines.append(f"identity provider: {snapshot.provider.name} {snapshot.provider.version}")

    lines.append("sequences:")
    if not snapshot.sequences:
        lines.append("- none")
    else:
        lines.extend(_render_snapshot_sequence(sequence) for sequence in snapshot.sequences)
    return "\n".join(lines) + "\n"


def render_fasta_index_integrity(result: FastaIndexIntegrityResult) -> str:
    """Render one exact FASTA/FAI structural diagnostic."""

    lines = [
        "FASTA index integrity",
        f"FASTA resource: {result.fasta_resource_id}",
        f"index resource: {result.index_resource_id}",
        f"exact structural match: {_yes_no(result.verified)}",
        f"evidence: {result.evidence_strength.value} / {result.evidence_polarity.value}",
        "differences:",
    ]
    if not result.differences:
        lines.append("- none")
    else:
        lines.extend(_render_difference(item) for item in result.differences)
    return "\n".join(lines) + "\n"


def render_sequence_dictionary_integrity(result: SequenceDictionaryIntegrityResult) -> str:
    """Render structural, content, gap, and cross-name dictionary evidence."""

    lines = [
        "Sequence dictionary integrity",
        f"FASTA resource: {result.fasta_resource_id}",
        f"dictionary resource: {result.dictionary_resource_id}",
        f"exact structure verified: {_yes_no(result.structurally_verified)}",
        f"exact-name M5 content verified: {_yes_no(result.content_verified)}",
        f"exact companion verified: {_yes_no(result.exact_companion_verified)}",
        f"conflict observed: {_yes_no(result.has_conflict)}",
        "differences:",
    ]
    if not result.differences:
        lines.append("- none")
    else:
        lines.extend(_render_sequence_dictionary_difference(item) for item in result.differences)

    lines.append("M5 evidence gaps:")
    if not result.missing_m5_sequences:
        lines.append("- none")
    else:
        lines.extend(f"- {name}: M5 unavailable" for name in result.missing_m5_sequences)

    lines.append("cross-name M5 identity matches:")
    if not result.renamed_identity_matches:
        lines.append("- none")
    else:
        lines.extend(
            (
                f"- {item.expected_name} -> {item.observed_name}: M5 {item.md5.value} "
                f"({item.evidence_strength.value} / {item.evidence_polarity.value})"
            )
            for item in result.renamed_identity_matches
        )

    lines.append("cross-name M5/LN inconsistencies:")
    if not result.cross_name_m5_length_inconsistencies:
        lines.append("- none")
    else:
        lines.extend(
            (
                f"- {item.expected_name} -> {item.observed_name}: M5 {item.md5.value}; "
                f"expected LN={item.expected_length}; observed LN={item.observed_length}"
            )
            for item in result.cross_name_m5_length_inconsistencies
        )
    return "\n".join(lines) + "\n"


def _snapshot_sequence_payload(sequence: SnapshotSequence) -> dict[str, object]:
    return {
        "name": sequence.local_name,
        "length": sequence.length,
        "ordinal": sequence.ordinal,
        "refget_id": _optional_value(sequence.refget_id),
        "md5": _optional_value(sequence.md5),
    }


def _fasta_index_difference_payload(difference: FastaIndexDifference) -> dict[str, object]:
    return {
        "kind": difference.kind.value,
        "sequence_name": difference.sequence_name,
        "expected_ordinal": difference.expected_ordinal,
        "observed_ordinal": difference.observed_ordinal,
        "expected_value": difference.expected_value,
        "observed_value": difference.observed_value,
    }


def _sequence_dictionary_difference_payload(
    difference: SequenceDictionaryDifference,
) -> dict[str, object]:
    return {
        "kind": difference.kind.value,
        "sequence_name": difference.sequence_name,
        "expected_ordinal": difference.expected_ordinal,
        "observed_ordinal": difference.observed_ordinal,
        "expected_value": difference.expected_value,
        "observed_value": difference.observed_value,
        "evidence_strength": difference.evidence_strength.value,
        "evidence_polarity": difference.evidence_polarity.value,
    }


def _m5_length_inconsistency_payload(
    item: SequenceDictionaryCrossNameM5LengthInconsistency,
) -> dict[str, object]:
    return {
        "expected_name": item.expected_name,
        "observed_name": item.observed_name,
        "md5": item.md5.value,
        "expected_length": item.expected_length,
        "observed_length": item.observed_length,
    }


def _render_snapshot_sequence(sequence: SnapshotSequence) -> str:
    return (
        f"- {sequence.local_name}: length={_display_scalar(sequence.length)}; "
        f"ordinal={_display_scalar(sequence.ordinal)}; "
        f"refget={_display_optional(sequence.refget_id)}; md5={_display_optional(sequence.md5)}"
    )


def _render_sequence_dictionary_difference(difference: SequenceDictionaryDifference) -> str:
    return (
        f"{_render_difference(difference)} "
        f"({difference.evidence_strength.value} / {difference.evidence_polarity.value})"
    )


def _render_difference(difference: FastaIndexDifference | SequenceDictionaryDifference) -> str:
    details: list[str] = []
    if difference.sequence_name is not None:
        details.append(f"sequence={difference.sequence_name}")
    if difference.expected_ordinal is not None:
        details.append(f"expected_ordinal={difference.expected_ordinal}")
    if difference.observed_ordinal is not None:
        details.append(f"observed_ordinal={difference.observed_ordinal}")
    if difference.expected_value is not None:
        details.append(f"expected={difference.expected_value}")
    if difference.observed_value is not None:
        details.append(f"observed={difference.observed_value}")
    suffix = f": {'; '.join(details)}" if details else ""
    return f"- {difference.kind.value}{suffix}"


def _optional_value(value: _StringValue | None) -> str | None:
    if value is None:
        return None
    return value.value


def _display_optional(value: _StringValue | None) -> str:
    rendered = _optional_value(value)
    return rendered if rendered is not None else "unavailable"


def _display_scalar(value: int | None) -> str:
    return str(value) if value is not None else "unavailable"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
