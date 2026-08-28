# BAM/CRAM non-mutation boundary

Milestone 4 is diagnostic. RefCompat can observe BAM/CRAM header facts, project
reference requirements, derive evidence-backed sequence bindings, classify
dictionary relationships, and decide whether an explicitly selected local FASTA
may be used for a future reference-dependent CRAM operation. None of those
operations authorizes RefCompat to modify the alignment resource.

This document closes the Milestone 4 roadmap requirement that RefCompat **not
reheader or realign data**. It specializes the project-wide decision in
[`adr/0005-no-silent-scientific-repair.md`](adr/0005-no-silent-scientific-repair.md)
for BAM/CRAM behavior.

## Read-only implementation boundary

The current alignment inspector opens BAM as `rb` and CRAM as `rc`, copies
parser-visible header values into immutable RefCompat-owned models, and closes
the provider handle. It does not open an output alignment file and does not
iterate records as part of header inspection.

The reasoning layers consume those immutable observations. They produce
requirements, capabilities, bindings, relationship summaries, and CRAM reference
plans; they do not write back to BAM/CRAM.

## A sequence binding is not a rename plan

A verified `SequenceBinding` means RefCompat has sufficient evidence to treat two
local sequence labels as referring to the same anchor sequence for compatibility
reasoning. The binding preserves both original labels and its evidence. It does
not imply that either resource should be renamed.

This distinction matters even for apparently familiar differences such as `1`
versus `chr1`. A binding may be scientifically justified while an in-place or
header-only rename is operationally unsafe because alignment records, indexes,
auxiliary resources, downstream tools, or provenance may depend on the original
namespace.

`@SQ AN` remains observational metadata and never becomes an automatic rename
rule.

## Dictionary relationships are descriptions, not repairs

`EXACT`, naming-difference, order-difference, subset/superset, overlap, disjoint,
M5-conflict, and unresolved states describe the declared header relationship to
the selected FASTA anchor. They do not prescribe a transformation.

In particular, RefCompat does not automatically:

- rewrite `@SQ SN`, `AN`, `LN`, `M5`, `AS`, `UR`, or other header fields;
- reorder, add, or remove `@SQ` records;
- run or emulate `samtools reheader`;
- rewrite BAM/CRAM indexes to match a changed header;
- remap alignment records to different reference names or coordinates; or
- realign reads.

A user or downstream workflow may choose a separate remediation step after
reviewing RefCompat's evidence, but that operation is outside the Milestone 4
API and outside the v0.1 diagnostic core.

## CRAM reference planning is not mutation

`CramOfflineReferencePlan` is provider-input planning. When its action is
`USE_EXPLICIT_LOCAL_ANCHOR`, it says that the selected readable FASTA is safe to
supply explicitly to a future CRAM operation that genuinely requires reference
bases. It does not embed that FASTA into the CRAM, alter `@SQ UR`, rewrite CRAM
containers, or convert the alignment.

When the evidence is insufficient, the plan is
`DEFER_REFERENCE_DEPENDENT_DECODING`. RefCompat does not repair the situation by
renaming references, fetching a different reference, or rewriting the CRAM.

## Safe next actions

Reports may identify the evidence needed to resolve an uncertainty or may state
that a separate transformation would be required for a particular downstream
workflow. Such guidance remains diagnostic: RefCompat does not execute the
transformation and does not present a familiar-looking name change as proven
safe without evidence.

This keeps the core distinction explicit:

- **reasoning:** what reference relationship is supported by the evidence;
- **remediation:** whether and how scientific data should be changed.

Milestone 4 implements the first and deliberately leaves the second outside
RefCompat's alignment path.

## Related design

- [`alignment-header-observation.md`](alignment-header-observation.md)
- [`alignment-contract-projection.md`](alignment-contract-projection.md)
- [`alignment-sequence-binding.md`](alignment-sequence-binding.md)
- [`alignment-dictionary-relationships.md`](alignment-dictionary-relationships.md)
- [`cram-offline-reference.md`](cram-offline-reference.md)
- [`adr/0005-no-silent-scientific-repair.md`](adr/0005-no-silent-scientific-repair.md)
