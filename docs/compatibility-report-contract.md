# Milestone 7 compatibility report and workflow contract

**Status:** contract pinned in Slice 1; immutable analysis-status/report-root model implemented in Slice 2; explicit deterministic draft JSON projection implemented in Slice 3; Slice 4 internal scientific/API review hardening plus the first stable schema freeze are complete; Slice 5 report-owned relationship/provenance context is implemented; and Slice 6 deterministic human rendering plus the stable whole-bundle workflow exit policy is implemented. The first stable core report remains exact schema `1.0.0`; the current additive stable report is `1.1.0`, and draft revision 3 remains a separate provisional surface with no stable compatibility guarantee.

Milestone 7 stabilizes how RefCompat exposes already-established compatibility
reasoning to people, automation, and downstream software. It does not add a new
scientific verdict system and does not change the M2-M6 evidence hierarchy,
selected-FASTA authority, scope rules, provider boundaries, or categorical
compatibility semantics.

Slice 6 does not change the machine-report wire shape: stable JSON remains
schema `1.1.0` and provisional JSON remains draft revision 3. Human rendering and
workflow exit policy are views over the existing report boundary rather than new
serialized fields.

The milestone exists because RefCompat now has mature internal reasoning pieces
(`BundleReasoningResult`, categorical verdict aggregation, findings/conditions,
and conflict-core extraction) but still exposes only provisional Milestone 1
JSON diagnostics. Adding more formats before stabilizing the whole-bundle report
would force future BCF/BED/profile work to target an unsettled public boundary.

## 1. Two separate axes: analysis status and compatibility

`CompatibilityVerdict` answers a scientific question about the requested
reference-coordinate relationship. `AnalysisStatus` answers whether RefCompat
actually completed the requested implemented analysis. They are not synonyms.

Milestone 7 defines three analysis states:

- `COMPLETE` — every requested analysis operation represented by the implemented
  evaluation path completed successfully. This does **not** mean the relationship
  is compatible. A complete analysis may produce `COMPATIBLE`,
  `COMPATIBLE_WITH_CONDITIONS`, `INCOMPATIBLE`, or `INDETERMINATE`. In particular,
  a successful analysis that proves the available evidence is insufficient or
  ambiguous is still complete.
- `PARTIAL` — at least one requested analysis operation could not actually be
  completed, while the remaining completed work is valid enough to preserve in
  a report. The missing operation must be represented explicitly as an analysis
  issue; it must not be translated into biological contradiction. A partial
  analysis may retain an independently decisive `INCOMPATIBLE` conclusion when
  the omitted work cannot negate that hard conflict. Otherwise the report must
  remain `INDETERMINATE`; partial execution must never masquerade as a positive
  compatibility conclusion.
- `INVALID_INPUT` — required input is malformed, self-contradictory, or otherwise
  unusable for the requested scientific evaluation. Invalid input is not
  `INCOMPATIBLE`. A final stable report with this status does not emit a
  compatibility verdict.

Evidence insufficiency that the reasoner successfully models as an unresolved
mandatory requirement is not, by itself, `PARTIAL`. For example, the M6
`ucsc-preflight` path can deliberately reason over an unavailable provider
snapshot and produce an unresolved mandatory profile relationship; if that was
the modeled input to a successfully completed evaluation, the analysis may be
`COMPLETE` with verdict `INDETERMINATE`. `PARTIAL` is reserved for an analysis
operation that was requested but failed to execute or produce its modeled
result.

The Slice 2 report root requires a `PARTIAL` report to retain one coherent
bundle/verdict/conflict-core result from the work that did complete. That retained
verdict may be only `INCOMPATIBLE` or `INDETERMINATE`; an execution failure that
prevents any bundle-level scientific result is not converted into a synthetic
compatibility verdict merely so a report can be emitted.

## 2. Report assembly boundary

`CompatibilityReport` is the immutable public root result. Its assembly layer
consumes already-derived RefCompat values and validates that they belong to the
same evaluation. It must not:

- inspect files again;
- rebuild resource contracts or constraints;
- reinterpret profile/provider facts;
- score, vote, average, or otherwise recompute evidence strength;
- turn descriptive relationship summaries into a second verdict;
- convert missing evidence into incompatibility; or
- repair inconsistent internal objects by guessing what was intended.

