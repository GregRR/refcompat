"""Unit tests for the pysam-backed VCF observation boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from refcompat.inspectors.vcf import (
    UnsupportedVcfResourceError,
    VcfParseError,
    VcfProviderIncompatibleError,
    VcfUnreadableError,
    inspect_vcf_context,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind


def _resource(path: Path, kind: ResourceKind = ResourceKind.VCF) -> Resource:
    return Resource(ResourceId(path.name), kind, ArtifactIdentity(path))


def _header_record(**values: str) -> SimpleNamespace:
    return SimpleNamespace(get=lambda key, default=None: values.get(key, default))


def _fake_module(*, records: tuple[object, ...] = ()) -> SimpleNamespace:
    contigs = {
        "chr1": SimpleNamespace(
            name="chr1",
            length=100,
            header_record=_header_record(
                length="100",
                md5="a" * 32,
                assembly="GRCh38",
                URL="https://example.test/chr1",
            ),
        ),
        "chr2": SimpleNamespace(
            name="chr2",
            length=200,
            header_record=_header_record(length="200"),
        ),
    }
    header = SimpleNamespace(
        version="VCFv4.5",
        records=(SimpleNamespace(key="reference", value="file:///refs/grch38.fa"),),
        contigs=contigs,
    )

    class FakeVariantFile:
        is_bcf = False

        def __init__(self, _: str) -> None:
            self.header = header

        def __iter__(self) -> object:
            return iter(records)

        def close(self) -> None:
            pass

    return SimpleNamespace(__version__="0.24.0", VariantFile=FakeVariantFile)


def test_inspect_vcf_context_copies_header_and_chrom_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    fake_module = _fake_module(
        records=(
            SimpleNamespace(contig="chr1"),
            SimpleNamespace(contig="chr1"),
            SimpleNamespace(contig="chrUn"),
        )
    )
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    snapshot = inspect_vcf_context(_resource(path))

    assert snapshot.header.file_format == "VCFv4.5"
    assert snapshot.header.reference_claims == ("file:///refs/grch38.fa",)
    assert snapshot.header.contigs[0].name == "chr1"
    assert snapshot.header.contigs[0].length == 100
    assert snapshot.header.contigs[0].md5 == "a" * 32
    assert snapshot.header.contigs[0].assembly == "GRCh38"
    assert snapshot.header.contigs[0].url == "https://example.test/chr1"
    assert snapshot.record_count == 3
    assert [(item.sequence_name, item.record_count) for item in snapshot.chrom_usage] == [
        ("chr1", 2),
        ("chrUn", 1),
    ]


def test_inspect_vcf_context_rejects_wrong_resource_kind(tmp_path: Path) -> None:
    path = tmp_path / "reference.fa"
    path.write_text(">chr1\nA\n", encoding="utf-8")

    with pytest.raises(UnsupportedVcfResourceError):
        inspect_vcf_context(_resource(path, ResourceKind.FASTA))


def test_inspect_vcf_context_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VcfUnreadableError):
        inspect_vcf_context(_resource(tmp_path / "missing.vcf"))


def test_inspect_vcf_context_rejects_bcf_for_milestone3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "variants.bcf"
    path.write_bytes(b"synthetic")

    class FakeVariantFile:
        is_bcf = True
        header = SimpleNamespace(version="VCFv4.5", records=(), contigs={})

        def __init__(self, _: str) -> None:
            pass

        def __iter__(self) -> object:
            return iter(())

        def close(self) -> None:
            pass

    fake_module = SimpleNamespace(__version__="0.24.0", VariantFile=FakeVariantFile)
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfParseError, match="BCF input is deferred"):
        inspect_vcf_context(_resource(path))


def test_inspect_vcf_context_rejects_invalid_provider_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    fake_module = _fake_module(records=(SimpleNamespace(contig=1),))
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfProviderIncompatibleError, match="CHROM"):
        inspect_vcf_context(_resource(path))
