# VCF reference-context observation

**Status:** implemented as the first Milestone 3 VCF slice. Exhaustive direct REF-to-FASTA validation is implemented separately in [`vcf-ref-validation.md`](vcf-ref-validation.md), and format-neutral contract/evidence projection is implemented in [`vcf-contract-projection.md`](vcf-contract-projection.md). Verified-binding revalidation, mismatch-pattern findings, and whole-bundle verdict integration remain later work.

## Purpose

RefCompat uses `pysam`/HTSlib to extract the reference-relevant facts a VCF actually exposes without turning header metadata into compatibility proof.

The observation layer records:

- VCF file-format version;
- every generic `##reference` claim;
- ordered `##contig` declarations;
- declared contig length, `md5`, `assembly`, and `URL` fields when present;
- total variant-record count;
- actual `CHROM` usage and counts in first-observed order.

A header claim remains a claim. A declared contig is not automatically a verified sequence identity, and a CHROM value absent from a sparse VCF does not prove that the underlying reference lacks that sequence.

## Model

`VcfContextSnapshot` separates header declarations from record usage:

```text
VcfContextSnapshot
  resource_id
  header
    file_format
    reference_claims[]
    contigs[]
  record_count
  chrom_usage[]
```

Convenience projections expose declared names, used names, used-but-undeclared names, and declared-but-unused names. These remain observations; no projection is itself a compatibility verdict.

The `md5` value on a `##contig` line is intentionally stored as declared text rather than promoted directly to RefCompat's verified `Md5Digest` identity type. Later reasoning may assess that metadata against stronger content evidence.

## Parser boundary

`pysam>=0.24,<0.25` is loaded behind the inspector boundary. RefCompat copies primitive values into immutable RefCompat-owned models so `pysam`/HTSlib objects do not leak into the reasoning model.

The first slice accepts text VCF and bgzipped VCF. Ordinary gzip-compressed VCF is not seekable through the HTSlib VCF reader and is normalized to `VcfParseError`; callers should use BGZF/bgzip for `.vcf.gz`. BCF remains deferred to the v1.0 target even though `pysam.VariantFile` can read it.

### HTSlib normalization boundary

RefCompat observes the normalized VCF header representation exposed by `pysam`/HTSlib; this is not a raw-line-preserving parse. With the current `pysam`/HTSlib boundary, duplicate `##contig` IDs are collapsed before RefCompat sees them (the first exposed declaration wins), and malformed contig declarations such as a non-integer `length` may be dropped entirely. Integration tests pin those provider-visible semantics so a future dependency upgrade cannot silently change them.

Accordingly, a contig absent from `VcfHeaderData.contigs` means that the declaration was not exposed by the parser, not necessarily that no such raw header line existed. If later provenance requirements need byte-faithful duplicate/malformed-header reporting, that will require a different or additional raw-header observation path. RefCompat reads the raw provider-visible `length` header attribute where available so an explicit `length=0` remains distinguishable from an omitted length.

## Boundary with later VCF reasoning

This observation slice itself does not create VCF `ResourceContract` requirements, resolve aliases,
classify mismatch patterns, emit VCF-specific findings/verdict policy, or mutate VCF data.

Exact-name coordinate and exhaustive REF-to-FASTA comparison are implemented by the separate
[`vcf-ref-validation.md`](vcf-ref-validation.md) boundary. The subsequent
[`vcf-contract-projection.md`](vcf-contract-projection.md) bridge converts actual CHROM usage and
direct REF results into format-neutral requirements/evidence. Verified sequence binding,
mismatch-pattern interpretation, whole-bundle ingestion of pair-derived evidence, and reporting
remain later RCHECK-050 Milestone 3 slices.
