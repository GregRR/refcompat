# Milestone 1 diagnostic output

RefCompat's first reporting slice exposes the identity and derived-artifact
facts already established by the FASTA, `.fai`, and `.dict` implementations.
It is deliberately narrower than the eventual whole-bundle report model.

The diagnostic layer must not manufacture Milestone 2 concepts before the
reasoner can support them. In particular, these outputs contain no top-level
`COMPATIBLE`, `INCOMPATIBLE`, `INDETERMINATE`, finding, condition, or conflict-
core verdict. They report only the local identity/evidence facts already
present in the underlying RefCompat-owned models.

## CLI surface

The initial commands are:

```text
refcompat inspect-fasta FASTA [--format human|json]
refcompat check-fai FASTA FAI [--format human|json]
refcompat check-dict FASTA DICT [--format human|json]
```

Human output is the default. `--format json` emits deterministic, pretty JSON
using explicit RefCompat serialization rather than generic dataclass dumping.
The command-line path is used as the resource identifier so every diagnostic
remains traceable to the supplied artifact.

## FASTA identity diagnostics

FASTA diagnostics expose:

- resource identifier;
- snapshot completeness;
- SeqCol collection and component digests when available;
- identity-provider name/version when available;
- per-sequence local name, length, ordinal, refget sequence ID, and legacy MD5.

Missing values are represented as `null` in JSON and `unavailable` in human
output. A sparse future snapshot must remain sparse; the reporter does not
promote missing identity evidence.

## FASTA ↔ `.fai` diagnostics

FAI output exposes:

- the paired FASTA and index resource identifiers;
- exact structural verification state;
- Tier-B evidence strength and polarity;
- every localized count/name/order/length/layout difference.

The reporter does not label a mismatch `stale`; that causal interpretation
requires separate provenance evidence.

## FASTA ↔ `.dict` diagnostics

Sequence-dictionary output keeps distinct:

- exact structural verification;
- exact-name M5 content verification;
- exact companion verification;
- structural or M5 conflicts;
- missing-M5 evidence gaps;
- unambiguous cross-name M5 identity matches;
- cross-name M5/LN inconsistencies.

The mixed M5/LN inconsistency intentionally has no forced evidence polarity or
strength because the existing evidence vocabulary is binary and the
observation itself does not establish which declaration is wrong.

## JSON stability

This Milestone 1 JSON is **provisional diagnostic output**, not the stable
machine-readable `CompatibilityReport` schema described in `DESIGN.md`.
Field names should still change deliberately and with tests, but pre-1.0
consumers must not treat this shape as the final report-schema contract.

The stable schema/versioning decision remains deferred until the report model
and whole-bundle reasoning are implemented.

## Process exit status

For this provisional diagnostic surface, a successfully completed analysis
returns exit status `0` even when the result contains a structural/content
conflict. Input, parsing, provider, or computation failures normalized by the
implemented inspectors return `2` and a concise message on standard error.

This keeps a scientific/compatibility observation separate from command
execution failure. Stable CI/workflow exit-code behavior remains a later v1.0
interface decision.
