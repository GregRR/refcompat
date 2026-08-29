# GTF/GFF3 annotation coordinate compatibility

**Status:** Milestone 5 implementation and exit coverage complete; external review pending.

RCHECK-060 asks a directional question: can the reference-coordinate statements
made by this annotation be represented against the explicitly selected FASTA
anchor? Annotation files do not vote on which reference should be the anchor,
and RefCompat does not repair or normalize them to obtain a positive answer.

The normative check contract remains in
[`check-specifications.md`](check-specifications.md). This note records the
standards-derived invariants that should remain visible while Milestone 5 is
implemented.

The streaming observation boundary, format-neutral coordinate-bounds reasoning layer, ordinary annotation-to-FASTA validation, GFF3 sequence-region/provenance handling, embedded-FASTA identity/binding, landmark-aware circular-origin reasoning, and integration/adversarial exit suite are now implemented. Feature rows remain iterable in file order while compact snapshots retain per-seqid summaries and small reference-relevant GFF3/GTF metadata. Feature-used seqids plus any sequence-region-only seqids create mandatory presence requirements. Feature intervals and declared GFF3 regions project together through one anchor-owned coordinate capability, while relevant embedded GFF3 FASTA sequences can add content-derived identity requirements/capabilities and verified cross-name bindings. Independently established annotation-owned content identities may also be supplied solely as conservative binding evidence, which lets GTF participate in verified cross-name resolution without inventing identity from the GTF itself. External milestone-boundary review remains before Milestone 6.

## Native coordinate model

Supported GTF and GFF3 feature coordinates are positive one-based closed
intervals. RefCompat preserves native `start` and `end` values in annotation
observations. Any conversion required to query FASTA bases or lengths belongs
in the pair-validation layer and must be explicit.

For an ordinary resolved feature, representability requires:

```text
1 <= start <= end <= anchor sequence length
```

GFF3's defined circular-origin representation is the exception described below.

GFF3 seqids use the format's percent-encoding rules. RefCompat should preserve
the raw field for traceability while comparing the decoded logical identifier
to the FASTA namespace and to `##sequence-region` seqids. Characters allowed
unescaped by the GFF3 seqid grammar must remain unescaped rather than being
percent-encoded. When circular reasoning compares a landmark feature `ID` with
the logical seqid, the `ID` is decoded under GFF3 column-9 escaping rules:
reserved characters must be escaped, while characters that do not require
escaping must not be percent-encoded. Invalid, missing, or disallowed escaping
is malformed input; it is not an invitation to guess a name.

Coordinates carried by the GFF3 `Target` attribute belong to the aligned target
sequence rather than the column-1 landmark. They are not anchor-coordinate
requirements for RCHECK-060.

## Sparse resources and seqid resolution

An annotation normally exposes only sequences on which it carries features.
That used set is not a complete biological reference dictionary. Extra FASTA
sequences therefore do not create a conflict merely because the annotation does
not mention them.

Every used seqid creates a directional requirement on the anchor. Resolution
may use:

1. the same local sequence name; or
2. an explicit verified `SequenceBinding`.

No naming convention is itself a binding. In particular, RefCompat does not
infer `1` ↔ `chr1`, `MT` ↔ `chrM`, accession-version stripping, or other
plausible aliases from string form. GFF3 `Alias` attributes are feature aliases,
not authority to bind the column-1 seqid to an anchor sequence. If a used local
name cannot be resolved, its coordinate statements remain unresolved. They are
not called out of bounds because no anchor coordinate system has yet been
established for them, and the name difference alone does not prove biological
absence.

## Scalable coordinate evidence

Milestone 5 does not expand a large annotation into one generic requirement
object per feature. The annotation-specific validation result retains exhaustive per-seqid counts
plus the first representative local check for each non-match category on each
seqid, while generic bundle reasoning uses one resource-level
`CoordinateBoundsRequirement` and one anchor-owned
`CoordinateBoundsValidationCapability` for the exhaustive in-scope coordinate
set. For GFF3 that set includes both feature rows and `##sequence-region`
declarations while retaining their counts separately in annotation-specific
results. This keeps memory bounded by seqid/outcome categories plus declared
regions rather than by the number of problematic feature rows.

This mirrors the existing VCF direct-validation bridge: pair-derived evidence
can satisfy only the requirement for the same subject resource and selected
FASTA anchor. Peer resources never provide candidate anchor facts.

The generic coordinate-bounds requirement/capability, evaluation, evidence, finding, and bundle-supplemental machinery is implemented independently of annotation policy. Annotation coordinate validation resolves a local seqid either exactly or through an explicit verified `SequenceBinding`; no heuristic alias path exists. A proven ordinary out-of-bounds feature projects as a hard Tier-B structural conflict, while a local name without exact or verified resolution remains unresolved and a sparse annotation can be structurally compatible with a FASTA superset. The number of in-bounds features is descriptive and cannot cancel a conflict. Valid circular-origin features are counted separately in annotation-specific results but contribute to the generic representable coordinate total. Ambiguous landmark interpretation remains unresolved rather than being averaged into a positive conclusion.

## GFF3 `##sequence-region`

The Sequence Ontology GFF3 specification defines `##sequence-region seqid start
end` as the sequence segment referred to by the file. The directive may cover a
partial segment, so its `end` value is not automatically the length of the full
biological sequence and must not become an exact `SequenceLengthRequirement`.

Only one `##sequence-region` declaration is accepted for each decoded/logical
seqid. A directive also creates a sequence-presence requirement even when that
seqid has no feature rows, because the directive itself is a reference-coordinate
statement. When its seqid resolves, the declared segment is checked for
representability against the anchor and contributes to the same aggregate
coordinate-bounds capability as feature rows. An unfamiliar region seqid remains
unresolved rather than being guessed.

