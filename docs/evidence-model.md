
# RefCompat evidence model

RefCompat's usefulness depends less on producing a label than on showing why that label is justified.

## Evidence is not the same as an observation

An observation is a fact extracted from one resource:

```text
A: chr1 length = 248956422
B: 1    length = 248956422
```

Evidence relates one or more observations to a compatibility question:

```text
The lengths agree.
```

or:

```text
Content-derived sequence identities establish that A:chr1 and B:1 denote the same sequence.
```

The second is much stronger evidence than the first.

## Evidence object

Milestone 1 implements the stable qualitative `EvidenceStrength` and `EvidencePolarity` vocabulary used by the identity/derived-artifact results. Milestone 2 now adds a generalized immutable `Evidence` object plus `EvidenceAggregate`. Evidence items carry deterministic opaque IDs, scientific kind, derivation method, qualitative strength and polarity, the constraint/requirement/capability IDs involved, and any source observation IDs already attached to the capability.

The current generalized evidence object deliberately does not include an external-standard/tool reference field before a concrete producer needs one. That metadata can be added when standards-backed claim/evidence producers exist rather than as an unused placeholder.

Capabilities may carry zero or more source observation IDs. An empty tuple is a transitional traceability gap, not proof that no source observation exists; existing Milestone 1 inspectors have not yet been converted into generalized contract producers.


## Qualitative aggregation

`EvidenceAggregate` retains individual evidence rather than collapsing it into a score. It separately exposes supporting evidence, contradicting evidence, and Tier-A conclusive contradictions while retaining unresolved/not-applicable constraint IDs.

An unresolved constraint may still carry evidence when candidate capabilities disagree. The aggregate preserves both sides of that disagreement rather than selecting a winner. Counts of weaker support do not cancel a Tier-A contradiction. Whole-bundle interpretation remains a later layer.

Evidence IDs derived by the exact typed evaluator are deterministic opaque SHA-256-based identifiers over the constraint/requirement/capability relationship and its qualitative classification. They are not scientific digests and must not be parsed for semantic meaning.

## Evidence hierarchy

### Tier A — conclusive content evidence

Examples:

- GA4GH refget sequence identity;
- applicable SeqCol identity/relationship;
- SAM `M5` content checksum when correctly comparable;
- direct FASTA base comparison;
- exhaustive VCF REF disagreement with the anchor FASTA.

A Tier A contradiction is a hard conflict for the affected scope.

### Tier B — direct structural/content consistency

Examples:

- matching sequence name and length when exact digest is unavailable;
- `.fai` structural correspondence with the FASTA;
- `.dict` name/length consistency;
- GTF/GFF seqids resolved and coordinates in bounds;
- exact accession plus independently matching structural properties.

Tier B evidence can establish many operational constraints, but must not be described as exact sequence identity unless it actually proves content identity.

### Tier C — provenance and metadata

Examples:

- VCF `##reference`;
- assembly/provider/release metadata;
- BAM `AS`, `UR`, `SP`, or program records;
- source URL;
- workflow/pipeline configuration.

These can strongly support interpretation and are critical for bundle diagnosis, but content-derived identity governs when they conflict.

### Tier D — heuristic/contextual evidence

Examples:

- filename contains `hg38`;
- familiar chromosome naming style;
- coordinate values happen to fit a known build;
- pattern resembles a common build transition.

Tier D evidence may guide explanation or a next diagnostic action. It must not be promoted to verification.

## Conflict rules

### Hard contradiction veto

For the affected scope, a conclusive contradiction cannot be averaged away by many weaker matches.

Example:

```text
999,999 VCF records match the FASTA
1 VCF REF allele is proven not to match
```

The mismatching record is still a hard local incompatibility. The mismatch rate helps interpret likely cause; it does not erase the known contradiction.

### Absence of evidence is not incompatibility

A sparse annotation or VCF may expose only a subset of its underlying reference. Lack of an observed sequence does not prove that the reference lacks the sequence.

When an in-scope mandatory relationship cannot be established and no hard conflict is shown, the appropriate state is normally `UNRESOLVED` and the aggregate result may be `INDETERMINATE`.

### Local conflict need not invalidate unrelated scope

A mitochondrial sequence conflict should be reported as mitochondrial evidence. It does not authorize an unsupported claim that all autosomal sequences conflict.

The top-level verdict still depends on whether the affected requirement is mandatory for the requested evaluation scope.

### Sampling weakens a claim

Authoritative v0.1 VCF REF checking is exhaustive. If future performance modes permit sampling, the report must distinguish sampled absence-of-conflict from exhaustive agreement and must not make the same strength of claim.

### Metadata conflict remains visible

If content-derived identity proves collection X while metadata says collection Y:

- use content evidence for identity reasoning;
- retain the metadata statement as a provenance claim;
- mark the claim contradicted;
- report the contradiction prominently.

Do not silently normalize the metadata away.

## Alias evidence

Sequence-name resolution is shared infrastructure, not a string-rewrite table.

Evidence preference, strongest first:

1. common content-derived refget sequence identity;
2. compatible content checksum semantics such as independently matched M5 where valid;
3. standardized or authoritative alias declaration tied to a specific sequence;
4. assembly-report/authority alias relationship;
5. name resemblance.

Only adequate evidence can produce a verified alias/binding. `chr1` and `1` are not declared equivalent merely because the transformation is familiar.

## Provenance claims and assessments

Claims remain immutable. Later evidence produces assessments:

- `SUPPORTED`
- `VERIFIED`
- `CONTRADICTED`
- `UNRESOLVED`

This prevents RefCompat from rewriting history when a collaborator note or embedded metadata turns out to be wrong.

## Negative controls

RefCompat must support findings equivalent to:

> No reference-coordinate incompatibility was demonstrated by the available evidence.

The incident corpus contains many cases where the eventual cause was strandedness, resource limits, malformed input, software behavior, or another non-reference issue. A deterministic compatibility tool should narrow diagnosis, not force every failure into its own problem category.

## Traceability invariant

Every user-visible compatibility conclusion should be explainable as:

```text
Finding / condition
    -> constraint evaluation(s)
        -> evidence item(s)
            -> observation(s) and/or immutable claim(s)
                -> resource + source location
```

A report that cannot provide that trace should not claim a stronger conclusion than its model can justify.

The third Milestone 2 slice now materializes the first structured `CompatibilityFinding` and `CompatibilityCondition` objects. Conflict findings cite concrete evidence IDs; unresolved findings may legitimately cite none when evidence is absent. Scope conditions are derived only from explicit `EvaluationRequest` resource/anchor-sequence scope and do not themselves assert a compatibility verdict.
