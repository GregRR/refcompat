# ADR 0012 — Minimal runtime dependencies and format-parsing strategy

**Status:** Accepted

## Context

RefCompat spans several genomics formats, but importing broad parser frameworks before the corresponding checks exist would increase installation weight and constrain architecture prematurely.

## Decision

The initial direct runtime dependency set began with `refget>=0.12,<0.13`; Milestone 3 added bounded `pysam>=0.24,<0.25` for VCF parsing, and Milestone 4 reuses that dependency for BAM/CRAM header observation. This minimizes dependencies declared by RefCompat itself; it does not imply that the full installed environment is small, because `refget` has its own transitive runtime dependencies.

Additional format dependencies are introduced only when a milestone needs them directly:

- FASTA identity and SeqCol semantics use the RefCompat-owned adapter over `refget`.
- `.fai` and SAM/Picard-style `.dict` checks begin with narrow readers tailored to the fields RefCompat evaluates.
- VCF and BAM/CRAM header observation use `pysam>=0.24,<0.25` behind narrow adapter boundaries after dependency review.
- GTF/GFF3 begins with a narrow streaming parser for the tabular fields and directives required by RefCompat's reference-coordinate checks. A larger annotation database/framework is not required for the initial scope.
- Core domain objects use standard-library immutable dataclasses, enums, and typed value objects. Pydantic is not a core domain dependency.
- The CLI uses the standard library `argparse` initially.
- Machine-readable reports use explicit serialization from RefCompat-owned models. A stable checked-in JSON Schema is introduced only when the report model reaches a versioned stability point.

## Consequences

The RefCompat-declared runtime surface remains small, while the actual installation footprint includes `refget`'s transitive dependency tree and is tracked by `uv.lock`. RefCompat does not depend on packages merely because they are transitive dependencies of another library. Parser code remains narrowly aligned with the actual checks, while mature HTSlib-backed support can be added for binary/variant formats when needed.
