# UCSC preflight profile

**Status:** Milestone 6 Slices 1–7 implemented: provider snapshot, target-content/name reasoning, generic profile binding, VCF and BAM/CRAM integration, deterministic provider/offline snapshot handling, and the adversarial milestone-exit suite are complete. The first internal scientific/code checkpoint and targeted Slice 4 external review are closed, including the reviewer-requested peer-identity regression coverage. CRAM offline decoder-reference eligibility remains intentionally stricter than profile compatibility. The final internal milestone review and required external milestone-boundary review are complete; the external review found no MAJOR issue, and its one MINOR fail-loud alignment-binding invariant is regression-pinned before M7.

RCHECK-070 defines RefCompat's first ecosystem profile. The profile asks whether
in-scope resources can satisfy the reference-coordinate and naming requirements
of one explicitly selected native UCSC Genome Browser database while preserving
the selected FASTA as RefCompat's reference anchor.

The profile is deliberately conservative. A UCSC database name, chromosome
style, alias table, sequence length, assembly accession, download path, or other
provider metadata can describe the intended target, but none of those facts is
sequence identity for an arbitrary local FASTA.

The normative check summary is in
[`check-specifications.md`](check-specifications.md). This note pins the
scientific and provider boundary that Milestone 6 implementation must preserve.

## First Milestone 6 scope

The first `ucsc-preflight` implementation supports:

- one explicitly selected **native UCSC Genome Browser database**;
- the existing FASTA anchor model;
- UCSC canonical sequence names and lengths;
- UCSC-authoritative sequence-name aliases;
- content-derived identity for provider target sequences when available;
- existing VCF/VCF.gz REF and coordinate evidence;
- existing BAM/CRAM dictionary reasoning;
- reuse of generic coordinate reasoning where an already-supported resource
  participates in the profile.

The first milestone does **not** add:

- assembly-hub or GenArk-specific target semantics;
- bigBed/bigWig reference-property inspection;
- full track-hub reasoning;
- a replacement for UCSC `hubCheck`;
- persistent provider-cache policy;
- automatic sequence renaming, reheadering, conversion, or repair;
- build guessing from names, coordinates, metadata, species, or filenames.

Those boundaries keep the first profile focused on reference compatibility
rather than turning RefCompat into a UCSC client or track-hub validator.

## Explicit target selection

Activating `ucsc-preflight` is not enough by itself. The caller must select a
specific UCSC database identifier, such as a native Genome Browser `db` value.
The profile never chooses a target from:

- `hg38`/`mm39`-like text in filenames or headers;
- `chr` prefixes or other chromosome-name style;
- species labels;
- coordinate ranges;
- BAM `AS`/`UR` metadata;
- VCF `##reference` metadata;
- GFF/GTF provider/build comments.

Those may remain provenance claims. They do not select or authenticate the UCSC
target.

## Provider snapshot

Compatibility reasoning consumes an immutable provider snapshot. Network or
file acquisition belongs outside the reasoner.

The snapshot must keep these dimensions distinct:

1. the selected UCSC database identifier;
2. canonical UCSC sequence names and lengths;
3. authoritative sequence-name alias relationships and their named authority
   columns when available;
4. content-derived sequence identity for UCSC target sequences when available;
5. completeness for the sequence catalog, alias evidence, and identity coverage;
6. source/provenance information sufficient to explain where and when each
   provider fact was acquired.

Completeness is dimensional. A complete sequence catalog does not imply complete
content-identity coverage, and complete retrieval of the provider's alias table
does not imply that every biologically equivalent external name is represented
there.

Provider pieces must remain tied to one database context. An alias source for
one database must not be combined with a sequence catalog or target-content
source for another. A response that cannot be associated safely with the
selected database is unusable provider evidence; it is not evidence that the
user's genomic resources are biologically incompatible.

The snapshot is evidence, not authority over the selected FASTA. It never
replaces `ReferenceContext` or allows peer/provider resources to vote on the
anchor.

The implemented snapshot boundary lives in `refcompat.profiles.ucsc` rather than
in the generic model. `UcscProviderSnapshot` retains the selected database plus
an explicit opaque provider-context identifier, three independent completeness
dimensions, canonical `UcscSequence` values, `UcscSequenceAlias` relationships,
and timezone-aware `UcscProviderSource` provenance. Sequence and
alias facts cite the exact source IDs that supplied their catalog, identity, or
alias evidence. Construction rejects source/database or same-database/provider-context
cross-wiring, unknown or wrong-dimension provenance, duplicate canonical names,
dangling alias targets, known alias completeness without alias-source evidence,
and completeness claims inconsistent with the represented catalog/identity
coverage.

