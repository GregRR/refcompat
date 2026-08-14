# FASTA index (`.fai`) integrity

RefCompat treats a FASTA index as an **exact derived artifact of one FASTA byte representation**. Biological equivalence is not enough: an index whose record is named `1` is not the valid companion index for a FASTA record named `chr1`, even if those labels can later be proven to denote the same biological sequence.

## Format basis

The initial implementation follows HTSlib's five-column FASTA FAI format:

1. sequence name;
2. sequence length;
3. byte offset of the first base;
4. bases per sequence line;
5. bytes per sequence line, including the line terminator where present.

Primary reference: https://www.htslib.org/doc/faidx.html

The supplied `.fai` is parsed by a narrow RefCompat reader. Expected geometry is computed from the FASTA with the public `refget.compute_fai` API and copied immediately into RefCompat-owned immutable values. No external `refget`/`gtars` object enters the reasoning model.

## Exact comparison

For an explicitly paired FASTA and `.fai`, RefCompat compares:

- record count;
- local sequence-name membership;
- sequence order when both sides contain the same names;
- sequence length;
- byte offset;
- line-bases width;
- line-bytes width.

Differences are localized by sequence and field. The result is Tier-B direct structural evidence. It is deliberately **not** a top-level compatibility verdict; later bundle reasoning decides how the failed derived-artifact requirement affects the requested scope.

## Naming and order

Sequence names in a usable FAI are required to be unique. The authoritative FASTA anchor already requires unambiguous local sequence names, and the companion index must preserve those names exactly.

An order finding is reported only when the expected and observed name sets are identical and their order differs. If a sequence is missing or extra, RefCompat reports the membership difference rather than also describing the resulting ordinal shift as an independent order problem.

## What RefCompat does not infer

A structural mismatch proves that the supplied `.fai` is not the exact index geometry computed for the supplied FASTA representation. It does **not**, by itself, prove why.

In particular, RefCompat does not label an index `stale` merely because it differs. A later provenance layer may support a stale-artifact finding if there is evidence that the `.fai` was derived from an earlier version of the same logical FASTA.

RefCompat also does not regenerate or overwrite the supplied index in diagnostic mode.

## Compression boundary

The current `refget` 0.12 `compute_fai` API documents support for **uncompressed FASTA only**. HTSlib can index BGZF-compressed FASTA using additional compressed-offset information, but RefCompat does not claim to verify that representation through the current calculator.

The initial checker therefore rejects gzip/BGZF FASTA geometry computation as an unsupported representation rather than producing an incomplete or misleading comparison. This limitation can be revisited when the project has a standards-compatible need and implementation path for compressed reference indexing.

A separate narrow limitation exists for named **zero-length FASTA sequences**. `refget`/`gtars` 0.12 reports the sequence and its length but provides no FAI line geometry because there is no sequence line to describe. RefCompat therefore reports a computation limitation for such an anchor rather than misclassifying the provider as incompatible or inventing byte-layout values.

## Error categories

The FAI boundary distinguishes:

- unreadable FASTA/FAI artifacts;
- malformed five-column FAI input;
- unsupported FASTA representation;
- failure to compute expected geometry from an otherwise readable FASTA;
- incompatible/unexpected upstream `refget.compute_fai` API results;
- unsupported resource-kind usage.

Malformed input must not be reclassified as a scientific compatibility result, and a documented calculator limitation must not be mislabeled as provider/API incompatibility.

## Validation

The integration fixture is based on the canonical example in HTSlib's `faidx(5)` documentation. The test independently asserts the published FAI values and checks that `refget.compute_fai` produces the same geometry before RefCompat evaluates the pair.
