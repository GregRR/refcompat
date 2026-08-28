# BAM/CRAM verified sequence binding

**Status:** Milestone 4 verified cross-name M5 binding implemented.

RefCompat may use a SAM `@SQ M5` declaration to resolve a BAM/CRAM-local
reference name to a differently named FASTA anchor sequence, but only through
explicit content-identity evidence. Familiar naming conventions and `AN`
alternate-name declarations are not sufficient.

## Binding evidence

SAM defines `M5` as the MD5 checksum of the reference sequence and explicitly
notes that it can help resolve naming ambiguity between otherwise differently
named references. RefCompat nevertheless treats the header value as
**declared metadata**, not as anchor authority.

An alignment `@SQ` record contributes a `DECLARED_METADATA`
`SequenceIdentityCapability` for binding only when:

- every sequence in the complete FASTA anchor snapshot has an MD5 identity, so
  missing anchor identity cannot hide a duplicate target;
- the declared M5 identifies exactly one sequence in the **complete** FASTA
  anchor snapshot;
- that unique target is inside the selected anchor-sequence scope;
- the target name differs from the alignment-local `SN`; and
- the target FASTA sequence length agrees with the same `@SQ LN` declaration.

Uniqueness is evaluated against the full anchor snapshot before explicit
anchor-sequence scope is applied. Scope may therefore hide an otherwise unique
target, but it cannot manufacture uniqueness by hiding another sequence with
the same content.

If the target has the same name as `SN`, no binding capability is needed; the
ordinary exact-name requirement path evaluates the declaration directly.

## Conservative failures

No binding is created when:

- `M5` is absent;
- the complete anchor lacks MD5 coverage;
- the M5 matches zero or multiple anchor sequences;
- the unique target is outside anchor-sequence scope;
- the target has the same local name; or
- the target length conflicts with `LN`.

A cross-name M5/LN contradiction therefore remains unresolved rather than
using one declared header field to overrule another or manufacturing a hard
cross-name conflict without a verified binding.

`AN` remains observational metadata in this slice. An alternate name that
happens to equal an anchor name does not establish a binding without usable M5
identity evidence.

Two different alignment-local names may independently bind to the same anchor
sequence when each carries the same M5 and that content identity is unique in
the complete FASTA anchor. Uniqueness applies to the **target identified by the
content**, not to a requirement that every resource use one canonical local
label.

## Relationship reasoning

Verified bindings are also the only cross-name mappings consumed by
[`alignment-dictionary-relationships.md`](alignment-dictionary-relationships.md).
That layer remains descriptive and does not promote `AN` or name resemblance.

## Contract and bundle integration

`build_alignment_contract()` retains safe cross-name M5 binding capabilities in
the alignment `ResourceContract` alongside the mandatory presence, length, and
identity requirements established by the previous Milestone 4 slice.

The ordinary generic `reason_bundle()` path then derives the same
`SequenceBinding` through `derive_sequence_bindings()`; there is no separate
alignment-only evaluator or verdict path.

For a verified cross-name binding:

- sequence presence may be satisfied with `VERIFIED_ALIAS`;
- sequence length may be satisfied with `VERIFIED_ALIAS`;
- the mandatory M5 requirement is still checked against the bound FASTA
  sequence's **content-derived** MD5 and may be satisfied with
  `VERIFIED_SEQUENCE_IDENTITY`.

The declared alignment capability itself cannot satisfy that identity
requirement because generic comparability accepts only
`SequenceIdentityProvenance.CONTENT_DERIVED` candidate identity evidence. Its
sole role is conservative name binding.

A verified content identity also takes precedence over a misleading identical
string label. If alignment-local `SN=chr1` declares an M5 that uniquely and
length-consistently identifies anchor `chr2`, the verified binding is
`chr1 -> chr2`; the familiar `chr1` string does not override stronger identity
evidence.

## Header-only boundary

Binding still describes only the reference environment declared by the SAM
header. It does not prove that any alignment record actually uses the bound
sequence, and this slice does not scan reads or decode reference-dependent CRAM
records.

The binding layer also does not:

- trust `AN`, `AS`, `UR`, `SP`, `AH`, `TP`, or `@PG` as sequence identity;
- infer aliases from `chr` prefixes or other string patterns;
- compare M5 and refget identifiers across algorithms;
- make sequence-order policy decisions;
- reheader, rename, realign, or otherwise modify BAM/CRAM data.

## Standards and related design

- SAM v1: <https://samtools.github.io/hts-specs/SAMv1.pdf>
- [`alignment-header-observation.md`](alignment-header-observation.md)
- [`alignment-contract-projection.md`](alignment-contract-projection.md)
- [`reference-context-bundle.md`](reference-context-bundle.md)
- [`adr/0014-identity-capability-provenance.md`](adr/0014-identity-capability-provenance.md)
