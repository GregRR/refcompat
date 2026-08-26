# VCF verified sequence binding and REF revalidation

**Status:** implemented as Milestone 3 RCHECK-050F.

This slice resolves VCF sequence-name differences only when the VCF supplies
content-identity metadata that can be verified against the selected FASTA
anchor. It does not infer aliases from familiar strings such as `1` and
`chr1`.

## Binding evidence

VCF 4.5 reserves `md5` on `##contig` as the MD5 checksum of the referenced
sequence. RefCompat may use that declaration as **binding evidence**, not as
reference compatibility proof.

A used VCF contig can contribute a `DECLARED_METADATA` binding identity capability only when:

- every sequence in the complete FASTA anchor snapshot has an MD5 identity available, so an unobserved duplicate target cannot hide behind missing anchor identity;
- its `md5` is syntactically valid;
- that MD5 identifies exactly one sequence in the **complete** FASTA anchor
  snapshot;
- the unique target is inside the selected anchor-sequence scope;
- the target name differs from the VCF local name; and
- if the VCF also declares a contig length, that length agrees with the target
  FASTA sequence.

Uniqueness is determined against the full anchor snapshot before scope is
applied. Scope therefore cannot manufacture certainty by hiding a duplicate
sequence with identical content.

Invalid MD5, absent MD5, duplicate-content targets, out-of-scope targets, and
length contradictions produce no binding. In particular, a cross-name header
whose declared MD5 points at one anchor sequence while its declared length
contradicts that target remains unresolved rather than using either field to
manufacture a binding or hard conflict. Familiar-looking strings never
substitute for identity evidence.

Independently of whether an MD5 binding can be established, every **used**
contig with a declared length contributes a mandatory
`SequenceLengthRequirement`. A directly resolvable same-name length conflict
therefore remains visible even when all REF records happen to fall within the
shared coordinate range. A cross-name length declaration without a verified
binding remains unresolved rather than being matched by length alone.

For every **used** contig with a syntactically valid declared MD5, the VCF
contract also retains a mandatory `SequenceIdentityRequirement`. This keeps the
header declaration visible even when it cannot establish a cross-name binding.
A same-name FASTA sequence with a different MD5 therefore produces a Tier-A
identity contradiction rather than allowing the declaration to disappear. A
cross-name declaration that cannot be bound remains unresolved rather than
inventing an alias. Invalid or unused MD5 declarations create no identity
requirement in this slice.

The VCF contract retains the context-accepted `DECLARED_METADATA` identity
capability needed to establish a safe cross-name binding separately from that
requirement. Such a capability cannot satisfy an identity requirement as
candidate evidence; whole-bundle candidate reference facts continue to come
from `CONTENT_DERIVED` identities in the selected FASTA context.

## Binding-aware REF comparison

`evaluate_vcf_ref_records()` accepts explicit `SequenceBinding` values. A
binding takes precedence over the local VCF label for FASTA lookup:

```text
VCF CHROM 1
    |
    | verified MD5 identity
    v
FASTA chr1
```

The binding changes only name resolution. The same exhaustive coordinate and
REF-base comparison then runs against the bound FASTA sequence.

Consequently:

- a bound record whose REF agrees with FASTA becomes `MATCH`;
- a bound record whose REF disagrees remains a hard `MISMATCH`;
- a bound span outside the target sequence remains `OUT_OF_BOUNDS`;
- a verified binding whose target is missing from the supplied FASTA reader is
  rejected as cross-wiring rather than downgraded to `UNRESOLVED_SEQUENCE`.

The validation result retains the IDs of bindings actually used. Those IDs are
stored deterministically and are included in the pair-derived reference-base
capability identity, so an all-match bound validation does not lose the fact
that alias evidence participated.

## Projection and bundle integration

`project_vcf_contract()` independently derives the bindings expected for the
current VCF, FASTA, and scope. If the supplied validation did not use exactly
those bindings, projection fails instead of silently projecting a stale
exact-name result.

Presence and declared-length requirements are evaluated through the same
binding and can therefore be satisfied with `VERIFIED_ALIAS`. Valid used-contig
MD5 declarations are also evaluated as generic sequence-identity requirements
against the selected or bound FASTA sequence. Matching declarations are
satisfied with `VERIFIED_SEQUENCE_IDENTITY`; directly comparable contradictions
remain Tier-A evidence. The exhaustive reference-base requirement continues to
use the separately supplied anchor-owned `ReferenceBaseValidationCapability`.

Because the accepted VCF MD5 identity capability is retained in the VCF
`ResourceContract`, ordinary whole-bundle reasoning independently derives the
same `SequenceBinding`. No VCF-specific alias path is added to `reason_bundle()`.

A header MD5 match alone can therefore never make the bundle compatible. The
mandatory exhaustive REF requirement still must be satisfied; a proven bound
REF mismatch remains Tier-A contradictory evidence and can make the bundle
`INCOMPATIBLE`.

## Safety boundary

This slice does not:

- guess aliases from names;
- cross-compare MD5 and refget identifiers;
- treat `##reference`, `assembly`, or URL metadata as sequence identity;
- let anchor-sequence scope create uniqueness;
- rewrite VCF CHROM, REF, or ALT fields;
- infer a reference build or biological cause; or
- add stable report/CLI serialization.

The VCF 4.5 specification defines the reserved `##contig` `md5` attribute as
the MD5 checksum of the sequence:
<https://github.com/samtools/hts-specs/blob/master/VCFv4.5.tex>.
