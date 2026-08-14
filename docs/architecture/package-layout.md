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

Owns RefCompat's stable immutable domain vocabulary: resources, observations, claims, sequence-collection snapshots, contracts, constraints, evidence, findings, conditions, and verdicts.

Core domain objects use standard-library immutable dataclasses, enums, and typed value objects. Domain objects must not expose upstream `refget`, `gtars`, `pysam`, transport-validation, or CLI-framework types.

## `identity/`

Owns the sequence-identity port and adapters.

Direct imports from the external `refget` package are confined to the GA4GH identity adapter rather than scattered through the reasoning model.

Expected first implementation files are:

```text
identity/
├── protocol.py
└── refget.py
```

Remote metadata/discovery is separate from deterministic local identity. A metadata boundary should be introduced only when remote enrichment is implemented.

## `inspectors/`

Format-specific extraction. Inspectors produce immutable observations and claims. They do not emit top-level compatibility verdicts or decide that a familiar-looking name is a verified alias.

Inspectors are added one format at a time rather than pre-populating unused modules.

## `reasoning/`

Builds scope-dependent resource contracts, evaluates requirements against capabilities, creates evidence-backed findings/conditions, and aggregates whole-bundle verdicts.

The reasoning layer depends on RefCompat domain types, not format-parser internals.

## `profiles/`

Consumer/ecosystem-specific requirements. Profiles may add requirements or policy constraints; they may not rewrite observations or sequence identity.

No concrete profile module is required until the core reasoning model is stable.

## `reporting/`

Human-readable and machine-readable views over the same immutable report model. Presentation must not introduce conclusions absent from the reasoning model.

## CLI

`refcompat.cli` is intentionally thin. The initial CLI uses the Python standard library `argparse` and delegates scientific work to the same package APIs used by other callers.

## Directories intentionally not planned

Generic `plugins`, `registry`, `manager`, `service`, `repository`, `factory`, or `strategy` layers are not introduced until a concrete second implementation requires them. RefCompat should resist framework-building ahead of demonstrated need.
