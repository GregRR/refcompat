# ADR 0014 — Distinguish derived and declared sequence identity

**Status:** Accepted
**Date:** 2026-08-25

## Context

RefCompat uses sequence identity in two distinct roles. FASTA anchor identities
are derived from sequence content, while formats such as VCF and BAM/CRAM may
declare MD5/M5 values as metadata claims. A declared value can be useful for
conservative sequence-name binding, but it must not become reference authority
or satisfy an identity requirement merely because it has the same primitive
digest type.

Representing both roles without provenance makes that safety boundary depend on
call-site discipline and becomes riskier as more formats add declared identity
metadata.

## Decision

`SequenceIdentityCapability` carries required explicit provenance distinguishing
`CONTENT_DERIVED` from `DECLARED_METADATA`. Constructors must choose one; there
is no default provenance.

Only content-derived identity capabilities may satisfy
`SequenceIdentityRequirement` constraints or appear as authoritative anchor
identity capabilities in `ReferenceContext`. Declared metadata may participate
in conservative `SequenceBinding` derivation, where it is compared against
content-derived identities reconstructed from the complete FASTA anchor
snapshot.

`ReferenceContext` independently verifies that its anchor identity capabilities
exactly match the identities present on the selected FASTA snapshot sequences.

## Consequences

VCF `##contig md5` and future BAM/CRAM `@SQ M5` values can use the same typed
identity value while retaining a structural claim-versus-derived distinction.
Accidentally passing a declared identity as candidate reference evidence fails
at the constraint boundary instead of relying on convention.

Sequence binding remains conservative: metadata claims can identify an anchor
target only under the existing uniqueness and consistency rules, and a binding
does not turn the claim itself into reference authority.

The provenance discriminator is runtime-checked but is not self-proving. A new
producer could still incorrectly label declared metadata as ``CONTENT_DERIVED``
at construction time. That residual risk is accepted: provenance must be chosen
explicitly at every construction site, and format adapters must test and review
that choice against the origin of the identity value.
