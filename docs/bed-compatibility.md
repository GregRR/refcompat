# Milestone 9 standard BED coordinate compatibility contract

**Status:** Slice 1 contract pinned; implementation pending.

Milestone 9 adds standard BED as a first-class sparse coordinate resource. The
scientific question is directional: can every reference-coordinate statement in
the BED resource be represented against the explicitly selected FASTA anchor?
The BED file does not select the anchor and does not establish an assembly merely
because its chromosome names look familiar.

Primary standards references:

- GA4GH/Samtools HTS specifications index: <https://samtools.github.io/hts-specs/>
- GA4GH BED v1 specification: <https://samtools.github.io/hts-specs/BEDv1.pdf>
- UCSC data-file format FAQ: <https://genome.ucsc.edu/FAQ/FAQformat.html#format1>

## 1. Supported BED surface

M9 targets the standard BED fields defined by BED v1. Initial support is limited
to explicitly declared exact layouts:

- BED3, BED4, BED5, BED6, BED7, BED8, and BED9;
- BED12.

BED10 and BED11 are prohibited by BED v1 because block fields are meaningful
only as the complete BED12 group. Custom BEDn+m layouts are deferred. So are
BEDPE, bedGraph, narrowPeak/broadPeak, bigBed, and other BED-derived formats
whose additional fields may introduce semantics not captured by standard BED.

UCSC track files are also outside this contract. BED v1 distinguishes them from
BED files and does not permit `track` or `browser` lines in valid BED input.
Comment lines beginning with `#` in column 1 and blank lines carry no feature
data and may appear anywhere.

Plain BED and gzip-compressed BED are transport variants of the same logical
resource for M9. Compression detection must not rely solely on a filename
suffix. bigBed is a different indexed binary format and is not covered.

## 2. Layout is explicit, not inferred

BED does not carry an in-band schema. In particular, the same fourth or later
column can be a standard BED field or a custom field, and the reference assembly
is also supplied out of band.

The M9 API must therefore require a RefCompat-owned immutable layout value that
identifies the standard field count. The inspector must not infer BED6 from six
columns or reinterpret a failed standard field as custom data. Every data line
must have exactly the declared field count in this initial standard-only scope.

The explicitly selected FASTA anchor supplies the candidate reference context;
the layout value supplies only column meaning. Neither is inferred from the
artifact name, a `track` line, a familiar `chrom` spelling, or external ambient
state.

Empty and comment-only inputs still require a declared layout. They produce a
valid empty snapshot when their bytes otherwise satisfy the input boundary.

## 3. Streaming observation boundary

The BED inspector should expose RefCompat-owned immutable values and must not
emit compatibility verdicts. At minimum it must retain:

- resource ID and declared standard layout;
- zero-based record ordinal and one-based source line;
- native `chrom`, `chromStart`, and `chromEnd` for each streamed feature;
- coordinate-bearing optional fields when declared;
- compact first-observed per-`chrom` usage counts and minimum/maximum bounds;
- total feature count; and
- bounded representative local problems for later diagnostics.

Data lines are consumed sequentially and exhaustively. The compatibility path
does not require sort order, tabix, or another index. BEDv1 recommends sorting,
but a valid unsorted resource makes the same coordinate claims and must not
receive a different scientific verdict solely because of order.

The inspector validates the declared standard fields closely enough that later
reasoning never consumes ambiguous coordinates. It need not retain display-only
values after their syntax and local invariants are checked.

## 4. Native zero-based half-open coordinates

BED positions are zero-based and half-open. M9 preserves native
`chromStart`/`chromEnd` values in BED-owned observations rather than converting
them into the positive one-based closed GTF/GFF3 model.

For a feature resolved to an anchor sequence of length `N`, representability is:

```text
0 <= chromStart <= chromEnd <= N
```

Thus `[0, 1)` describes the first base, `[N - 1, N)` describes the last base,
and `[0, N)` spans the complete sequence. Integration coverage must fail under
either a mistaken +1 conversion or a mistaken inclusive interpretation of
`chromEnd`.

BED also permits `chromStart == chromEnd` to describe a boundary feature such as
an insertion. `[0, 0)` and `[N, N)` are representable boundary positions. They
cover no reference base and must not be changed into fabricated one-base spans.
Their presence and bounds remain real coordinate statements even though their
covered-base count is zero.

## 5. Optional coordinate structure

When the declared layout includes standard optional fields, their BEDv1 syntax
and local invariants are part of input validity. In particular:

- BED7+ `thickStart` lies within the top-level feature span;
- BED8+ `thickEnd` is not before `thickStart` and lies within the span;
- BED12 has a positive `blockCount` with equally sized `blockSizes` and
  `blockStarts` arrays;
- blocks remain inside the feature, are sorted and non-overlapping, the first
  begins at `chromStart`, and the last ends at `chromEnd`.

A violation is malformed BED rather than evidence that a different FASTA would
make the resource compatible. After those invariants pass, thick and block
coordinates cannot extend beyond the top-level feature span; exhaustive anchor
bounds validation can therefore project the top-level span without creating a
separate generic requirement for every block.

Score, strand, item color, and display thickness do not establish sequence
identity or change reference-coordinate compatibility. Their standard syntax
may be validated without promoting them to scientific evidence.

## 6. Sparse presence and bounds requirements

BED is sparse. It normally mentions only sequences with features, so a FASTA
superset is not contradictory.

