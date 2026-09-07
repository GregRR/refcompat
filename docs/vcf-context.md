# VCF/BCF reference-context observation

**Status:** VCF/VCF.gz observation was implemented in Milestone 3; Milestone 8 Slice 2 extends the same logical observation boundary to BCF2 with strict declared-format validation, and Slice 3 pins reuse of the existing RCHECK-050 scientific path. Scoped/profile/reporting BCF parity remains documented separately for later M8 work.

## Purpose

RefCompat uses `pysam`/HTSlib to extract the reference-relevant facts exposed by textual VCF or BCF2 without turning header metadata into compatibility proof.

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

The `md5` value on a `##contig` line is intentionally stored first as declared text. RCHECK-050F parses syntactically valid values on used contigs into sequence-identity requirements and, when the binding checks pass, into identity capabilities explicitly marked `DECLARED_METADATA`. They are never marked `CONTENT_DERIVED`. A declaration may support conservative cross-name binding when it uniquely identifies an eligible FASTA sequence, but it still does not prove REF compatibility by itself.

## Parser boundary

`pysam>=0.24,<0.25` is loaded behind the inspector boundary. RefCompat copies primitive values into immutable RefCompat-owned models so `pysam`/HTSlib objects do not leak into the reasoning model.

The shared inspector accepts text VCF, bgzipped VCF, and BCF2. Ordinary gzip-compressed VCF is not seekable through the HTSlib VCF reader and is normalized to `VcfParseError`; callers should use BGZF/bgzip for `.vcf.gz`. `ResourceKind.VCF` and `ResourceKind.BCF` remain distinct, and `VariantFile.is_bcf` must agree with the caller-declared kind. Filename suffixes are not format authority. BCF is decoded only into the same logical VCF header/record facts; provider binary objects do not enter the domain model.

### HTSlib normalization boundary

RefCompat observes the normalized VCF header representation exposed by `pysam`/HTSlib; this is not a raw-line-preserving parse. With the current `pysam`/HTSlib boundary, duplicate `##contig` IDs are collapsed before RefCompat sees them (the first exposed declaration wins), and malformed contig declarations such as a non-integer `length` may be dropped entirely. Integration tests pin those provider-visible semantics so a future dependency upgrade cannot silently change them.

Accordingly, a contig absent from `VcfHeaderData.contigs` means that the declaration was not exposed by the parser, not necessarily that no such raw header line existed. If later provenance requirements need byte-faithful duplicate/malformed-header reporting, that will require a different or additional raw-header observation path. RefCompat reads the raw provider-visible `length` header attribute where available so an explicit `length=0` remains distinguishable from an omitted length.

## Boundary with later VCF reasoning

This observation slice itself does not create VCF `ResourceContract` requirements, resolve aliases,
classify mismatch patterns, emit VCF-specific findings/verdict policy, or mutate VCF data.

Exact-name coordinate and exhaustive REF-to-FASTA comparison are implemented by the separate
[`vcf-ref-validation.md`](vcf-ref-validation.md) boundary. The subsequent
[`vcf-contract-projection.md`](vcf-contract-projection.md) bridge converts actual CHROM usage and
direct REF results into format-neutral requirements/evidence. Pair-derived exhaustive REF evidence can now be ingested by the generic whole-bundle reasoner through the separate [`vcf-bundle-orchestration.md`](vcf-bundle-orchestration.md) supplemental-capability boundary. Verified sequence binding is documented in [`vcf-sequence-binding.md`](vcf-sequence-binding.md); stable reporting remains later work. Threshold-free mismatch-pattern interpretation is documented in [`vcf-ref-conflict-patterns.md`](vcf-ref-conflict-patterns.md).
