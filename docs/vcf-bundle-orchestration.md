# VCF pair-derived evidence in whole-bundle reasoning

Milestone 3 now connects the VCF contract/evidence projection to the existing
anchor-driven whole-bundle reasoner without moving pair-derived evidence into a
peer resource contract.

## Supplemental capability boundary

`reason_bundle()` accepts an optional tuple of
`ReferenceBaseValidationCapability` values as `supplemental_capabilities`.
These capabilities are produced by direct comparison of a consumer resource
against the selected FASTA anchor. They are therefore neither intrinsic VCF
capabilities nor ordinary peer facts.

The orchestrator requires each supplemental capability to:

- be owned by the request's selected FASTA anchor;
- describe a resource inside the explicit evaluation scope;
- match an in-scope `ReferenceBaseRequirement` by consumer, anchor, and checked
  record count;
- have a unique capability ID; and
- be the only exhaustive supplemental candidate for any one reference-base
  requirement.

A supplemental capability that is cross-wired, unused, duplicated, or
competing is rejected rather than silently ignored.

## Candidate selection

Ordinary sequence presence, length, identity, and order requirements continue
to receive candidates only from `ReferenceContext.anchor_capabilities`, with
verified `SequenceBinding` projection where applicable.

`ReferenceBaseRequirement` is different because exhaustive REF evidence is
pair-derived. Its candidate comes only from the explicit supplemental channel.
Peer `ResourceContract.capabilities` are never considered for this purpose.
The requirement must itself name the same FASTA anchor selected by the
`EvaluationRequest`.

If no matching supplemental validation is supplied, the reference-base
requirement remains `UNRESOLVED`.

## Bundle traceability

`BundleReasoningResult` retains supplemental capabilities separately from the
resource contracts. Its invariants require:

- unique supplemental capability IDs;
- anchor ownership and scoped consumer identity;
- no capability-ID collision with ordinary anchor capabilities;
- every constraint candidate to come from either the reference context or the
  explicit supplemental set; and
- every supplemental capability to be cited by at least one constraint.

This keeps pair-derived evidence directly traceable without pretending that it
was asserted by the VCF or another peer resource.

## Existing verdict policy remains unchanged

No VCF-specific verdict rule is introduced here. The already-reviewed generic
layers consume the resulting constraint state and evidence:

- exhaustive all-match validation can satisfy a mandatory reference-base
  requirement and therefore participate in an otherwise `COMPATIBLE` bundle;
- any proven REF mismatch remains Tier-A contradictory evidence and can drive
  the existing mandatory-constraint verdict to `INCOMPATIBLE`;
- incomplete direct validation remains `UNRESOLVED`, produces no fabricated
  evidence, and can drive the existing verdict to `INDETERMINATE`;
- conflict-core extraction continues to report only the decisive trace.

There is no scoring, voting, mismatch-rate threshold, or majority rule.

## VCF-specific pattern interpretation

Isolated/localized/distributed/systematic REF-conflict distribution is now
interpreted
separately in [`vcf-ref-conflict-patterns.md`](vcf-ref-conflict-patterns.md).
Those labels do not alter the generic bundle verdict or conflict-core path
described here.

## Still deferred

The VCF path does not yet:

- reinterpret `OUT_OF_BOUNDS` as a VCF-specific policy conclusion;
- infer sequence-name aliases from string similarity;
- add a stable `CompatibilityReport` schema or new CLI command; or
- rewrite VCF REF/ALT data.