The snapshot deliberately preserves duplicate biological content under distinct
canonical names and aliases that resolve to multiple canonical targets. Those
are scientifically meaningful ambiguity cases for later reasoning; the provider
model must not manufacture uniqueness by deleting them. It also keeps canonical
lookup separate from alias lookup, so merely querying the snapshot cannot turn an
alternate name into a binding.

## Anchor-to-UCSC target identity

A fully positive UCSC-target conclusion requires a content-derived bridge from
the selected UCSC target sequence to the selected FASTA anchor for every target
sequence needed to establish a mandatory in-scope relationship.

Sufficient bridge evidence is an independently comparable biological sequence
identity, such as a refget identity or comparable MD5 derived from the UCSC
target sequence content. The implementation may obtain such identity through a
narrow provider adapter or another independently authenticated standards-aware
resolver, but it must retain provenance and must not convert a provider label
into a digest.

The following are **not** sufficient to create that bridge:

- identical names;
- identical lengths;
- a UCSC database identifier;
- a `chromAlias` relationship;
- GenBank/RefSeq/Ensembl-looking accessions by themselves;
- a download URL or filename;
- an assembly/provider label;
- multiple weaker facts that happen to agree.

When a comparable UCSC target identity is available, matching happens against
the complete FASTA anchor before explicit sequence scope is applied. Exactly one
anchor target must be established. Duplicate matching content, conflicting
identity evidence, or a match hidden outside explicit scope does not become a
usable scoped identity by removing alternatives.

A provider-target identity proves that required target content is absent only
when the same identity scheme is available for every sequence in the complete
FASTA anchor and none matches the provider target. That exhaustive absence is a
real contradiction to the explicit UCSC profile requirement. A mismatch against
merely the same-named anchor sequence is not enough when another anchor sequence
could still match. If comparable anchor coverage is incomplete, target identity
is unavailable, or resolution is non-unique, the relationship remains unresolved
rather than being guessed from names and lengths.

The implemented Slice 3 target resolver reuses the generic
`AnchorIdentityResolution` path that now also underlies ordinary content-derived
`SequenceBinding`. A provider target is `BOUND` only when at least one comparable
identity scheme covers the complete FASTA anchor, resolves uniquely there, every
other known positive identity match agrees, the target remains in explicit scope,
and the provider catalog length agrees with the content-bound FASTA sequence. A
complete-scheme miss can become `PROVEN_ABSENT` only when no supplied provider
identity positively matches any anchor sequence under another scheme. Missing
identity, incomplete coverage, duplicate content, conflicting cross-scheme
evidence, an out-of-scope unique target, or a provider length/content conflict
remains `UNRESOLVED`. Exact UCSC names are not consulted during this content
step.

## Authoritative alias semantics

UCSC documents `chromAlias` as a mechanism for mapping alternate sequence-name
authorities to the names used by a Genome Browser assembly. RefCompat treats
such data as **authoritative provider naming evidence**, not content identity.

An authoritative alias can project a resource-local name to an anchor sequence
only when all of the following are true:

1. the alias evidence belongs to the explicitly selected UCSC database;
2. the alias resolves to exactly one canonical UCSC target in the complete
   relevant provider naming context, including both the canonical catalog and
   alias evidence;
3. that UCSC target has already been content-bound to exactly one sequence in
   the complete FASTA anchor;
4. that anchor target remains inside explicit evaluation scope; and
5. no stronger directly comparable content evidence contradicts the
   relationship.

This ordering is intentional:

```text
resource-local name
    -> provider-authoritative alias
    -> canonical UCSC target
    -> content-derived target identity
    -> selected FASTA anchor sequence
```

The alias never short-circuits the content-derived UCSC-target-to-anchor step.
String resemblance is not a fallback alias source.

A missing alias in complete provider naming evidence establishes only that the
provider snapshot did not declare that naming relationship. It does not prove
that the underlying biological sequence is absent or different. Incomplete or
ambiguous naming evidence remains unresolved.

Distinct canonical UCSC target names remain distinct coordinate axes even when
the provider reports identical sequence content. If two distinct canonical
targets required by the evaluated bundle would both resolve to the same single
FASTA anchor sequence, the profile withholds positive binding validation for
those relationships rather than collapsing the axes. An advisory colliding target
remains unresolved without indirectly blocking an otherwise valid mandatory
canonical relationship. Multiple resource-local aliases that resolve to the same
canonical UCSC target are not such a collision.

