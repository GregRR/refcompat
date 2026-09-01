# BAM/CRAM dictionary relationship reasoning

**Status:** Milestone 4 relationship reasoning implemented; Milestone 6 profile-binding reuse added.

RefCompat interprets the BAM/CRAM SAM `@SQ` dictionary relative to the selected
FASTA `ReferenceContext`. By default it derives conservative M5-backed sequence
bindings from the header. After whole-bundle reasoning, it may additionally reuse
already-validated generic `SequenceBinding` values, including an
`AUTHORITATIVE_NAME` binding established by a consumer profile. This layer is
descriptive: it summarizes the declared header relationship and does not
introduce a second alignment-specific compatibility verdict.

## Resolution boundary

Each alignment-local `SN` is considered in header order.

1. A validated `SequenceBinding` takes precedence when one exists. In the
   standalone Milestone 4 path this is an M5-backed binding derived from the
   header; when a completed bundle result is supplied it may also be an
   independently authorized naming relationship already validated by generic
   bundle reasoning.
2. Otherwise an exact `SN` match may resolve structurally to an in-scope FASTA
   sequence.
3. No `AN` value, naming convention, length equality, assembly label, URI, or
   species field creates an alias.
4. A sequence outside explicit anchor scope remains unresolved even if the
   complete FASTA contains that name or M5.

A verified binding can therefore override a misleading identical string label,
consistent with the generic sequence-binding model. Each cross-name resolution
retains the concrete `SequenceBindingId` that established it.

## Separate relationship dimensions

`classify_alignment_dictionary_relationship()` reports dimensions separately so
one difference cannot hide another.

### Membership

- `EXACT` — the resolved alignment target set equals the selected anchor set and
  there are no additional M5-distinct header records.
- `ALIGNMENT_SUBSET` — every alignment record resolves conservatively and the
  resolved target set is a strict subset of the selected anchor set.
- `ALIGNMENT_SUPERSET` — every selected anchor sequence is represented and the
  header also contains one or more M5-distinct records.
- `OVERLAP` — some selected anchor sequences are represented and the header also
  contains one or more M5-distinct records.
- `DISJOINT` — no selected anchor sequence is resolved and every alignment record
  is M5-distinct under the conservative complete-anchor rule.
- `UNRESOLVED` — unfamiliar/ambiguous names, scope exclusions, or a non-bijective
  local-to-anchor mapping prevent a complete membership statement.

An empty `@SQ` dictionary is mathematically an `ALIGNMENT_SUBSET` of a non-empty
selected anchor, but its naming, order, and M5-content dimensions remain
`UNRESOLVED`. Consumers must not treat the membership dimension alone as proof
that reference usage or provider addressability has been established.

An unfamiliar local name is **not** automatically extra. RefCompat records it as
M5-distinct only when:

- the complete FASTA anchor has MD5 coverage for every sequence;
- neither the local `SN` nor a declared `AN` names any sequence anywhere in the
  complete FASTA; and
- the declared `@SQ M5` does not match any content-derived FASTA MD5.

This remains a relationship among **declared header facts** and independently
derived anchor facts. It does not independently recompute the alignment-local
reference sequence behind the M5 declaration. `AN` never creates a binding,
but an `AN` that names the anchor makes an otherwise-extra record unresolved
rather than letting RefCompat ignore internally competing header claims.

### Naming

- `EXACT` — every resolved shared sequence uses the anchor-local name.
- `VERIFIED_DIFFERENCE` — at least one shared sequence uses a different local
  name resolved through a validated sequence binding. The per-sequence resolution
  records whether that binding came from verified M5 identity or an authoritative
  naming relationship.
- `UNRESOLVED` — naming cannot be stated safely for the complete shared mapping.

`verified_naming_only_difference` is true only when membership is exact, order
is consistent, every shared M5 is verified against the anchor, lengths agree,
and verified names are the only remaining difference.

### Order

- `CONSISTENT` — resolved shared sequences occur in the same relative order as
  those anchor sequences.
- `DIFFERENT` — resolved shared sequences are reordered.
- `UNRESOLVED` — unresolved or duplicate target mappings prevent a safe order
  comparison.

For subset/superset/overlap summaries, extra header sequences are ignored when
checking the **relative order of the shared anchor sequences**. This does not
make order a mandatory core constraint; order policy remains separate.

### M5 content

- `M5_VERIFIED` — every sequence resolved to the selected anchor declares an M5
  equal to that anchor sequence's content-derived MD5.
- `M5_CONFLICT` — at least one resolved sequence declares a directly comparable
  M5 that disagrees with the anchor.
- `UNRESOLVED` — comparable M5 evidence is missing or some sequence resolution
  remains unresolved.

Length disagreement is retained separately in
`length_conflict_sequence_names`. A matching M5 does not erase a contradictory
`LN`, and a length disagreement does not rewrite the M5 observation. An
authoritative-name binding resolves naming only: if the header does not declare
M5, the M5-content dimension remains `UNRESOLVED` rather than borrowing provider
target identity as if it were alignment-owned content evidence.

## Exact identity

`exact_identity` is intentionally strict. It requires:

- exact membership;
- exact primary names;
- consistent order;
- M5 verification for every resolved sequence; and
- no declared-length conflict.

Same names and lengths without complete M5 evidence therefore remain
structurally exact but do not become an exact-identity claim.

## Duplicate local identities

Two different alignment-local names may each carry valid M5 evidence for the
same unique FASTA sequence. The binding layer permits those independent facts,
but relationship classification does not call the resulting dictionary an
exact subset/superset relationship because the local-to-anchor mapping is not
bijective. `duplicate_anchor_target_names` records that condition and membership
remains `UNRESOLVED`.

Future BAM/CRAM reporting must surface this relationship context alongside any
generic compatibility verdict rather than presenting the verdict alone. In
particular, `duplicate_anchor_target_names` must remain visible when a
non-bijective dictionary has individually satisfiable sequence requirements.

## Header-only completeness

All of these relationships describe the declared SAM header. They do not prove
that reads use every declared sequence, that no undeclared reference content is
needed by record decoding, or that mapped reads are biologically correct.

RefCompat still does not scan reads in this slice, infer usage from absence of
records, reheader/rename references, or retrieve CRAM reference content. A
separate offline plan defines whether an explicitly selected local FASTA may be
used if future CRAM record decoding genuinely requires reference bases.

## Related design

- [`alignment-header-observation.md`](alignment-header-observation.md)
- [`alignment-contract-projection.md`](alignment-contract-projection.md)
- [`alignment-sequence-binding.md`](alignment-sequence-binding.md)
- [`reference-context-bundle.md`](reference-context-bundle.md)
- [`cram-offline-reference.md`](cram-offline-reference.md)
- [`alignment-non-mutation-boundary.md`](alignment-non-mutation-boundary.md)
