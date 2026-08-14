# ADR 0012 — Minimal runtime dependencies and format-parsing strategy

**Status:** Accepted

## Context

RefCompat spans several genomics formats, but importing broad parser frameworks before the corresponding checks exist would increase installation weight and constrain architecture prematurely.

## Decision

The initial runtime dependency set contains only `refget>=0.12,<0.13`.

Additional format dependencies are introduced only when a milestone needs them directly:

- FASTA identity and SeqCol semantics use the RefCompat-owned adapter over `refget`.
- `.fai` and SAM/Picard-style `.dict` checks begin with narrow readers tailored to the fields RefCompat evaluates.
- BAM/CRAM/VCF implementation is expected to use `pysam` when that milestone begins, subject to a dependency review at adoption time.
- GTF/GFF3 begins with a narrow streaming parser for the tabular fields and directives required by RefCompat's reference-coordinate checks. A larger annotation database/framework is not required for the initial scope.
- Core domain objects use standard-library immutable dataclasses, enums, and typed value objects. Pydantic is not a core domain dependency.
- The CLI uses the standard library `argparse` initially.
- Machine-readable reports use explicit serialization from RefCompat-owned models. A stable checked-in JSON Schema is introduced only when the report model reaches a versioned stability point.

## Consequences

The base installation remains small. RefCompat does not depend on packages merely because they are transitive dependencies of another library. Parser code remains narrowly aligned with the actual checks, while mature HTSlib-backed support can be added for binary/variant formats when needed.