The report assembler rejects cross-wired or internally inconsistent inputs
before they can become report authority. Stable requirement and capability IDs
must be globally unique within one report, and requirement/capability/binding,
evaluation, evidence, finding, condition, verdict, and conflict-core references
must agree with the already-derived objects they claim to trace. This is
consistency validation, not a second reasoning pass.

Analysis-status policy may conservatively prevent partial/invalid execution from
being presented as positive compatibility, but it must not weaken an already
independently established hard contradiction merely because unrelated work is
incomplete.

## 3. Stable external model, not internal-object serialization

The stable JSON representation is a RefCompat-owned interface. It must be built
through explicit report DTO/projection code. The implementation must not use a
recursive `dataclasses.asdict()`-style dump of internal reasoning objects or
serialize `pysam`, `refget`, UCSC-provider, or other upstream/library types
directly.

This separation is load-bearing:

- internal dataclass layout may evolve without silently changing the public
  schema;
- provider-specific implementation details do not leak into generic output;
- schema changes are deliberate and reviewable;
- JSON field names and nullability are part of the public contract rather than
  accidental Python structure.

## 4. Required stable report content

The M7 report must be able to represent at least:

1. report schema/version identity and RefCompat tool version;
2. analysis status plus explicit analysis issues when status is not complete;
3. evaluation request, selected FASTA anchor, explicit scope, active profiles,
   and policy selector when present;
4. supplied resource identities and kinds, with optional artifact byte sizes
   and digests when independently available; local `ArtifactIdentity.path`
   values are execution context and are not stable report identity;
5. the compatibility verdict when scientifically reportable;
6. the mandatory constraint-state basis retained by `VerdictAggregation`;
7. findings, conditions, and decisive conflict cores;
8. evidence records with requirement/capability/binding/source-observation trace;
9. verified sequence-binding relationships needed to explain cross-name results;
10. relevant report-owned observation/provenance records sufficient to follow
    decisive conclusions back to their factual basis;
11. unresolved questions/analysis issues that materially limit the report; and
12. typed relationship context needed to explain a generic verdict without
    creating a second verdict system.

The first required relationship-context example is BAM/CRAM dictionary
classification. A report must be able to surface membership, naming, order,
M5-content, conflict, and non-bijective mapping context alongside the generic
compatibility verdict. The relationship summary remains descriptive: it never
replaces or overrides the generic constraints/evidence/verdict.

M6 provider/profile provenance that materially authorizes a reported conclusion
is projected in Slice 5 into report-owned provenance/context records. The
current UCSC projection records the selected provider context, dimensional
completeness, source provenance, resource-local name-resolution trace, and the
target-content proof that authorized any profile binding. Naming-source
provenance is retained separately from target-content provenance. The stable
report does not embed `UcscProviderSnapshot` or other profile implementation
dataclasses directly. The separate stable-profile-interface work remains a
later v1.0 boundary; these records preserve traceability for the already-
implemented profile without freezing its implementation API.

Slice 5 also accepts report-owned `ResourceObservation` values when the caller
retains them, and validates BAM/CRAM `AlignmentDictionaryRelationshipSummary`
records against the already-derived bundle and sequence bindings before
serialization. These context arrays are additive trace surfaces; their presence
does not cause the report assembler to re-run an inspector or classifier. A
source-observation ID already carried by evidence/capabilities is not claimed to
be globally resolvable unless its observation record was actually supplied to
the report.

## 5. Determinism and ordering

Stable machine output must be reproducible for scientifically equivalent report
inputs.

- JSON key order is deterministic.
- Collections whose semantics are sets are emitted in a documented canonical
  order based on stable report identifiers or another explicit semantic key.
- Scientifically meaningful order is preserved rather than sorted away. Examples
  include caller resource order when exposed as request context, FASTA sequence
  order where relevant, and BAM/CRAM shared-sequence order diagnostics.
- Duplicate stable IDs are invalid; in particular, requirement IDs and
  capability IDs are report-global within their respective namespaces rather
  than merely unique inside one resource contract.
