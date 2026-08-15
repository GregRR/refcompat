"""End-to-end CLI diagnostics over the Milestone 1 identity and integrity slices."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refcompat.cli import main

_FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_cli_inspect_fasta_json_uses_refget_identity(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fasta = _FIXTURES / "fasta" / "ga4gh_base.fa"

    assert main(["inspect-fasta", str(fasta), "--format", "json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["type"] == "sequence_collection_snapshot"
    assert payload["completeness"] == "complete"
    assert len(payload["sequences"]) == 3
    assert payload["provider"]["name"] == "refget"
    assert "verdict" not in payload


def test_cli_check_fai_human_reports_exact_structural_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fasta = _FIXTURES / "fai" / "htslib_example.fa"
    fai = _FIXTURES / "fai" / "htslib_example.fa.fai"

    assert main(["check-fai", str(fasta), str(fai)]) == 0
    captured = capsys.readouterr()

    assert "FASTA index integrity" in captured.out
    assert "exact structural match: yes" in captured.out
    assert "differences:\n- none" in captured.out


def test_cli_check_dict_json_reports_exact_companion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fasta = _FIXTURES / "fasta" / "ga4gh_base.fa"
    dictionary = _FIXTURES / "dict" / "ga4gh_base.dict"

    assert main(["check-dict", str(fasta), str(dictionary), "--format", "json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["type"] == "sequence_dictionary_integrity"
    assert payload["structurally_verified"] is True
    assert payload["content_verified"] is True
    assert payload["exact_companion_verified"] is True
    assert payload["differences"] == []


def test_cli_check_fai_json_reports_conflict_without_process_failure(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    fasta = _FIXTURES / "fai" / "htslib_example.fa"
    source_fai = _FIXTURES / "fai" / "htslib_example.fa.fai"
    conflicting_fai = tmp_path / "conflicting.fa.fai"
    conflicting_fai.write_text(
        source_fai.read_text(encoding="utf-8").replace("one\t66\t", "one\t65\t", 1),
        encoding="utf-8",
    )

    assert main(["check-fai", str(fasta), str(conflicting_fai), "--format", "json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["type"] == "fasta_index_integrity"
    assert payload["verified"] is False
    assert any(item["kind"] == "length" for item in payload["differences"])
    assert captured.err == ""


def test_cli_check_dict_json_reports_conflict_without_process_failure(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    fasta = _FIXTURES / "fasta" / "ga4gh_base.fa"
    source_dictionary = _FIXTURES / "dict" / "ga4gh_base.dict"
    conflicting_dictionary = tmp_path / "conflicting.dict"
    conflicting_dictionary.write_text(
        source_dictionary.read_text(encoding="utf-8").replace("SN:chr1\tLN:4", "SN:chr1\tLN:5", 1),
        encoding="utf-8",
    )

    assert main(["check-dict", str(fasta), str(conflicting_dictionary), "--format", "json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["type"] == "sequence_dictionary_integrity"
    assert payload["has_conflict"] is True
    assert payload["exact_companion_verified"] is False
    assert any(item["kind"] == "length" for item in payload["differences"])
    assert captured.err == ""


@pytest.mark.parametrize(
    ("command", "fasta"),
    [
        ("check-fai", _FIXTURES / "fai" / "htslib_example.fa"),
        ("check-dict", _FIXTURES / "fasta" / "ga4gh_base.fa"),
    ],
)
def test_cli_companion_checks_normalize_missing_artifact_errors_to_stderr(
    command: str,
    fasta: Path,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    missing_artifact = tmp_path / "missing-companion"

    assert main([command, str(fasta), str(missing_artifact)]) == 2
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err.startswith("refcompat: error: ")
