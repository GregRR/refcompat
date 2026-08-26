# VCF contract and evidence projection

Milestone 3 projects already-observed VCF facts into RefCompat's format-neutral
reasoning model while keeping VCF-specific pattern interpretation outside the
core constraint layer.

## Inputs

`project_vcf_contract()` consumes:

- a `VcfContextSnapshot` from the complete VCF record scan;
- the exhaustive `VcfRefValidationResult` for that same VCF and FASTA;
- the selected FASTA `ReferenceContext`.

The three inputs are cross-checked for resource identity, record count, and
per-sequence record coverage before any contract/evidence object is produced.
Coverage comparison is by sequence name and count, not incidental tuple order;
the VCF snapshot still determines the first-observed ordering of projected
presence requirements.

## Contract shape

Actual `CHROM` usage becomes one mandatory `SequencePresenceRequirement` per
used sequence name, in first-observed order. Header-only `##contig`
declarations do not create presence requirements because an unused declaration
is not evidence that the VCF actually requires that contig for its records.

A syntactically valid `##contig` MD5 declaration for an actually used contig
also becomes one mandatory `SequenceIdentityRequirement`. When the declaration
is directly comparable to the selected or verified-bound FASTA sequence, a
different MD5 is Tier-A identity contradiction evidence. A declaration that
cannot be compared remains unresolved. Invalid and unused declarations do not
create identity requirements in this slice.

Context-accepted `##contig` MD5 identity may additionally appear as a VCF peer
capability only when it uniquely establishes a safe cross-name binding as
defined in [`vcf-sequence-binding.md`](vcf-sequence-binding.md). That capability
is binding evidence, not direct REF compatibility evidence.

The complete VCF record set becomes one mandatory `ReferenceBaseRequirement`
that explicitly names the selected FASTA anchor and carries its exhaustive
record count. RefCompat deliberately does **not** create one requirement object
per VCF record; the format-specific validation result
already retains every non-match, and a large VCF must not require a
million-object contract merely to state that all REF assertions must agree with
the anchor.

## Direct reference-base capability

`ReferenceBaseValidationCapability` is anchor-owned and records:

- the VCF resource whose assertions were checked;
- total checked records;
- matches;
- mismatches;
- unresolved direct comparisons.

For this projection, unresolved direct comparisons combine the existing
`OUT_OF_BOUNDS` and `UNRESOLVED_SEQUENCE` counts. Their distinct local causes
remain preserved in `VcfRefValidationResult` for later VCF-specific
interpretation.

The capability is pair-derived evidence. It is kept separate from the VCF's
`ResourceContract` because it is not an intrinsic capability asserted by the
VCF itself. Generic comparability requires its `resource_id` to equal the
`anchor_resource_id` named by the `ReferenceBaseRequirement`; a validation
capability from another FASTA therefore cannot satisfy the requirement.

## Generic constraint semantics

The format-neutral reference-base constraint applies these rules:

1. any exhaustive direct mismatch -> `UNSATISFIED`;
2. otherwise any unresolved direct comparison -> `UNRESOLVED`;
3. otherwise a non-empty all-match validation -> `SATISFIED` with
   `EXHAUSTIVE_DIRECT` satisfaction mode;
4. an empty record set -> `NOT_APPLICABLE`.

A mismatch is Tier-A conclusive content evidence using
`EXHAUSTIVE_REFERENCE_BASE_VALIDATION`. It cannot be averaged away by a larger
number of matches or by another supporting direct-validation capability.
Unresolved-only validation does not fabricate support or contradiction
evidence.

## Sequence-name boundary

Presence requirements use the ordinary generic sequence-presence machinery. Verified VCF bindings are now derived from uniquely matched `##contig` MD5 identity and supplied to the generic constraint machinery; string similarity remains irrelevant. Projection rejects a validation whose binding-ID trace does not match the bindings independently expected for the current VCF/FASTA/scope, preventing stale exact-name results from being silently reused.

## Deliberate boundary

This slice does not yet:

- convert `OUT_OF_BOUNDS` into a VCF-specific compatibility policy;
- treat `##reference`, declared `md5`, or unused `##contig` metadata as direct
  REF compatibility proof;
- rewrite REF/ALT;
- add stable report serialization;
- change the existing categorical bundle-verdict policy.

`VcfContractProjection` retains the generic contract, constraints,
evaluations/evidence, the original compact VCF validation result, and its
threshold-free `VcfRefConflictPatternSummary` without weakening the generic
hard-conflict rule. The anchor-owned pair-derived capability may now be passed
explicitly to `reason_bundle()` as supplemental evidence; it is never moved
into a peer contract or treated as peer-supplied reference authority. See
`vcf-bundle-orchestration.md`.
