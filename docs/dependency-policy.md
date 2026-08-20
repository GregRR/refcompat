# Dependency policy

RefCompat is licensed under the Apache License 2.0 and is intended to remain straightforward to adopt in academic, open-source, infrastructure, and commercial environments.

## Runtime dependency preference

Prefer runtime dependencies under permissive licenses such as:

- Apache-2.0
- MIT
- BSD-2-Clause
- BSD-3-Clause

A dependency under another license is not automatically prohibited, but its implications must be reviewed before adoption.

Licenses and terms requiring explicit review include:

- LGPL
- GPL
- AGPL
- MPL
- source-available licenses
- noncommercial licenses
- custom or otherwise restrictive licenses

Development/test-only dependencies and external command-line tools are evaluated according to how they are used rather than treated as equivalent to directly imported runtime libraries.

## Runtime dependency set

The package currently declares two direct runtime dependencies:

```text
pysam>=0.24,<0.25
refget>=0.12,<0.13
```

The upper bound is intentional because `refget` is pre-1.0 and its Python API is actively evolving. RefCompat isolates it behind an adapter so an upstream minor-version change does not propagate external types through the domain model.

Optional `refget` server/database extras are not part of RefCompat's dependency set.

A small direct dependency set does not mean the installed environment has only those runtime packages. `refget` 0.12 currently brings its own transitive stack, including `gtars` plus HTTP, CLI, YAML, and JSON-Schema-related packages. RefCompat does not import most of those packages directly, but they remain part of the installation footprint through `refget`. The committed lockfile is the authoritative dependency graph, and upstream dependency changes should be reviewed when the bounded `refget` line is updated.

## Format parsing

Dependencies are added when the corresponding implementation milestone needs them directly.

- FASTA/reference identity uses the `refget` adapter.
- `.fai` uses a narrow five-column reader; expected uncompressed FASTA geometry is computed through the existing public `refget.compute_fai` API, so no additional runtime dependency is introduced. `.dict` uses a narrow SAM-header reader for the `@SQ` fields required by its check; no additional runtime dependency is introduced.
- VCF now uses `pysam>=0.24,<0.25` behind a narrow adapter boundary. The 0.24 line provides CPython 3.14 wheels and permissive MIT licensing. BAM/CRAM may reuse the same dependency when that milestone begins.
- GTF/GFF3 begins with a narrow streaming parser for seqids, coordinates, required directives, and provenance fields. A larger annotation database/framework is not part of the initial scope.

A deliberately narrow parser is preferred when it is sufficient, easier to audit, and avoids imposing unrelated semantics.

## Application/model dependencies

Core domain models use the Python standard library rather than a runtime validation framework. Transport/schema libraries may be added later if the machine-readable report boundary demonstrates a concrete need.

The CLI initially uses standard-library `argparse` to avoid a separate CLI-framework dependency.

## External ecosystem tools

Consumer-specific profiles may understand requirements of external ecosystems without incorporating their source code.

If RefCompat later bundles, links, or directly depends on an external tool, that tool's license and redistribution terms must be reviewed at that time.
