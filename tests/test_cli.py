"""Command-line smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refcompat import __version__
from refcompat.cli import main
from refcompat.identity import Ga4ghRefgetIdentityProvider, ReferenceUnreadableError
from refcompat.model.identity import CollectionCompleteness, SequenceCollectionSnapshot
from refcompat.model.resources import Resource, ResourceId


def test_cli_without_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "reference-coordinate" in captured.out
    assert "context" in captured.out
    assert "inspect-fasta" in captured.out
    assert "check-fai" in captured.out
    assert "check-dict" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert f"refcompat {__version__}" in captured.out


def test_cli_inspect_fasta_emits_json_without_top_level_verdict(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nACGT\n", encoding="utf-8")

    def fake_inspect(
        self: Ga4ghRefgetIdentityProvider,
        resource: Resource,
    ) -> SequenceCollectionSnapshot:
        del self
        return SequenceCollectionSnapshot(
            resource_id=resource.id,
            completeness=CollectionCompleteness.COMPLETE,
        )

    monkeypatch.setattr(Ga4ghRefgetIdentityProvider, "inspect_fasta", fake_inspect)

    assert main(["inspect-fasta", str(path), "--format", "json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["type"] == "sequence_collection_snapshot"
    assert payload["resource_id"] == str(path)
    assert "verdict" not in payload
    assert captured.err == ""


def test_cli_normalizes_diagnostic_errors_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing.fa"

    def fail_inspect(
        self: Ga4ghRefgetIdentityProvider,
        resource: Resource,
    ) -> SequenceCollectionSnapshot:
        del self, resource
        raise ReferenceUnreadableError("cannot read reference")

    monkeypatch.setattr(Ga4ghRefgetIdentityProvider, "inspect_fasta", fail_inspect)

    assert main(["inspect-fasta", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "refcompat: error: cannot read reference\n"


def test_cli_uses_path_as_transparent_resource_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "reference.fa"
    seen_ids: list[ResourceId] = []

    def capture_resource(
        self: Ga4ghRefgetIdentityProvider,
        resource: Resource,
    ) -> SequenceCollectionSnapshot:
        del self
        seen_ids.append(resource.id)
        return SequenceCollectionSnapshot(
            resource_id=resource.id,
            completeness=CollectionCompleteness.COMPLETE,
        )

    monkeypatch.setattr(Ga4ghRefgetIdentityProvider, "inspect_fasta", capture_resource)

    assert main(["inspect-fasta", str(path)]) == 0
    capsys.readouterr()
    assert seen_ids == [ResourceId(str(path))]