Separately, GFF3 requires features on a landmark with a supplied
`##sequence-region` to stay within that region unless the standard
circular-landmark exception applies. Ordinary self-contradiction stops
coordinate evaluation as invalid annotation input rather than producing a
biological `INCOMPATIBLE` verdict. The exception now applies only when the file
contains the exact logical circular landmark and the affected feature is a valid
single-wrap circular-origin encoding; an unrelated circular child feature does
not excuse a region violation.

## GFF3 circular-origin features

GFF3 requires ordinary start/end coordinates to satisfy `start <= end`. For a
feature crossing the origin of a circular landmark, the specification encodes
the wrapped end by adding the landmark length. A valid feature can therefore
have an encoded `end` greater than the anchor sequence length.

RefCompat applies this exception narrowly. A circular landmark candidate is
observed only when a feature carries `Is_circular=true` and its decoded `ID`
exactly equals the logical column-1 seqid. A wrap is proven only when exactly
one such candidate exists, the candidate begins at coordinate 1, its end (the
landmark length) equals the resolved anchor sequence length, and an extended
feature satisfies `1 <= end - landmark_length < start <= landmark_length`.
Such a feature is recorded as circular-representable and contributes positive
Tier-B coordinate evidence. If the exact landmark relationship exists but its
length cannot be reconciled with the selected anchor, the wrap remains
unresolved rather than being accepted on numeric coincidence. Multiple or
non-origin landmark candidates likewise do not manufacture compatibility.

An `Is_circular=true` attribute on some other feature is not landmark evidence
and does not suppress an ordinary out-of-bounds conflict. Coordinates that
would require more than one wrap, or that begin beyond the landmark before
wrapping, are invalid input rather than valid circular coordinates. Organism
type, a familiar sequence name, or an apparently plausible wraparound pattern
is never enough.

The supported GTF/GFF2-derived coordinate model has no corresponding core
circular-origin rule; ordinary GTF intervals therefore use the normal resolved
sequence bounds check.

## Provenance claims and embedded FASTA

Assembly names, assembly accessions, provider/release comments, species labels,
and similar metadata remain provenance claims. The implemented contract ignores
those claims when building presence/coordinate requirements and capabilities, so
changing a claim such as `##genome-build` cannot change compatibility by itself.
Claims may be reported and may help a user diagnose a problem, but they do not
become content-derived sequence identity or prove aliases.

GFF3 `##FASTA` is different from metadata because it begins actual embedded
sequence content. The streaming parser recognizes that boundary so FASTA lines
are never parsed as annotation features; the GFF3 backward-compatibility rule
that a line beginning with `>` implies the FASTA section is handled at the same
boundary. Embedded sequence bases are summarized without materializing complete
sequences in memory. MD5 identity uses the refget checksum normalization:
non-sequence formatting is removed, letters are uppercased, and the normalized
sequence is hashed. Embedded records with no normalized sequence content are invalid.
Legacy semicolon-comment syntax is rejected rather than risking comment text being
normalized into sequence identity.

An embedded sequence contributes identity only when its FASTA identifier exactly
matches a feature-used or `##sequence-region` logical annotation seqid. Extra
bundled target/protein sequences do not become RCHECK-060 reference evidence,
and FASTA header resemblance to an external anchor name is never treated as an
alias. Relevant embedded identities are `CONTENT_DERIVED` evidence owned by the
annotation resource. They become mandatory sequence-identity requirements and
may establish a cross-name `SequenceBinding` only through the existing complete-
anchor identity reasoner. The matching identity scheme must be available for
every sequence in the complete anchor before uniqueness can be claimed; missing
anchor identity, duplicate identity, or explicit scope cannot manufacture a
binding. Annotation projection independently derives the expected bindings and
rejects stale coordinate validation that did not use exactly those bindings.
The verified binding is then used consistently for presence, identity, feature
bounds, and sequence-region bounds.

When a relevant embedded FASTA identifier exactly matches a logical annotation
seqid, its normalized sequence length also constrains the GFF3 document itself.
An ordinary feature or `##sequence-region` extending beyond that embedded
sequence is invalid annotation input, not evidence that the selected external
FASTA is incompatible. A feature may extend beyond matching embedded sequence
length only when the exact landmark-aware single-wrap rule is proven; ambiguous
landmark evidence remains unresolved.

Because embedded bases are actual content, an exact-name identity contradiction
against the selected FASTA is Tier-A evidence and can make the bundle
`INCOMPATIBLE`. Matching embedded content or a verified cross-name binding can
support compatibility, but embedded content never selects, replaces, or
outranks the explicitly supplied FASTA anchor. Exact-name coordinate
compatibility does not require embedded sequence and does not prove which named
genome build produced the annotation.

## Deliberate non-goals

Milestone 5 does not:

- validate gene/transcript/exon biological correctness;
- repair `ID`/`Parent` hierarchy or attributes;
- perform general GFF3/GTF conformance validation beyond syntax needed for the
  compatibility check;
- infer aliases or genome builds from familiar strings;
- convert GTF and GFF3;
- clip, lift, rename, delete, or rewrite features;
- enforce consumer-specific annotation dialect requirements.

Those concerns belong to dedicated validators, later transformations, or
explicit consumer profiles.

## Standards and ecosystem references

- Sequence Ontology GFF3 specification: https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
- Ensembl GFF/GTF format documentation: https://www.ensembl.org/info/website/upload/gff.html
- GENCODE GTF format documentation: https://www.gencodegenes.org/pages/data_format.html
- NCBI GFF3 format notes: https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/file-formats/annotation-files/about-ncbi-gff3/