Each distinct feature-used `chrom` creates one mandatory
`SequencePresenceRequirement`. All data rows contribute to one scalable
`CoordinateBoundsRequirement` naming the selected FASTA anchor and the total
coordinate count. Exact-name or verified-binding resolution is used to perform
exhaustive feature checks and create one anchor-owned
`CoordinateBoundsValidationCapability`.

The generic results remain:

- resolved and wholly representable coordinates support the bounds requirement;
- any resolved out-of-bounds feature is hard Tier-B structural contradiction;
- a `chrom` that cannot be resolved remains unresolved, not proven absent;
- valid empty/comment-only BED contributes no presence or coordinate
  requirements and is not itself a compatibility conflict.

Compact BED-specific validation detail remains attached to the projection for
diagnostics, while generic bundle reasoning, evidence aggregation, findings,
conditions, verdict precedence, and conflict-core extraction remain unchanged.

## 7. Sequence-name resolution

BED carries no sequence-content identity or complete reference dictionary.
Neither coordinate equality nor a familiar spelling can establish which anchor
sequence a `chrom` denotes.

Resolution may use only:

1. an exact local-name match; or
2. an independently verified `SequenceBinding` supplied through existing
   evidence infrastructure.

Profile authorization remains subject to the M6 rule: a provider target must be
independently content-bound to the selected FASTA anchor before authoritative
provider names may resolve a BED `chrom`. Scope must not manufacture uniqueness
or hide conflicting identity evidence.

BED itself cannot prove a cross-name binding, sequence-content mismatch, or
exhaustive absence from the anchor. Raw name misses remain unresolved unless an
independent evidence path establishes a stronger result.

## 8. Stable reporting boundary

The stable report family defines `ResourceKind` as a closed enum. Adding
`ResourceKind.BED = "bed"` is therefore a MAJOR schema change even if the report
body needs no other new field.

When BED becomes serializable:

- current exact stable schema advances from `2.0.0` to `3.0.0`;
- exact `1.0.0`, `1.1.0`, and `2.0.0` schemas and known answers remain retained
  and byte-for-byte unchanged;
- schema `3.0.0` may otherwise preserve the `2.0.0` body shape while adding only
  the `bed` resource-kind value;
- retained schemas must reject `bed` rather than silently widening;
- the provisional draft revision advances at the same emit-able boundary; and
- non-BED output from the current serializer continues to identify the current
  exact schema rather than masquerading as an older version.

The enum, schema `3.0.0`, draft-revision advance, and a minimal known-answer BED
report must land atomically. There must be no intermediate state in which the
current serializer can emit `bed` while identifying its payload as schema
`2.0.0`.

The explicit BED layout is analysis input needed to interpret the artifact and
must be retained as a report `ResourceObservation` using the existing generic
observation shape. This preserves reproducibility without inventing a BED-only
top-level report branch or requiring a schema-shape change beyond the new
closed-enum value.

## 9. Error and workflow boundary

Unreadable input, invalid compression, non-BED track lines, absent or unsupported
layout declaration, inconsistent data-row width, malformed coordinates, or
invalid optional/block structure is an input problem. None is a biological
`INCOMPATIBLE` verdict.

A future report assembler must preserve the existing separation between
`INVALID_INPUT`, `PARTIAL`, and scientific results. M9 does not add BED-specific
workflow exit codes or change the established mapping.

## 10. Fixture and review strategy

Small redistributable synthetic fixtures should cover at least:

- BED3 first-base, last-base, and complete-sequence intervals;
- valid zero-length `[0, 0)` and `[N, N)` boundary features;
- end-exclusive and +1/-1 adversarial cases;
- resolved out-of-bounds and unresolved-`chrom` results;
- sparse BED against a FASTA superset and an empty/comment-only BED;
- valid unsorted data and repeated intervals;
- each supported standard field count, with focused optional-field failures;
- valid BED12 blocks plus count, containment, ordering, overlap, first-start,
  and last-end failures;
- layout mismatch, BED10/BED11, custom-field, and `track`/`browser` rejection;
- plain/gzip parity and misleading filename suffixes;
- exact-name, explicit scope, and UCSC-profile verified-binding paths;
- compatible, incompatible, indeterminate, and conditional whole-bundle results;
- exact schema `3.0.0`, retained-schema rejection, deterministic stable JSON,
  human rendering, and workflow exits.

The ordinary quality gate remains offline and deterministic. Broad corpus
collection is not required unless implementation exposes a new unresolved
category or a targeted profile needs evidence.

After representative end-to-end paths are implemented, perform an internal
scientific/API and backward-compatibility review focused on coordinate edges,
layout authority, sparse semantics, binding provenance, generic-reasoner reuse,
report-schema versioning, and retained-schema immutability. Then obtain an
independent milestone-boundary review before M9 closes.

## 11. Non-goals

M9 does not:

- infer standard-versus-custom field meaning from column count;
- support custom BEDn+m, BEDPE, bedGraph, narrowPeak/broadPeak, bigBed, or UCSC
  track files;
- require or validate sort order, tabix, or bigBed indexes;
- infer assembly identity or aliases from chromosome names;
- compare feature names, scores, strand, colors, or display style for biological
  compatibility;
- compare two BED resources for interval equality, overlap, or semantic
  equivalence;
- validate gene/transcript models or interpret blocks as exons;
- extract bases merely because a BED interval addresses them;
- perform liftover, renaming, sorting, merging, clipping, repair, or rewriting;
- add reference-free comparison, a portable manifest, or a new profile API; or
- introduce BED-specific generic requirements, evidence tiers, verdicts, or
  workflow exits.
