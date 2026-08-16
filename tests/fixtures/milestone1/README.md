# Milestone 1 exit fixtures

These tiny synthetic fixtures encode deterministic failure patterns drawn from
the project discovery corpus. They are not intended to represent a biological
reference distribution.

- `content_v1.fa` is the baseline two-sequence FASTA.
- `content_v2.fa` preserves names, order, and lengths but changes the content of
  `chr1`; it is the same-name/different-sequence control.
- `content_v1.dict` was constructed for `content_v1.fa`. Pairing it with
  `content_v2.fa` creates a dictionary that is stale **by construction** while
  allowing RefCompat to report only the observable M5 contradiction.
- `content_v1.fa.fai` was constructed for `content_v1.fa`. Pairing it with
  `length_changed_v2.fa` creates an index that is stale **by construction**
  while RefCompat reports only the observable structural differences. A `.fai`
  carries structural geometry rather than sequence-content digests, so the
  same-length content-only change in `content_v2.fa` is intentionally invisible
  to this index check; the geometry-changing fixture is used for the stale-index
  detection case.
- `alias_only.dict` carries the same M5 content under `1`/`2` primary names and
  declares `chr1`/`chr2` as aliases; declarations do not satisfy exact
  companion-artifact naming.
- `order_difference.dict` contains the exact baseline records in the opposite
  order.

The tests deliberately preserve the distinction between how a fixture was
constructed and what the checker is justified in concluding from its evidence.
