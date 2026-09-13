"""Unit tests for the pysam-backed VCF/BCF observation boundary."""

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


def _fake_module(*, records: tuple[object, ...] = (), is_bcf: bool = False) -> SimpleNamespace:
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

    provider_is_bcf = is_bcf

    class FakeVariantFile:
        is_bcf = provider_is_bcf

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


@pytest.mark.parametrize(
    ("declared_kind", "provider_is_bcf", "provider_name"),
    [
        (ResourceKind.VCF, True, "BCF"),
        (ResourceKind.BCF, False, "VCF"),
    ],
)
def test_inspect_vcf_context_rejects_declared_provider_format_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared_kind: ResourceKind,
    provider_is_bcf: bool,
    provider_name: str,
) -> None:
    path = tmp_path / "variants.bin"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(is_bcf=provider_is_bcf)
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(
        VcfParseError,
        match=rf"declared as {declared_kind.value.upper()}.*identified {provider_name}",
    ):
        inspect_vcf_context(_resource(path, declared_kind))


def test_inspect_bcf_context_copies_logical_header_and_chrom_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "variants.bcf"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(
        records=(
            SimpleNamespace(contig="chr1"),
            SimpleNamespace(contig="chr1"),
            SimpleNamespace(contig="chrUn"),
        ),
        is_bcf=True,
    )
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    snapshot = inspect_vcf_context(_resource(path, ResourceKind.BCF))

    assert snapshot.header.file_format == "VCFv4.5"
    assert snapshot.header.contigs[0].name == "chr1"
    assert snapshot.record_count == 3
    assert [(item.sequence_name, item.record_count) for item in snapshot.chrom_usage] == [
        ("chr1", 2),
        ("chrUn", 1),
    ]


def test_inspect_vcf_context_rejects_invalid_provider_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    fake_module = _fake_module(records=(SimpleNamespace(contig=1),))
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfProviderIncompatibleError, match="CHROM"):
        inspect_vcf_context(_resource(path))


def test_iter_bcf_ref_records_preserves_logical_one_based_pos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "variants.bcf"
    path.write_bytes(b"synthetic")
    fake_module = _fake_module(
        records=(SimpleNamespace(contig="chr1", pos=2, ref="C"),),
        is_bcf=True,
    )
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    records = tuple(iter_vcf_ref_records(_resource(path, ResourceKind.BCF)))

    assert [(item.ordinal, item.sequence_name, item.position, item.ref) for item in records] == [
        (0, "chr1", 2, "C")
    ]


def test_iter_vcf_ref_records_copies_fields_and_file_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    fake_module = _fake_module(
        records=(
            SimpleNamespace(contig="chr1", pos=10, ref="A"),
            SimpleNamespace(contig="chr2", pos=20, ref="CG"),
        )
    )
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    records = tuple(iter_vcf_ref_records(_resource(path)))

    assert [(item.ordinal, item.sequence_name, item.position, item.ref) for item in records] == [
        (0, "chr1", 10, "A"),
        (1, "chr2", 20, "CG"),
    ]


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (SimpleNamespace(contig=1, pos=1, ref="A"), "CHROM"),
        (SimpleNamespace(contig="chr1", pos="1", ref="A"), "POS"),
        (SimpleNamespace(contig="chr1", pos=1, ref=1), "REF"),
    ],
)
def test_iter_vcf_ref_records_rejects_invalid_provider_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record: SimpleNamespace,
    message: str,
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    fake_module = _fake_module(records=(record,))
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfProviderIncompatibleError, match=message):
        tuple(iter_vcf_ref_records(_resource(path)))


def test_iter_vcf_ref_records_rejects_invalid_ref_as_parse_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    fake_module = _fake_module(records=(SimpleNamespace(contig="chr1", pos=1, ref="R"),))
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfParseError, match="invalid VCF REF record"):
        tuple(iter_vcf_ref_records(_resource(path)))


def test_iter_vcf_ref_records_closes_provider_after_exhaustive_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "variants.vcf"
    path.write_text("placeholder\n", encoding="utf-8")
    closed = False

    class FakeVariantFile:
        is_bcf = False

        def __init__(self, _: str) -> None:
            pass

        def __iter__(self) -> object:
            return iter((SimpleNamespace(contig="chr1", pos=1, ref="A"),))

        def close(self) -> None:
            nonlocal closed
            closed = True

    fake_module = SimpleNamespace(__version__="0.24.0", VariantFile=FakeVariantFile)
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    assert len(tuple(iter_vcf_ref_records(_resource(path)))) == 1
    assert closed


def test_bcf_iteration_failure_is_normalized_and_provider_is_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "truncated.bcf"
    path.write_bytes(b"synthetic")
    header = _fake_module(is_bcf=True).VariantFile(str(path)).header
    close_count = 0

    class FakeVariantFile:
        is_bcf = True

        def __init__(self, _: str) -> None:
            self.header = header

        def __iter__(self) -> object:
            yield SimpleNamespace(contig="chr1", pos=2, ref="C")
            raise OSError("synthetic truncated BCF")

        def close(self) -> None:
            nonlocal close_count
            close_count += 1
            raise FileNotFoundError("synthetic provider close failure")

    fake_module = SimpleNamespace(__version__="0.24.0", VariantFile=FakeVariantFile)
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfParseError, match="cannot parse BCF records"):
        inspect_vcf_context(_resource(path, ResourceKind.BCF))
    assert close_count == 1

    records = iter_vcf_ref_records(_resource(path, ResourceKind.BCF))
    first = next(records)
    assert (first.ordinal, first.sequence_name, first.position, first.ref) == (0, "chr1", 2, "C")
    with pytest.raises(VcfParseError, match="cannot parse BCF records"):
        next(records)
    assert close_count == 2


def test_provider_close_failure_without_prior_error_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from refcompat.inspectors.vcf import iter_vcf_ref_records

    path = tmp_path / "variants.bcf"
    path.write_bytes(b"synthetic")
    header = _fake_module(is_bcf=True).VariantFile(str(path)).header

    class FakeVariantFile:
        is_bcf = True

        def __init__(self, _: str) -> None:
            self.header = header

        def __iter__(self) -> object:
            return iter((SimpleNamespace(contig="chr1", pos=2, ref="C"),))

        def close(self) -> None:
            raise OSError("synthetic close-only failure")

    fake_module = SimpleNamespace(__version__="0.24.0", VariantFile=FakeVariantFile)
    monkeypatch.setattr("refcompat.inspectors.vcf.import_module", lambda _: fake_module)

    with pytest.raises(VcfParseError, match="cannot close BCF resource"):
        inspect_vcf_context(_resource(path, ResourceKind.BCF))

    with pytest.raises(VcfParseError, match="cannot close BCF resource"):
        tuple(iter_vcf_ref_records(_resource(path, ResourceKind.BCF)))