Slice 3 implements this provider-name step separately from target identity. A
represented canonical UCSC name resolves directly to that provider target but
claims nothing about FASTA content. An alternate name resolves only when the
snapshot declares both the canonical sequence catalog and alias dimension
`COMPLETE` and every matching alias row
points to one canonical target; multiple authority columns may repeat the same
relationship without creating ambiguity. Requiring the complete catalog prevents
an omitted canonical name from colliding invisibly with a represented alternate
name. A familiar but undeclared name, partial/unknown catalog or alias coverage,
or one alias pointing to multiple targets stays unresolved. Slice 4 composes that
naming result with the independently resolved provider target while retaining
both provider source provenance and the anchor-content proof trace.

## Profile projection into the generic reasoner

The profile adds consumer requirements; it does not replace core resource
contracts.

The intended projection is:

1. preserve every core-format requirement already produced for the resource;
2. add profile-origin requirements needed to establish the selected UCSC target;
3. derive any authoritative alias relationship with explicit provider and
   anchor-content evidence trace;
4. pass those requirements/relationships into the existing generic constraint,
   evidence, finding, condition, and verdict machinery;
5. reuse existing pair-derived validation such as exhaustive VCF REF and
   coordinate-bounds evidence rather than implementing UCSC-specific copies.

A profile must not suppress or rewrite a core-format requirement simply because
UCSC accepts another name. Existing content contradictions retain precedence.
For example, reassuring UCSC metadata or an alias cannot erase a VCF REF
mismatch, BAM M5 contradiction, embedded GFF3 sequence contradiction, or other
directly comparable hard evidence.

Slice 4 introduces the smallest generic extension needed for that composition.
`SequenceBindingRequirement` asks whether one resource-local sequence has an
explicit evidence-backed relationship to the selected anchor; matching strings
alone cannot satisfy it. An anchor-owned `SequenceBindingValidationCapability`
records a conclusive `BOUND`, exhaustively `PROVEN_ABSENT`, or independently
established `CONTENT_CONFLICT` pair result. The conflict state is used only when
peer identity already binds the local name to a different anchor target than the
content-bound UCSC target; unresolved provider/name/target relationships still
contribute no capability.
`SequenceBindingMethod.AUTHORITATIVE_NAME` records the naming path without
pretending that the provider target identity is peer-owned content identity.
The identity values and anchor capability IDs on that binding authenticate the
provider-target-to-anchor content leg, while the profile-specific projection
retains the UCSC naming and provider-source trace. Generic bundle reasoning
rechecks that the authoritative binding's identity trace uniquely resolves on
the complete FASTA anchor and requires exactly one matching `BOUND` pair
validation before the supplemental binding may affect ordinary core checks. The
existing `VERIFIED_SEQUENCE_IDENTITY` path and its full-anchor rules are
unchanged.

Slice 5 extends that reuse into BAM/CRAM dictionary interpretation. After generic
bundle reasoning has validated a profile-supplied `AUTHORITATIVE_NAME` binding,
the alignment relationship classifier may consume the completed bundle result and
record the cross-name relationship as an authoritative-name binding rather than
re-deriving or pretending it is M5 evidence. Membership and order can therefore be
described using the verified relationship while the independent M5-content
dimension remains `UNRESOLVED` when the SAM header does not declare comparable
M5. A direct M5 disagreement remains a content conflict.

CRAM offline-reference planning may carry that richer relationship trace when a
completed bundle result is supplied, but it still authorizes the selected FASTA
for future reference-dependent decoding only under the pre-existing strict rule:
exact primary names, complete matching M5, acceptable membership, matching
lengths, and a readable selected anchor. A profile-compatible authoritative alias
therefore does not imply that HTSlib can safely address a differently named FASTA.

The profile adds one binding requirement for each peer sequence already required
by a core presence requirement. A provider target proven absent by exhaustive
comparable anchor identity yields a hard negative validation, while a conflicting
independently established peer identity yields a hard binding contradiction. When
peer identity evidence exists but cannot establish one binding because it conflicts
internally, directly disagrees with the proposed anchor target under a comparable
scheme, or positively matches another sequence anywhere in the complete anchor,
provider naming is not allowed to manufacture an authoritative binding. That case
remains unresolved unless an existing core requirement independently proves a hard
conflict. Incomplete or otherwise ambiguous evidence likewise yields no validation
and therefore an unresolved mandatory profile requirement. This prevents exact-name
core presence, matching length, or even successful format-specific checks from
rescuing a missing or contradicted mandatory UCSC target bridge.

