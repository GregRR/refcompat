# Exhaustive VCF REF ↔ FASTA validation

**Status:** implemented direct-evidence boundary for Milestone 3 RCHECK-050B. The subsequent
format-neutral contract/evidence bridge is implemented in
[`vcf-contract-projection.md`](vcf-contract-projection.md).

This slice exhaustively compares every VCF record's `REF` allele with an
explicitly supplied FASTA anchor. It remains the direct record-level source
result; contract/evidence projection is a separate layer, and VCF-specific
pattern classification is implemented separately in
[`vcf-ref-conflict-patterns.md`](vcf-ref-conflict-patterns.md), while verified-alias
revalidation and report presentation remain later work.

## Inputs and traversal

`iter_vcf_ref_records()` streams every VCF record sequentially in file order and
copies only RefCompat-owned primitive fields:

- source VCF resource ID;
- zero-based file ordinal;
- `CHROM`;
- native one-based `POS`;
- `REF`.

The iterator supports plain VCF and BGZF-compressed VCF and does not require a
VCF tabix/CSI index. BCF remains deferred with the rest of the current VCF
adapter boundary.

The evaluator requires every record to carry the requested VCF resource ID and
requires ordinals to be contiguous from zero. Cross-wired, skipped, or reordered
record streams therefore cannot accidentally be described as an exhaustive
result for another artifact.

## Authoritative FASTA access

Base comparison must not trust an arbitrary adjacent `.fai` supplied by the
user. `open_fasta_sequence_reader()` therefore:

1. computes exact FAI geometry from the supplied FASTA representation using the
   existing RefCompat FAI computation boundary;
2. writes that geometry to a temporary index outside the FASTA directory;
3. opens `pysam.FastaFile` with that explicit temporary index path;
4. removes the temporary index when the reader closes.

An existing `<reference>.fai` is neither read nor rewritten by this path. The
current FAI computation boundary supports uncompressed FASTA only, so
RCHECK-050B inherits that representation limit for now.

## Per-record states

Every streamed record produces exactly one direct state:

- `MATCH` — exact-name FASTA sequence exists, the REF span is in bounds, and
  normalized FASTA bases equal REF;
- `MISMATCH` — the span is comparable and the FASTA bases contradict REF;
- `OUT_OF_BOUNDS` — the exact-name sequence exists but the ordinary REF span
  cannot be represented within that sequence;
- `UNRESOLVED_SEQUENCE` — the VCF `CHROM` has no exact-name FASTA sequence in
  this slice.

`UNRESOLVED_SEQUENCE` deliberately does **not** infer that familiar-looking
names such as `1` and `chr1` are aliases. Later SequenceBinding integration may
resolve such a record only from verified identity evidence.

### Coordinate conversion

VCF `POS` is one-based. For a REF string of length `L`, the FASTA fetch interval
is exactly:

```text
start = POS - 1
end   = start + L
```

The comparison intentionally uses `POS` plus `len(REF)`, not a parser's
`record.stop`, because symbolic-allele `END` semantics are not the REF span.

VCF 4.5 permits telomere sentinel positions `0` and `N+1`. Those positions have
no ordinary FASTA base interval for REF comparison and are represented here as
`OUT_OF_BOUNDS`. In this direct-evidence model that state means "not directly
comparable as an ordinary FASTA interval"; it does not by itself claim that the
VCF record is syntactically invalid.

## Reference alphabet

VCF REF uses `A`, `C`, `G`, `T`, or `N` case-insensitively. VCF 4.5 also states
that when the FASTA contains another IUPAC ambiguity code, the VCF REF
representation uses the alphabetically first concrete base represented by that
code. RefCompat applies that reduction before comparison:

```text
R -> A    Y -> C    S -> C    W -> A    K -> G    M -> A
B -> C    D -> A    H -> A    V -> A
```

`A/C/G/T/N` remain themselves. Unsupported FASTA symbols abort this direct
check rather than fabricating a `MISMATCH` conclusion.

## Aggregation and traceability

`VcfRefValidationResult` records exhaustive aggregate and per-VCF-sequence
counts. It retains an individual `VcfRefRecordCheck` for every non-match:

- every mismatch;
- every out-of-bounds record;
- every unresolved sequence record.

Matching records are counted but not retained individually, so a large fully
compatible VCF does not require memory proportional to its record count.
Mismatches retain the actual fetched FASTA bases needed to explain the local
content contradiction.

This is descriptive aggregation only. A tiny mismatch fraction never erases a
known mismatch. Threshold-free isolated/localized/distributed/systematic
distribution
interpretation is implemented separately in
[`vcf-ref-conflict-patterns.md`](vcf-ref-conflict-patterns.md).

## Deliberately deferred

This slice does not yet:

- project verified `SequenceBinding` aliases into VCF REF checking;
- add VCF-specific pattern-dependent finding or verdict policy;
- apply evaluation-scope exclusions;
- sample records;
- rewrite, swap, normalize, delete, or repair REF/ALT alleles.

Those remain later Milestone 3 reasoning/reporting boundaries.
