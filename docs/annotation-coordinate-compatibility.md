# GTF/GFF3 annotation coordinate compatibility

**Status:** Milestone 5 implementation in progress; ordinary exact-name bounds path complete.

RCHECK-060 asks a directional question: can the reference-coordinate statements
made by this annotation be represented against the explicitly selected FASTA
anchor? Annotation files do not vote on which reference should be the anchor,
and RefCompat does not repair or normalize them to obtain a positive answer.

The normative check contract remains in
[`check-specifications.md`](check-specifications.md). This note records the
standards-derived invariants that should remain visible while Milestone 5 is
implemented.

The streaming observation boundary, format-neutral coordinate-bounds reasoning layer, and ordinary exact-name annotation-to-FASTA validation path are now implemented. Feature rows remain iterable in file order while compact snapshots retain per-seqid summaries and small reference-relevant GFF3/GTF metadata. Used seqids create mandatory presence requirements, exhaustive feature bounds project through one anchor-owned coordinate capability, and normal bundle reasoning reaches compatible, incompatible, or indeterminate outcomes without creating one generic requirement per feature. Verified cross-name binding and GFF3-specific sequence-region, embedded-FASTA identity, and circular-origin semantics remain later slices.

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
percent-encoded. Invalid, missing, or disallowed escaping is malformed input;
it is not an invitation to guess a name.

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
`CoordinateBoundsValidationCapability` for the exhaustive in-scope feature set.
This keeps memory bounded by seqid/outcome categories rather than by the number
of problematic feature rows.

This mirrors the existing VCF direct-validation bridge: pair-derived evidence
can satisfy only the requirement for the same subject resource and selected
FASTA anchor. Peer resources never provide candidate anchor facts.

The generic coordinate-bounds requirement/capability, evaluation, evidence, finding, and bundle-supplemental machinery is implemented independently of annotation policy. The ordinary exact-name annotation validator is now connected to that bridge: a proven ordinary out-of-bounds feature projects as a hard Tier-B structural conflict, while an unfamiliar seqid remains unresolved and a sparse annotation can be structurally compatible with a FASTA superset. The number of in-bounds features is descriptive and cannot cancel a conflict. An unresolved feature count likewise remains unresolved rather than being averaged into a positive conclusion. Until the dedicated circular slice establishes the GFF3 exception, an otherwise out-of-bounds feature on a seqid with observed circular evidence is conservatively counted as unresolved rather than contradicted.

## GFF3 `##sequence-region`

The Sequence Ontology GFF3 specification defines `##sequence-region seqid start
end` as the sequence segment referred to by the file. The directive may cover a
partial segment, so its `end` value is not automatically the length of the full
biological sequence and must not become an exact `SequenceLengthRequirement`.

When its seqid resolves, the declared segment can be checked for
representability against the anchor. Separately, GFF3 requires features on a
landmark with a supplied `##sequence-region` to stay within that region unless
the standard circular-landmark exception applies. A file that contradicts its
own required region semantics is malformed input; input validity must remain
separate from a biological incompatibility verdict.

## GFF3 circular-origin features

GFF3 requires ordinary start/end coordinates to satisfy `start <= end`. For a
feature crossing the origin of a circular landmark, the specification encodes
the wrapped end by adding the landmark length. A valid feature can therefore
have an encoded `end` greater than the anchor sequence length.

RefCompat must apply this exception narrowly. The GFF3 document must supply the
standard landmark evidence establishing the relevant feature as circular, and
the extended coordinates must be valid under the defined representation.
Organism type, a familiar sequence name, or an apparently plausible wraparound
pattern is not enough. When the exception cannot be established safely, the
relationship remains unresolved rather than being declared compatible or
incompatible on a guessed interpretation.

The supported GTF/GFF2-derived coordinate model has no corresponding core
circular-origin rule; ordinary GTF intervals therefore use the normal resolved
sequence bounds check.

## Provenance claims and embedded FASTA

Assembly names, assembly accessions, provider/release comments, species labels,
and similar metadata remain provenance claims. They may be reported and may
help a user diagnose a problem, but they do not become content-derived sequence
identity or prove aliases.

GFF3 `##FASTA` is different from metadata because it begins actual embedded
sequence content. The streaming parser must recognize that boundary so FASTA
lines are never parsed as annotation features. The GFF3 backward-compatibility
rule that a line beginning with `>` implies the FASTA section belongs at this
same parser boundary. When RefCompat derives sequence identity from embedded
bases for binding evidence, that identity is `CONTENT_DERIVED` evidence owned by
the annotation resource and remains subject to the existing full-anchor
uniqueness safeguards. It never selects, replaces, or outranks the explicitly
supplied FASTA anchor.

Exact-name coordinate compatibility does not require an annotation to contain
embedded sequence and does not prove which named genome build produced it.

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
