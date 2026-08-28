# Package layout

**Status:** accepted initial architecture.

The source tree begins with these boundaries:

```text
src/refcompat/
├── __init__.py
├── cli.py
├── py.typed
├── model/
├── identity/
├── inspectors/
├── reasoning/
├── profiles/
└── reporting/
```

## `model/`

Owns RefCompat's stable immutable domain vocabulary: resources, observations, claims, sequence-collection snapshots, contracts, constraints, evidence, findings, conditions, verdicts, and conflict cores.

Core domain objects use standard-library immutable dataclasses, enums, and typed value objects. Domain objects must not expose upstream `refget`, `gtars`, `pysam`, transport-validation, or CLI-framework types.

`model/observations.py` owns the format-neutral `ResourceObservation`, `ObservationId`, `ObservationKind`, and `SourceLocation` primitives. `model/evaluation.py`, `model/contracts.py`, and `model/constraints.py` own the first Milestone 2 request/scope, typed requirement/capability contract, and question/result boundaries. `model/evidence.py` owns generalized qualitative evidence items and aggregates. `model/interpretation.py` owns structured findings and explicit-scope conditions. `model/reference_context.py` owns the FASTA-anchored `ReferenceContext` and evidence-backed `SequenceBinding`; `model/bundle.py` groups the whole-bundle reasoning result. `model/verdict.py` owns categorical verdict aggregation output, and `model/conflict_core.py` owns compact decisive failure cores. `model/alignment_relationship.py` owns the descriptive BAM/CRAM declared-dictionary relationship summary, `model/cram_reference.py` owns the deterministic offline CRAM reference plan, while `model/vcf_contract.py` owns the VCF-specific projection result; these reuse format-neutral reasoning types rather than defining parallel verdict systems.

## `identity/`

Owns the sequence-identity port and adapters.

GA4GH sequence/collection identity access to the external `refget` package is confined to the identity adapter. Format-specific code may use another documented public `refget` utility when it directly serves that format check (currently `compute_fai`), but external objects must still be copied immediately into RefCompat-owned values and may not leak into reasoning.

The initial identity implementation is:

```text
identity/
├── protocol.py
└── refget.py
```

`ReferenceIdentityProvider.inspect_fasta()` is the first frozen port method.
Comparison operations are added only when the reasoning layer requires them.

Remote metadata/discovery is separate from deterministic local identity. A metadata boundary should be introduced only when remote enrichment is implemented.

## `inspectors/`

Format-specific extraction. Inspectors produce immutable observations and claims. They do not emit top-level compatibility verdicts or decide that a familiar-looking name is a verified alias.

Inspectors are added one format at a time rather than pre-populating unused modules. `inspectors/fasta_index.py` parses supplied five-column FAI data and computes expected uncompressed FASTA geometry. `inspectors/sequence_dictionary.py` parses narrow SAM/Picard `.dict` artifacts and derives expected `SN`/`LN`/`M5` records from the already-computed complete FASTA identity snapshot. `inspectors/vcf.py` streams parser-isolated VCF observations, `inspectors/alignment.py` copies BAM/CRAM SAM-header declarations without scanning reads, and `inspectors/fasta_sequence.py` provides temporary-index FASTA random access computed from the FASTA itself. None decides a top-level compatibility verdict.

## `reasoning/`

Builds scope-dependent resource contracts, evaluates requirements against capabilities, creates evidence-backed findings/conditions, orchestrates anchor-driven bundle reasoning, aggregates categorical whole-bundle verdicts, and extracts compact decisive conflict cores.

The reasoning layer depends on RefCompat domain types, not format-parser internals. `reasoning/fasta_index.py` compares expected and observed FAI structure as Tier-B evidence. `reasoning/sequence_dictionary.py` compares exact dictionary structure while keeping Tier-A M5 evidence and missing-M5 uncertainty separate. `reasoning/constraints.py` implements the first exact typed requirement/capability evaluator and keeps missing evidence unresolved unless explicit negative evidence is available. `reasoning/evidence.py` derives traceable qualitative evidence from evaluator-relevant capabilities and aggregates it without numeric scoring. `reasoning/interpretation.py` maps non-satisfied applicable constraints to structured findings and explicit request scope to conditions. `reasoning/reference_context.py` constructs the selected FASTA context and content-verified local-name bindings, while `reasoning/bundle.py` evaluates all scoped typed requirements against that anchor. `reasoning/verdict.py` then applies mandatory/advisory policy and categorical verdict precedence without scoring or voting. `reasoning/conflict_core.py` projects only the decisive verdict-basis findings into compact resource/evidence cores. `reasoning/alignment_contract.py` projects BAM/CRAM `@SQ` names, lengths, and declared M5 values into generic core-format requirements and retains only safe declared-M5 capabilities supplied by `reasoning/alignment_binding.py` for conservative cross-name binding. `reasoning/alignment_relationship.py` describes declared dictionary membership, naming, relative shared-sequence order, M5 content state, and retained conflicts without creating a second verdict path. `reasoning/cram_reference.py` turns those header facts into a deterministic offline plan for any future reference-dependent CRAM decode, using only an explicitly selected local FASTA anchor or deferring the operation. `reasoning/vcf_ref.py` performs exhaustive direct REF comparison over RefCompat-owned record observations and a narrow reference-sequence protocol, without importing pysam or assigning a bundle verdict. `reasoning/vcf_binding.py` derives conservative cross-name VCF bindings from uniquely matched `##contig` MD5 identity. `reasoning/vcf_ref.py` can apply those explicit bindings during exhaustive REF comparison. `reasoning/vcf_contract.py` projects actual CHROM usage, declared lengths and valid MD5 declarations for used contigs, verified bindings, and the compact exhaustive REF result into generic presence, length, identity, and reference-base requirements, evaluations, and evidence. `reasoning/vcf_ref_pattern.py` adds threshold-free VCF-specific distribution interpretation without changing generic constraint or verdict policy.

## `profiles/`

Consumer/ecosystem-specific requirements. Profiles may add requirements or policy constraints; they may not rewrite observations or sequence identity.

No concrete profile module is required until the core reasoning model is stable.

## `reporting/`

Milestone 1 provides provisional human-readable and JSON diagnostics over the immutable identity and integrity result models in `reporting/diagnostics.py`. Presentation must not introduce conclusions absent from those models. Once the whole-bundle report model exists, reporting should converge on views over that shared immutable report rather than grow a parallel reasoning layer.

## CLI

`refcompat.cli` is intentionally thin. It uses the Python standard library `argparse` and delegates scientific work to the same package APIs used by other callers. The Milestone 1 surface exposes `inspect-fasta`, `check-fai`, and `check-dict` with human or provisional JSON output; stable CI verdict/exit-code policy remains a later interface decision.

## Directories intentionally not planned

Generic `plugins`, `registry`, `manager`, `service`, `repository`, `factory`, or `strategy` layers are not introduced until a concrete second implementation requires them. RefCompat should resist framework-building ahead of demonstrated need.