- Local filesystem artifact paths are not serialized as stable resource
  identity. Caller-provided resource IDs and display names remain caller-visible
  context, while independently available byte size/digest facts may be emitted.
- JSON output uses UTF-8 and must not emit non-standard NaN/Infinity values.
- Human rendering may reorder information for readability only when it does not
  change the machine-report semantics.

Known-answer fixtures must pin deterministic bytes or normalized JSON values for
representative reports before the schema is frozen.

The draft projection is intentionally self-identifying as
`refcompat.compatibility_report` with `stability = "draft"` and an integer draft
revision. That marker is not the stable report schema version and does not create
backward-compatibility guarantees. The Slice 4 review hardening advanced the
draft revision from 1 to 2 because omitting local artifact paths changed the
provisional wire shape. Slice 5 advances the draft again to revision 3 because
report-owned observations, alignment relationship summaries, and profile/
provider provenance are added to the scientific-result body. The draft
projection is explicit rather than a recursive dataclass dump: it emits request/
resource context, analysis status/issues, verdict basis, typed requirements/
constraints/evaluations, trace-relevant capabilities, evidence/findings/
conditions, verified sequence bindings, conflict cores, and the same supplied
report-owned context records. Internal `ResourceContract`, `ReferenceContext`,
and profile/provider implementation objects are not serialized directly.

Capabilities are included when they are referenced by constraints, evaluations,
evidence, sequence-binding traces, or transitive identity-absence provenance;
the draft does not serialize the complete anchor capability graph merely because
it exists internally. Source-observation IDs are retained where already present,
and Slice 5 emits any report-owned observation/provenance records explicitly
supplied to the validated report root.

`compatibility_report_payload()` and `render_compatibility_report_json()` now
identify the current additive stable body as schema `1.1.0`. Exact schema
`1.0.0` remains packaged and its frozen known-answer reports remain unchanged.
The draft payload/rendering functions remain separate and emit revision 3;
callers are never silently migrated from draft to stable semantics.

## 6. Schema versioning

Stable report schema versions are independent of the Python package version and
use semantic `MAJOR.MINOR.PATCH` identifiers. A stable report identifies itself
before the body through:

```json
{
  "report_format": {
    "name": "refcompat.compatibility_report",
    "schema_version": "1.1.0"
  }
}
```

The first frozen stable schema is `1.0.0`. Its exact JSON Schema remains packaged
as `refcompat.schemas/compatibility-report-1.0.0.schema.json` with the stable
identifier `urn:refcompat:schema:compatibility-report:1.0.0`. Slice 5 adds the
current exact schema `1.1.0` at
`refcompat.schemas/compatibility-report-1.1.0.schema.json`, with identifier
`urn:refcompat:schema:compatibility-report:1.1.0`. Both use JSON Schema Draft
2020-12. Stable 1.0.0 known-answer bytes are retained, while 1.1.0 adds
compatible, incompatible, and representative UCSC/BAM contextual fixtures. The
draft fixture is now revision 3.

One schema-only pre-release erratum is applied to the retained 1.0.0 validator:
its refget identity regex was originally over-escaped and rejected the already-
defined serializer's valid `SQ.<32-character>` representation. RefCompat is
still pre-release and no package release has shipped schema 1.0.0, so the
checked-in validator is corrected in place before the first release without
changing emitted 1.0.0 JSON or field meaning. Once a schema version has shipped
in a package release, its checked-in bytes are immutable; the same kind of
correction then requires a PATCH schema version.

Version compatibility rules are:

- **MAJOR** increments for breaking wire or semantic changes: removing or
  renaming fields, making an existing optional field required, changing a field's JSON type
  or nullability, adding or removing values from an existing closed enum or
  discriminated union, changing the meaning of an existing value, or changing
  scientifically meaningful ordering semantics. Existing `1.x` enums and typed
  unions are closed unless a future major version explicitly says otherwise.
