# BAM/CRAM contract projection

**Status:** Milestone 4 core header-contract projection implemented; verified
cross-name binding and relationship classification remain later slices.

RefCompat projects the declared BAM/CRAM SAM reference dictionary into the same
format-neutral requirement vocabulary used by the rest of the reasoner. This
keeps header semantics separate from parser objects and from later
alignment-specific interpretation.

## Core requirements

For every declared `@SQ` record, `build_alignment_contract()` creates:

- a mandatory `SequencePresenceRequirement` for `SN`;
- a mandatory `SequenceLengthRequirement` for `LN`;
- when `M5` is present, a mandatory `SequenceIdentityRequirement` for that MD5.

All three are `RequirementOrigin.CORE_FORMAT`. An empty `@SQ` dictionary creates
no sequence requirements rather than inventing a reference environment.

The contract builder requires the BAM/CRAM resource to be inside the explicit
`ReferenceContext` resource scope.

## What a declared M5 means here

A SAM `@SQ M5` remains a declaration made by the alignment header. Projecting it
as an identity requirement means the selected FASTA anchor must expose the same
content-derived MD5 before that requirement can be satisfied.

This does **not** turn the header value into anchor authority. Candidate identity
evidence still comes only from `SequenceIdentityCapability` values with
`SequenceIdentityProvenance.CONTENT_DERIVED`, as enforced by the generic
constraint model and ADR 0014.

A same-name M5 disagreement is therefore a directly comparable hard identity
conflict. A same-name match can be satisfied through verified sequence identity.

## Binding remains separate

This slice intentionally emits no peer `SequenceIdentityCapability` values from
alignment `M5` declarations. Therefore:

- a different `SN` with the same M5 does not yet create a `SequenceBinding`;
- an `AN` alternate name is retained as header metadata but is not trusted as an
  alias;
- same-length/different-name records remain unresolved without verified identity
  binding;
- familiar naming conventions are never inferred.

A later Milestone 4 slice will decide when an alignment `M5` declaration is safe
to expose as `DECLARED_METADATA` binding evidence, including full-anchor
uniqueness and conflicting-header safeguards.

## Order and other metadata

`@SQ` order is preserved by the observation model but does not create a
`SequenceOrderRequirement` in this core-format contract. Order becomes mandatory
only when an explicit scope/profile requires exact ordering.

`AN`, `AS`, `UR`, `SP`, `AH`, `TP`, `@HD`, and `@PG` remain observations or
provenance in this slice. They do not create core compatibility requirements or
reference authority.

## Header-only completeness

All requirements here describe the reference environment declared by the header.
They do not prove that any alignment record actually uses a declared sequence.
RefCompat does not scan reads in this slice and does not silently drop declared
sequences based on assumptions about primary, alternate, or decoy usage.

## Standards and related design

- SAM v1: <https://samtools.github.io/hts-specs/SAMv1.pdf>
- [`alignment-header-observation.md`](alignment-header-observation.md)
- [`reference-context-bundle.md`](reference-context-bundle.md)
- [`adr/0014-identity-capability-provenance.md`](adr/0014-identity-capability-provenance.md)