## Verdict semantics

The existing categorical aggregation rules remain authoritative.

### `COMPATIBLE`

A UCSC-preflight result may be `COMPATIBLE` only when every mandatory in-scope
core and profile requirement is satisfied and no unresolved mandatory provider
or target relationship could change the conclusion. In particular, matching
provider names/lengths plus aliases cannot produce this verdict without the
required FASTA-to-UCSC target-content bridge.

### `COMPATIBLE_WITH_CONDITIONS`

Conditions may qualify a positive result only for scope the caller explicitly
selected. They do not rescue missing mandatory UCSC target identity. An
unresolved mandatory target relationship remains `INDETERMINATE` rather than
being reframed as a positive result with a caveat.

### `INCOMPATIBLE`

A hard in-scope contradiction remains `INCOMPATIBLE`, including exhaustive
comparable anchor identity proving that required UCSC target sequence content is
absent. A mismatch against only the same-named anchor sequence is not sufficient
when another anchor sequence could still match. Provider acquisition failure,
alias absence, stale age alone, or ambiguous metadata is not a hard biological
contradiction.

### `INDETERMINATE`

The result is `INDETERMINATE` when no hard contradiction is proven but a
mandatory UCSC relationship cannot be established, including missing target
identity, ambiguous alias mapping, incomplete provider evidence, or unavailable
provider enrichment needed for the requested profile conclusion.

## VCF, BAM/CRAM, and annotation reuse

Once a resource-local sequence name has an exact or evidence-backed projection
to a content-bound UCSC target/FASTA sequence, existing format semantics remain
in force.

For VCF, exhaustive REF comparison remains the record-level content check. The
profile does not invent a second UCSC REF validator. The first Slice 4
end-to-end path derives an authoritative-name binding only after the UCSC target
is content-bound, supplies that binding to the existing exhaustive REF evaluator,
projects the resulting reference-base capability normally, and sends the
profile-augmented contract plus pair validations through the ordinary bundle and
verdict reasoners. A matching VCF REF check cannot rescue a missing mandatory
UCSC target identity; the profile binding requirement remains unresolved and the
whole result remains `INDETERMINATE`.

For BAM/CRAM, existing dictionary presence, length, M5, ordering, relationship,
and offline-reference semantics remain distinct. A UCSC alias cannot turn
missing M5 into content verification or erase an M5/length contradiction.

For GTF/GFF3, Milestone 5 sparse-coordinate, embedded-content, and circular
contracts remain unchanged. M6 does not add an annotation-specific UCSC path;
the generic binding model can support such composition later without changing
annotation coordinate semantics.

## Online, offline, freshness, and reproducibility

Scientific reasoning operates on the provider snapshot, not on live HTTP state. Slice 6 adds a strict versioned JSON artifact boundary for an already-materialized snapshot. The renderer canonicalizes provider-fact ordering and normalizes acquisition timestamps to UTC for reproducible bytes; the loader rejects unknown/duplicate fields, re-runs all immutable snapshot invariants, and may verify an expected exact-file SHA-256 before parsing. This is deliberately not a network client or persistent cache. A live acquisition adapter, if later added, must finish by producing the same immutable snapshot model.

If acquisition produces no usable snapshot at all, `project_ucsc_preflight` accepts provider evidence as unavailable. It still projects the mandatory `SequenceBindingRequirement` values but emits no provider-authorized binding or pair-validation capability. The corresponding requirements therefore remain unresolved and can make an otherwise positive evaluation `INDETERMINATE`; provider unavailability itself contributes no negative biological evidence.

Therefore:

- the same snapshot must yield the same compatibility result online or offline;
- a live fetch, if implemented, must finish by materializing the snapshot before
  compatibility reasoning begins;
- network timeout/unavailability contributes no negative biological evidence;
- the ordinary test/quality gate uses frozen redistributable provider fixtures;
- live provider smoke tests, if present, are separate from the authoritative
  deterministic gate;
- provider source locations and acquisition/freshness metadata remain retained on
  the snapshot/profile trace for later diagnostics or reporting; the current
  generic diagnostics do not yet render UCSC-specific provider provenance;
- age alone does not invalidate a snapshot unless a later explicit freshness
  policy requires it;
- a newly changed UCSC source may legitimately produce a different *new*
  snapshot, but that change must not be silently mixed into an existing one.

