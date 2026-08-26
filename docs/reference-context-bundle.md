# Milestone 2 anchor-driven reference context and bundle reasoning

**Status:** implemented as the fourth Milestone 2 reasoning slice. The following categorical verdict-aggregation and conflict-core slices are also implemented; analysis status and stable `CompatibilityReport` serialization remain later work.

This slice establishes the bridge from per-resource contracts to one explicit
FASTA-anchored bundle evaluation. It does not decide the bundle verdict.

## Reference context

`ReferenceContext` is reasoner-produced from the FASTA selected by
`EvaluationRequest.anchor_resource_id` and the explicit `EvaluationScope`.
For v0.1:

- the anchor snapshot must be `COMPLETE`;
- the anchor must remain inside resource scope;
- an explicit anchor-sequence subset must contain names that actually exist in
  the FASTA snapshot;
- selected sequences preserve FASTA order even when the caller lists the subset
  in another order;
- anchor presence, length, content-identity, and order capabilities are derived
  only from the selected anchor sequences.

Peer resources never contribute candidate reference capabilities. They cannot
vote on, replace, or outweigh the selected FASTA anchor.

The context intentionally derives positive presence only for selected anchor
sequences; it does not synthesize `present=False` for every unmatched raw name.
A name absent from the FASTA namespace may still be an unbound local alias, so
raw-name absence remains `UNRESOLVED` until evidence establishes a binding or
an explicit negative capability can legitimately prove absence. Explicit
anchor-sequence scope likewise hides out-of-scope anchor facts rather than
turning them into contradictions.

## Sequence binding

`SequenceBinding` maps a resource-local sequence name to one anchor-local
sequence only when comparable content identity establishes the relationship.
The current derivation supports refget sequence IDs and M5/MD5 identities
without cross-algorithm comparison. Identity capabilities require explicit
provenance distinguishing `CONTENT_DERIVED` values from `DECLARED_METADATA`
claims. Only content-derived identities may satisfy sequence-identity
requirements or populate authoritative anchor identity capabilities; declared
metadata may participate only in conservative binding derivation.
`ReferenceContext` independently verifies that its anchor identity capability
set exactly matches the selected FASTA snapshot.

A binding records:

- the local resource and local sequence name;
- the FASTA anchor and anchor-local sequence name;
- the content identity value(s) that established the relationship;
- the source capability IDs used to establish it;
- a deterministic opaque binding ID.

String resemblance is never enough. Binding uniqueness is checked against the
complete FASTA anchor snapshot, before any explicit anchor-sequence scope is
applied. If one local identity maps to more than one anchor sequence because
identical sequence content is duplicated anywhere in the FASTA, the binding
remains unresolved rather than choosing by name. Narrowing evaluation scope may
hide a unique target and leave the relationship unresolved, but it must never
turn an ambiguous full-FASTA match into a verified binding. Conflicting local
identity capabilities likewise do not produce a binding.

A verified binding takes precedence over an identical string label when the two
conflict. This prevents a familiar or matching label from overruling stronger
content-derived evidence.

## Binding-aware constraints and evidence

`CompatibilityConstraint` may carry verified sequence bindings. Exact-name
behavior is unchanged when no binding is present.

For a bound cross-name relationship:

- presence and length may be satisfied with `SatisfactionMode.VERIFIED_ALIAS`;
- identity remains satisfied with `VERIFIED_SEQUENCE_IDENTITY`;
- sequence-order requirements are projected through verified bindings before
  comparison;
- derived evidence uses `EvidenceMethod.VERIFIED_SEQUENCE_BINDING` and carries
  the relevant binding ID(s).

These binding-aware generic sequence constraints do not relax the specialized
FASTA/`.fai` or FASTA/`.dict` exact companion-artifact checks. A verified
biological binding may satisfy a biological naming requirement while still
failing an exact derived-artifact requirement; those Milestone 1 checks retain
their stricter representation semantics.

Evidence therefore remains traceable through:

```text
Finding
  -> Evidence
    -> SequenceBinding
      -> identity Capability IDs
```

as well as the existing capability-to-observation trace path.

## Whole-bundle orchestration

`reason_bundle()` requires exactly one `ResourceContract` for every resource in
explicit scope. Empty contracts are allowed, but silently omitting a scoped
resource is not.

The orchestrator:

1. normalizes contracts into request-scope order;
2. validates any explicitly supplied anchor-owned pair-derived supplemental capabilities;
3. builds the FASTA `ReferenceContext`;
4. derives unique evidence-backed sequence bindings;
5. builds one anchor-driven constraint for every typed requirement;
6. evaluates those constraints;
7. aggregates qualitative evidence;
8. produces structured findings and explicit-scope conditions.

The supplemental channel was added in Milestone 3 for exhaustive direct reference-base validation; peer contracts still cannot supply or vote on reference authority. `BundleReasoningResult` groups those immutable layers for later policy. It has no `verdict`, score, analysis status, or conflict core.

## Deliberately not implemented yet

This slice does **not** implement:

- conflict-core extraction (implemented by a later Milestone 2 slice);
- provenance claim assessment;
- stable `CompatibilityReport` serialization;
- CI exit-code policy;
- reference-free consensus or majority selection.

Those layers consume this anchor-driven result rather than being hidden inside
reference-context construction or sequence binding.
