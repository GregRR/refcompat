# BAM/CRAM header observation

**Status:** Milestone 4 header-observation boundary implemented.

RefCompat inspects the SAM header carried by BAM and CRAM resources before it
attempts compatibility reasoning. This boundary is observational: header fields
are declarations made by the alignment resource, not independently verified
facts about the selected FASTA anchor.

## Scope

`inspect_alignment_header()` accepts resources explicitly typed as `BAM` or
`CRAM` and copies the parser-visible SAM header into RefCompat-owned immutable
values.

From `@HD`, RefCompat currently preserves:

- `VN` — SAM format version;
- `SO` — declared sort order;
- `GO` — declared grouping order;
- `SS` — declared sub-sort order.

From each ordered `@SQ` record, RefCompat preserves:

- `SN` — primary sequence name;
- `LN` — declared sequence length;
- `M5` — declared SAM sequence MD5, when present;
- `AN` — alternate sequence names;
- `AS` — assembly identifier;
- `UR` — sequence URI;
- `SP` — species;
- `AH` — alternate-locus declaration;
- `TP` — molecule topology.

The tuple order of the `@SQ` records is preserved exactly. SAM defines `@SQ`
order as the reference ordering used by coordinate sorting, but this observation
slice does not yet decide whether a different order is compatible for a given
evaluation scope.

From `@PG`, RefCompat preserves the standard program provenance fields `ID`,
`PN`, `CL`, `PP`, `DS`, and `VN`. Program metadata remains provenance evidence;
it does not establish sequence identity.

## M5 is declared metadata

An alignment `@SQ M5` is copied into the domain model as a normalized
`Md5Digest`, but its presence in a BAM/CRAM header does not make it
content-derived anchor authority. Milestone 4 contract/binding work must convert
such values to identity capabilities only with
`SequenceIdentityProvenance.DECLARED_METADATA`, as required by ADR 0014.

This is the same claim-versus-derived distinction already enforced for VCF
`##contig md5` metadata.

## Header-only completeness

This slice does **not** iterate alignment records. Therefore:

- an `@SQ` declaration does not prove that any read actually uses that sequence;
- the absence of observed record usage is not inferred from the header;
- no mapping-quality, CIGAR, read-group, or alignment-correctness conclusion is
  made;
- an empty `@SQ` dictionary is representable so an unmapped-only alignment
  resource can still be observed without inventing reference requirements.

Future Milestone 4 reasoning projects the declared header dictionary into
reference requirements while keeping these header-only limits explicit.

## CRAM and reference availability

CRAM stores a textual SAM header in its initial header container. RefCompat's
header observation opens a CRAM resource and reads that header without scanning
alignment records and without supplying a reference FASTA to pysam. Merely
observing the header therefore must not require reference-sequence retrieval.

This does **not** imply that later CRAM record decoding is reference-independent.
Milestone 4 will define separately what can be concluded when CRAM operations
that genuinely require reference content cannot obtain it offline.

## Provider boundary

The adapter uses `pysam.AlignmentFile`, reads the provider's unparsed SAM header
text, copies normalized primitive values immediately, and closes the provider
without yielding provider-owned objects. RefCompat parses only the standard tags
it needs and ignores valid extension tags rather than asking pysam's validating
`AlignmentHeader.to_dict()` conversion to recognize every tag. The resource's
declared `ResourceKind` must agree with the format identified by pysam; a
BAM/CRAM mismatch is rejected rather than silently reclassified.

BAM stores its binary reference-name/length dictionary separately from the plain
SAM header text. If textual `@SQ` lines are absent but pysam exposes that binary
dictionary, RefCompat retains those names and lengths rather than reporting an
empty reference environment. When both views are present, their ordered names and
lengths must agree.

The adapter opens with `check_sq=False` so truly header-only files without `@SQ`
or binary reference records remain observable. RefCompat-owned model validation
still enforces SAM sequence-name/length rules, global `SN`/`AN` distinctness,
valid M5 values, and unique `@PG ID` values on the normalized data it accepts.

## Explicit non-goals for this slice

This slice does not yet:

- build BAM/CRAM `ResourceContract` requirements;
- compare `@SQ` declarations with the FASTA anchor;
- derive sequence bindings from `M5` or `AN`;
- classify exact/subset/superset/order relationships;
- scan reads to determine actual reference usage;
- decode CRAM records that require external reference content;
- reheader, realign, rename, or otherwise modify the alignment resource.

## Standards

- SAM v1: <https://samtools.github.io/hts-specs/SAMv1.pdf>
- CRAM v3: <https://samtools.github.io/hts-specs/CRAMv3.pdf>
- pysam AlignmentFile API: <https://pysam.readthedocs.io/en/latest/api.html>