- **MINOR** increments for backward-preserving extensions such as new fields or
  sections whose meaning is independent of existing fields. A newly introduced
  section may be required by the newer exact-version schema when every report
  claiming that new version can emit it (including as an empty collection);
  older same-major consumers remain forward-tolerant only if they deliberately
  ignore that unknown section. A new section may define its own new enums or
  record types, but an existing closed enum/union is not widened under a minor
  bump. Slice 5 relationship/provenance additions therefore advance the current
  schema to `1.1.0` rather than silently redefining `1.0.0`.
- **PATCH** increments only when emitted stable JSON instances and their meanings
  are unchanged, for example documentation/schema corrections that bring the
  checked-in schema into agreement with the already-frozen serializer without
  requiring consumer logic changes.

Each checked-in schema is an **exact-version validator**. Version `1.0.0` is
closed against unknown object fields and closed over its current enum/type
variants, so a `1.1.0` report is validated against the `1.1.0` schema rather than
being relabeled as `1.0.0`. Consumers may deliberately implement same-major
forward tolerance by ignoring unknown optional fields, but they must inspect
`schema_version` first. Unknown values in an existing closed enum or typed union
are not a same-major extension and must not be silently reinterpreted. Consumers
that require an exact contract should reject versions for which they do not
possess the matching schema.

Requiredness and nullability are defined only by the versioned JSON Schema. A
required field is always present; a nullable field is present with JSON `null`
when no value is available. Absence and `null` are not interchangeable unless a
later schema explicitly says so. The stable serializer continues to use UTF-8,
strict JSON numbers, deterministic key ordering, and a trailing newline.

The draft marker (`stability = "draft"`, integer `revision`) is intentionally
not a schema version. Draft reports do not satisfy the stable schema and carry no
backward-compatibility promise.

## 7. Traceability

Every reported scientific conclusion must be traceable to RefCompat-owned IDs.
At minimum:

- a verdict cites its retained mandatory state/basis;
- decisive non-positive outcomes cite findings/conflict cores;
- findings cite constraints and evidence;
- evidence cites requirements, capabilities, source observations when present,
  and sequence bindings where required;
- cross-name relationships cite their verified bindings; and
- profile/provider authorization that materially affects a conclusion retains
  source/context provenance through report-owned records.

The stable report may summarize non-decisive evidence, but it must not drop the
trace required to justify a conclusion or invent a trace that the reasoning
layer did not establish.

## 8. Human output

Human output is a view over the immutable report, not a parallel reasoning path.
The preferred order remains:

1. resources evaluated;
2. selected reference context and verified/claimed/unresolved relationships;
3. analysis status and scoped compatibility verdict;
4. decisive failed or unresolved mandatory constraints;
5. meaningful relationship/difference context;
6. evidence/provenance conflicts;
7. explicit conditions; and
8. safest non-mutating next diagnostic action when one is represented by the
   report.

Presentation may omit low-value detail from the default view, but machine output
retains the stable trace. Slice 6 exposes
`render_compatibility_report_human(report)` as deterministic plain text. It does
not include machine-local artifact paths and does not use color or terminal
control sequences. The human layout is intentionally for people rather than a
second machine-readable protocol; downstream software must consume the
versioned JSON report instead of parsing human text.

## 9. CLI and workflow exit behavior

Slice 6 freezes the stable **whole-bundle** workflow exit mapping. The mapping is
a policy view over one validated `CompatibilityReport`; it does not alter the
scientific verdict or analysis-status model.

| Exit | Stable meaning |
|---:|---|
| `0` | complete analysis with `COMPATIBLE` or `COMPATIBLE_WITH_CONDITIONS` |
| `1` | complete analysis with `INCOMPATIBLE` |
| `2` | `INVALID_INPUT` report / invalid whole-bundle input |
| `3` | complete analysis with `INDETERMINATE` |
| `4` | `PARTIAL` analysis, regardless of the retained non-positive scientific result |
| `5` | operational failure before a `CompatibilityReport` could be constructed |

The public `WorkflowExitCode` enum and `workflow_exit_code(report)` function own
that mapping. `OPERATIONAL_FAILURE` is intentionally not returned for any report
instance: it is reserved for parser/provider-adapter/runtime failure that aborts
before the report boundary exists.

Several consequences are deliberate:

