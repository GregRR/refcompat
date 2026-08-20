
# RefCompat

**RefCompat** is a planned open-source Python tool for determining whether heterogeneous genomic resources can share a coherent reference-coordinate context for a stated use case, and for explaining the evidence, conflicts, conditions, and unresolved questions behind that conclusion.

The project is currently in **early development** and should not yet be treated as production software.

## The problem

Genomic workflows commonly combine files that appear to belong to the same reference but differ in ways that matter operationally:

- assembly or reference-distribution differences such as GRCh37, hg19, b37, or hs37d5;
- `chr1` versus `1` and other sequence-name namespaces;
- primary-only references versus ALT/decoy/patch-inclusive distributions;
- stale `.fai` or sequence-dictionary artifacts;
- VCF REF alleles that do not match the supplied FASTA;
- BAM/CRAM sequence dictionaries that do not reconcile with the intended reference;
- GTF/GFF annotations that require missing sequences or exceed sequence bounds;
- bundles whose files carry inconsistent provenance or were generated from different reference assets.

Existing tools solve important parts of this problem. RefCompat is intended to provide the reasoning layer above those parts: inspect a collection of resources, represent what each resource requires and provides, evaluate the constraints against a coherent reference context, and produce a scoped, traceable verdict.

## Core position

RefCompat does **not** define genomic sequence identity.

- Individual sequence identity is delegated to **GA4GH refget Sequences**.
- Sequence-collection identity and comparison are delegated to **GA4GH Refget Sequence Collections (SeqCol)**.
- RefCompat consumes those standardized identities and relationships as evidence for higher-level interoperability reasoning.

Conceptually:

```text
refget Sequences
"What exact sequence is this?"
        |
        v
SeqCol
"What exact collection is this?"
"How do collections relate?"
        |
        v
RefCompat
"Are the requirements of these heterogeneous resources jointly
satisfied for the stated reference-coordinate use case?"
```

## Compatibility model

Compatibility is treated as **constraint satisfaction, not similarity**.

RefCompat is being designed around these principles:

- strong content evidence cannot be overridden by many weak similarities;
- compatibility can be directional: one resource may require a subset of what another provides;
- a result is always scoped to a stated evaluation context;
- `INDETERMINATE` is a first-class result when evidence is insufficient;
- input/analysis status is separate from compatibility status;
- provenance claims remain distinguishable from verified identity;
- conditions must come from explicit scope or profile rules, not from RefCompat guessing what the user considers irrelevant;
- no silent scientific repair or semantic transformation.

Implemented top-level verdicts are:

- `COMPATIBLE`
- `COMPATIBLE_WITH_CONDITIONS`
- `INCOMPATIBLE`
- `INDETERMINATE`

Planned analysis status remains separate from compatibility verdicts: `COMPLETE`, `PARTIAL`, or `INVALID_INPUT`.

## Research basis

The current design was informed by a purposively collected and reviewed corpus of **200 real compatibility-related incidents** from public genomics support forums and issue trackers. Two independent 100-case batches were used to test whether the problem taxonomy and proposed feature priorities remained stable under a different source mix.

The corpus is design evidence, **not a prevalence study**. The row-level incident records are not distributed with RefCompat; validation uses small synthetic or clearly redistributable fixtures derived from observed failure patterns.

## Planned first substantial release

The initial implementation scope is intentionally narrow:

- FASTA inspection and local refget/SeqCol identity;
- FASTA ↔ `.fai` integrity;
- FASTA ↔ SAM/Picard-style `.dict` integrity;
- FASTA ↔ BAM/CRAM reference-context checks;
- VCF header/reference-context checks (implemented);
- exhaustive VCF REF ↔ FASTA verification;
- GTF/GFF3 sequence-name and coordinate-bounds checks;
- whole-bundle compatibility reasoning;
- verified alias handling as shared evidence infrastructure;
- human-readable and machine-readable reports.

BED, liftover, broad workflow validation, automatic repair, and complex ecosystem profiles are intentionally deferred.

## Design documents

Start with:

- [`DESIGN.md`](DESIGN.md) — current design baseline;
- [`ROADMAP.md`](ROADMAP.md) — implementation milestones and scope boundaries;
- [`docs/compatibility-model.md`](docs/compatibility-model.md) — formal domain model;
- [`docs/evidence-model.md`](docs/evidence-model.md) — evidence hierarchy and provenance rules;
- [`docs/refget-seqcol-integration.md`](docs/refget-seqcol-integration.md) — standards/integration boundary;
- [`docs/check-specifications.md`](docs/check-specifications.md) — explicit v0.1 check contracts;
- [`docs/fasta-index-integrity.md`](docs/fasta-index-integrity.md) — exact FASTA/`.fai` derived-artifact semantics;
- [`docs/sequence-dictionary-integrity.md`](docs/sequence-dictionary-integrity.md) — FASTA/`.dict` structure, M5, alias, and provenance semantics;
- [`docs/diagnostic-output.md`](docs/diagnostic-output.md) — provisional human/JSON output for the Milestone 1 identity and integrity slice;
- [`docs/reasoning-foundation.md`](docs/reasoning-foundation.md) — typed Milestone 2 request, contract, and constraint/evaluation boundary;
- [`docs/evidence-aggregation.md`](docs/evidence-aggregation.md) — qualitative, traceable Milestone 2 evidence derivation and aggregation;
- [`docs/findings-conditions.md`](docs/findings-conditions.md) — structured Milestone 2 issue/unresolved findings and explicit-scope conditions;
- [`docs/reference-context-bundle.md`](docs/reference-context-bundle.md) — FASTA-anchored reference context, verified sequence bindings, and whole-bundle orchestration;
- [`docs/verdict-aggregation.md`](docs/verdict-aggregation.md) — categorical mandatory-constraint verdict aggregation without numeric scoring;
- [`docs/adr/`](docs/adr/) — architectural decisions.

## Project status

Milestone 1 and the Milestone 2 reasoning foundation are complete, and Milestone 3 VCF observation work has begun. RefCompat now has explicit anchor-driven evaluation requests/scope, typed sequence presence/length/identity/order requirements and capabilities, separate compatibility constraints/evaluations, qualitative traceable evidence aggregation without numeric scoring, structured issue/unresolved findings plus explicit-scope conditions, an explicit FASTA `ReferenceContext` with content-verified `SequenceBinding` plus whole-bundle orchestration, categorical `COMPATIBLE` / `COMPATIBLE_WITH_CONDITIONS` / `INCOMPATIBLE` / `INDETERMINATE` aggregation over mandatory constraints, and compact decisive conflict-core extraction. Analysis status and stable `CompatibilityReport` serialization remain later work.

## Current CLI diagnostics

```bash
refcompat inspect-fasta reference.fa
refcompat check-fai reference.fa reference.fa.fai
refcompat check-dict reference.fa reference.dict
```

Add `--format json` to any command for provisional machine-readable output. These local diagnostics intentionally do not emit a whole-bundle compatibility verdict; see [`docs/diagnostic-output.md`](docs/diagnostic-output.md).

## Development

RefCompat supports Python 3.12 and newer and uses `uv` for project environments and dependency locking.

```bash
uv sync --all-groups
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv build
```

See [`docs/development.md`](docs/development.md) for details.

## License

RefCompat is licensed under the [Apache License 2.0](LICENSE). See [`NOTICE`](NOTICE) for project provenance.

## Citation

RefCompat was created by Greg Roe. If you use RefCompat in published research, please cite the software using the metadata in [`CITATION.cff`](CITATION.cff).
