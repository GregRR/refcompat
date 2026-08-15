# FASTA / sequence-dictionary integrity

RefCompat's initial SAM/Picard `.dict` check answers a narrow question:

> Does this sequence dictionary exactly describe the ordered FASTA anchor, and what stronger or weaker evidence does the dictionary provide about sequence identity?

The check deliberately separates **exact companion-artifact structure** from **biological sequence identity** and from **provenance metadata**.

## Standards basis

The SAM specification defines `@SQ` as the reference sequence dictionary. Every `@SQ` requires `SN` and `LN`, the order of `@SQ` lines defines reference ordering, and all primary `SN` names plus every individual `AN` alternate name across the dictionary must be distinct. `LN` is restricted to 1 through 2^31-1.

Relevant optional fields include:

- `M5` — MD5 checksum of the sequence;
- `AN` — alternate reference-sequence names;
- `AS` — genome assembly identifier;
- `SP` — species;
- `UR` — sequence URI/path;
- `TP` — molecule topology (`linear` or `circular`);
- `AH` — alternate-locus relationship.

SAM explicitly describes `M5` as sequence-derived identity evidence that can help establish that differently named references carry the same sequence content. RefCompat therefore treats an M5 contradiction as stronger evidence than a name/length-only structural contradiction.

Primary references:

- SAM v1 specification: <https://samtools.github.io/hts-specs/SAMv1.pdf>
- samtools `dict`: <https://www.htslib.org/doc/samtools-dict.html>
- Picard `CreateSequenceDictionary`: <https://gatk.broadinstitute.org/hc/en-us/articles/360037068312-CreateSequenceDictionary-Picard>

## Exact companion semantics

The dictionary's primary `SN` values, sequence membership, order, and lengths are compared exactly with records expected from the complete FASTA identity snapshot.

A declared alias does **not** substitute for the FASTA's primary local name in this derived-artifact check. For example:

```text
FASTA name: chr1
DICT SN:    1
DICT AN:    chr1
```

may provide useful alias evidence, but the `.dict` is not an exact primary-name companion of that FASTA representation.

Similarly, a unique matching M5 under different primary names can establish Tier-A sequence-content identity while the exact companion-artifact check still reports the name/membership difference.

## M5 semantics

For exact-name records:

- matching M5 values provide content-level support;
- conflicting M5 values are Tier-A content contradictions;
- missing dictionary M5 is an **evidence gap**, not a contradiction.

Therefore a dictionary with exact names, order, and lengths but no M5 can be structurally verified without being content-verified as an exact companion.

Cross-name M5 relationships are surfaced only when unambiguous. If the same M5 occurs more than once on either side, RefCompat does not guess which differently named records correspond.

For a unique cross-name pair, matching M5 and matching `LN` can be surfaced as content-identity support. If the M5 matches but the declared lengths disagree, RefCompat retains an explicit M5/LN inconsistency instead of silently discarding the relationship or promoting it to uncomplicated identity support. The inconsistency does not by itself determine whether the M5, the length, or some upstream provenance is wrong.

## Provenance metadata

`AS`, `SP`, `UR`, `TP`, `AH`, and declared `AN` values are preserved as observations for later provenance/profile reasoning. This slice does not use them to override exact structural or M5 evidence.

For example, `AS:GRCh38` cannot outweigh a conflicting M5, and `AN:chr1` cannot make primary `SN:1` an exact match for FASTA `chr1`.

## What the parser accepts

The initial `.dict` parser intentionally targets sequence-dictionary artifacts rather than becoming a general SAM parser. It accepts:

- an optional first `@HD` line with a valid `VN` tag;
- one or more `@SQ` records;
- standard or unknown tags on `@SQ` records, while preserving the fields RefCompat currently needs.

It rejects alignment records, unrelated SAM header-record types, duplicate tags, missing `SN`/`LN`, invalid SAM reference names, invalid lengths, malformed M5 values, invalid topology, and collisions among `SN` and `AN` names.

BAM/CRAM header inspection will be implemented separately and can reuse the relevant dictionary model without turning this narrow `.dict` reader into a full SAM parser.

## Expected dictionary from FASTA identity

RefCompat does not reread or rehash the FASTA to construct expected `.dict` records. It reuses the already computed complete `SequenceCollectionSnapshot` and requires each sequence to have:

- an unambiguous local name representable as a SAM `SN`;
- a positive SAM-representable length;
- a content MD5 from the FASTA identity provider.

A zero-length FASTA sequence can exist in RefCompat's generic identity model, but SAM `LN` cannot represent length zero. That case is reported as a dictionary-computation limitation rather than as provider incompatibility or a biological contradiction.

## Evidence model

Dictionary evidence is intentionally mixed-strength:

- M5 conflict or unique M5-backed cross-name identity with consistent lengths: **Tier A — conclusive content evidence** under SAM M5 semantics;
- names, sequence membership, order, and lengths: **Tier B — direct structural evidence**;
- unique cross-name M5 agreement with disagreeing lengths: retained as an explicit mixed M5/LN inconsistency rather than collapsed into a single evidence tier;
- `AS`, `SP`, `UR`, `AN`, `TP`, `AH`: retained metadata/claims for later interpretation.

The current evaluator reports exact differences and evidence gaps. It does not yet create the final project-level `COMPATIBLE`, `INCOMPATIBLE`, or `INDETERMINATE` verdict.

## No stale-artifact inference

A mismatching `.dict` is not automatically called **stale**. Structural or M5 disagreement proves that the supplied pair does not agree in the observed way; determining that the dictionary was derived from an earlier FASTA version requires separate provenance evidence.

Likewise, RefCompat does not automatically rewrite `SN`, regenerate a dictionary, or change sequence metadata.