UCSC's current distribution layout makes this boundary important. For example,
the `hg38` top-level `bigZips` page distinguishes the initial GRCh38 files from
newer patch-inclusive Browser content and exposes a separate `latest/` target.
RefCompat must identify exactly which provider context supplied its facts rather
than assuming every path containing `hg38` describes an interchangeable
sequence collection.

## Adversarial requirements

Milestone 6 tests must prove both sufficient and insufficient evidence. At
minimum they should cover:

- explicit target selection versus guessed database names;
- exact UCSC name with verified target content;
- exact UCSC name with same length but different content while another anchor
  sequence matches the required UCSC target;
- exhaustive comparable anchor identity proving the required UCSC target content
  absent;
- authoritative cross-name alias with verified target content;
- familiar `1`/`chr1`-style resemblance with no provider alias evidence;
- ambiguous alias mappings;
- alias evidence from the wrong database;
- incomplete alias data or complete alias rows over an incomplete canonical
  catalog;
- missing provider target identity;
- duplicate target content in the complete FASTA anchor;
- distinct required UCSC canonical targets with identical content attempting to
  collapse onto one FASTA coordinate axis;
- an otherwise unique target hidden outside explicit scope;
- provider support contradicted by stronger VCF/BAM/content evidence;
- network/provider unavailability producing unresolved evidence rather than
  incompatibility;
- a fixed snapshot yielding the same result whether loaded from a frozen file or supplied as the same already-materialized provider document;
- complete provider unavailability yielding unresolved profile requirements rather than incompatibility;
- mixed hard contradiction plus unrelated unresolved provider evidence;
- a negative control where reference compatibility passes but UCSC hosting or
  hub configuration would still fail for a non-reference reason.

Slice 7 implements this matrix in `tests/integration/test_milestone6_exit.py` with
only synthetic or already-frozen Milestone 6 fixtures. The suite also pins the
positive side of explicit scope: after full-anchor uniqueness is established, an
otherwise-positive explicitly scoped evaluation may become
`COMPATIBLE_WITH_CONDITIONS`; scope never converts an ambiguous or hidden target
into a positive relationship. The invalid-hub control deliberately remains
outside RefCompat parsing and verifies only that a positive reference verdict is
not a claim of structural hub validity. Dedicated VCF, BAM/CRAM, and offline
integration tests remain the format-level proof paths and are not replaced by
this cross-cutting exit matrix.

## Review checkpoints

The first internal scientific/code review occurred after:

1. the provider snapshot model exists;
2. authoritative-alias semantics are implemented;
3. the FASTA-to-UCSC target-content bridge is enforced; and
4. one representative end-to-end profile path exercises those semantics through
   the normal bundle reasoner.

That checkpoint is complete. It found and corrected a false-positive path where
conflicting/non-bindable peer identity could be overridden by provider naming,
and a deterministic validation-ID defect that omitted provider context. Broader
profile integration may now proceed from the hardened relationship boundary.

The full M6 adversarial suite is implemented. The final internal milestone review
found and corrected two additional false-positive paths: alternate aliases could
be authorized from complete alias rows over an incomplete canonical catalog, and
distinct required UCSC canonical targets with identical content could collapse
onto one FASTA coordinate sequence. The hardened profile now requires complete
canonical-plus-alias naming context for alternate aliases and withholds positive
profile authorization when distinct required canonical targets collapse onto one
anchor sequence, while preserving advisory isolation, hard peer-content conflicts,
and multiple aliases of one canonical target. The required external milestone-boundary review is now complete. It found no
MAJOR issue and assessed the repository SAFE TO BEGIN M7. Its one MINOR finding
identified an unpinned fail-loud BAM/CRAM classifier invariant; the follow-up test
now locks that internal contract before M7.

## Primary UCSC references

- UCSC custom-track FAQ, including supported non-UCSC chromosome names and
  `chromAlias` discovery:
  https://genome.ucsc.edu/FAQ/FAQcustom
- UCSC Assembly Hub User Guide, `chromAlias.txt` format and authority columns:
  https://genome.ucsc.edu/goldenPath/help/assemblyHubHelp.html
- UCSC REST API, including UCSC-genome, chromosome, and sequence endpoints:
  https://genome.ucsc.edu/goldenpath/help/api.html
- UCSC `hg38` bigZips index, including initial-versus-patch/latest distinctions:
  https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/
- UCSC Track Hub User Guide and `hubCheck` guidance:
  https://genome.ucsc.edu/goldenPath/help/hgTrackHubHelp