- a valid scientific `INCOMPATIBLE` result is exit `1`, not a tool crash;
- a valid scientific `INDETERMINATE` result is exit `3`, not malformed input;
- `COMPATIBLE_WITH_CONDITIONS` maps to exit `0`, but the condition remains
  explicit in the report. A caller requiring unconditional compatibility must
  inspect the verdict/conditions rather than treating exit `0` as a stronger
  scientific claim;
- a partial report maps to exit `4` even when it retains an independently
  decisive `INCOMPATIBLE` result. The report still carries that scientific
  result, while process status foregrounds the incomplete requested analysis;
- invalid input (`2`) and pre-report operational failure (`5`) remain distinct
  from normal scientific outcomes; and
- existing Milestone 1 `inspect-fasta`, `check-fai`, and `check-dict` commands
  keep their current provisional exit behavior. In particular, their diagnostic
  conflicts still return `0` and their normalized diagnostic/input errors still
  return `2`; Slice 6 does not silently migrate those commands to the stable
  whole-bundle mapping.

For CI, a caller that already assembled a report can terminate with the stable
policy directly:

```python
from refcompat.reporting import workflow_exit_code

raise SystemExit(workflow_exit_code(report))
```

A shell wrapper can then choose deliberately among `1` (incompatible), `3`
(indeterminate), and `4` (partial) instead of collapsing them into one generic
failure. Code `5` is reserved for failures where no report was produced.

## 10. Non-goals for Milestone 7

M7 does not, merely because reporting is being stabilized:

- add BCF or BED support;
- add reference-free comparison;
- introduce a portable reference manifest;
- freeze the general profile/plugin interface;
- add live UCSC acquisition or a persistent provider cache;
- add new biological compatibility heuristics;
- change the four compatibility verdicts;
- perform liftover, renaming, reheadering, realignment, repair, or mutation; or
- make human presentation authoritative over the machine report.

Those remain separate roadmap capabilities.

## 11. Planned implementation slices

1. **Contract** — pin this report/status/schema/workflow boundary.
2. **Report root** — add immutable analysis-status/report-root models and
   cross-object validation over existing reasoning results. **Implemented.**
3. **Draft serialization** — add explicit deterministic report DTO/JSON
   projection and representative known-answer fixtures without yet claiming the
   schema is frozen. **Implemented.**
4. **Internal checkpoint + schema freeze** — conduct scientific/API review, fix
   any model/trace defects, then check in the first stable JSON Schema and
   versioning rules. **Complete; stable core schema `1.0.0`.**
5. **Relationship/provenance context** — include BAM/CRAM dictionary relationship
   context and the report-owned provenance needed to trace the existing UCSC
   profile without leaking profile internals. **Complete; current additive stable
   schema `1.1.0`, with exact `1.0.0` retained.**
6. **Human/CLI workflow surface** — render the same report for people and pin the
   stable whole-bundle exit-code contract while leaving provisional legacy
   diagnostics unchanged until explicitly migrated. **Implemented.**
7. **Representative end-to-end paths** — exercise VCF, BAM/CRAM, annotation,
   explicit scope, UCSC profile, incompatible, and indeterminate reports through
   the same root model/serialization.
8. **Exit/review** — adversarial schema/traceability/backward-compatibility
   fixtures, final internal review, and external milestone-boundary review.

## 12. Exit criteria

Milestone 7 is complete only when:

- report assembly cannot create a scientific conclusion absent from the existing
  reasoning results;
- analysis status is distinct from compatibility and insufficient evidence is
  not mislabeled as partial execution;
- partial/invalid execution cannot appear as unconditional positive compatibility;
- the stable JSON schema is checked in, versioned, deterministic, and covered by
  known-answer plus compatibility tests;
- decisive conclusions are traceable through stable report-owned identifiers;
- BAM/CRAM non-bijective and naming/content relationship context is visible
  beside, not instead of, the generic verdict;
- the M6 UCSC profile remains traceable without serializing provider internals
  directly;
- human output and workflow exits are views/policy over the same report rather
  than separate reasoning systems;
- legacy provisional diagnostics are either intentionally migrated or clearly
  remain separate; and
- internal and external milestone reviews are complete before later format
  milestones rely on the stable report surface.
