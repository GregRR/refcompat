# CRAM offline reference policy

**Status:** Milestone 4 deterministic offline reference planning implemented.

RefCompat keeps CRAM header reasoning separate from any operation that would
actually decode records against reference bases. This distinction is necessary
because the SAM header does not say whether every CRAM container or slice can be
restored without an external reference.

## What the header can and cannot establish

The initial CRAM container carries the textual SAM header, so RefCompat can
observe `@SQ` declarations without decoding alignment records or retrieving
reference sequence content.

CRAM reference dependency is encoded below that header boundary. In CRAM 3.x,
the compression-header preservation map includes `RR` ("reference required"),
and individual slices may carry embedded reference bases. A header-only
assessment therefore must not conclude either that an external reference is
required or that the CRAM is self-contained.

The CRAM specification also requires `@SQ M5` unless the relevant reference was
embedded. Missing M5 is consequently not permission to guess which local FASTA
should be used.

## Deterministic offline action

`plan_cram_offline_reference()` answers a narrower question:

> If a later RefCompat operation genuinely needs reference bases, is the
> explicitly selected local FASTA anchor safe to pass to the CRAM provider?

There are only two actions:

- `USE_EXPLICIT_LOCAL_ANCHOR`
- `DEFER_REFERENCE_DEPENDENT_DECODING`

The selected FASTA can be offered explicitly only when all of the following are
true for the evaluated CRAM header:

- declared membership is `EXACT` or `ALIGNMENT_SUBSET` relative to the selected
  FASTA scope;
- shared sequences resolve by exact primary `SN` names rather than cross-name
  binding;
- every resolved sequence is M5-verified against content-derived FASTA identity;
- no declared `LN` conflict remains; and
- the selected FASTA path is locally readable.

A strict subset is safe because the selected FASTA may contain additional
sequences that the CRAM header does not declare.

## Why verified cross-name identity still defers

A verified M5-backed `SequenceBinding` proves a semantic sequence relationship
inside RefCompat. It does not by itself prove that an external CRAM provider can
address sequences in one FASTA using the CRAM header's different `SN` labels.

RefCompat therefore does not turn a cross-name semantic binding into permission
to hand that FASTA to a record decoder. Provider-level name/addressing support
would need its own explicit, tested mechanism rather than being inferred from
biological identity.

## No ambient or network fallback

The deterministic core does not automatically use:

- `@SQ UR` paths;
- `REF_CACHE`;
- `REF_PATH`; or
- remote reference retrieval.

HTSlib/pysam can use those mechanisms during CRAM decoding when no explicit
reference is supplied. RefCompat's policy is instead to supply the selected
local FASTA explicitly only when it is safe, which overrides those fallback
paths, or to defer reference-dependent decoding.

A header `UR` remains provenance/metadata even when it happens to name a local
file.

## What `UNRESOLVED` means here

Deferring reference-dependent decoding is not an incompatibility verdict. It
means only that RefCompat lacks sufficient deterministic offline evidence to
choose a local reference source for that future operation.

Header-derived requirements, verified bindings, and dictionary relationship
results remain valid. RefCompat does not erase those conclusions merely because
a later record-level operation cannot proceed offline.

## Non-goals

This slice does not:

- inspect CRAM compression headers, preservation maps, slices, or records;
- claim whether a particular CRAM actually requires an external reference;
- download or cache references;
- follow header `UR` automatically;
- inspect mapping correctness or actual read use;
- rename/reheader references; or
- realign reads.

## Related design

- [`alignment-header-observation.md`](alignment-header-observation.md)
- [`alignment-contract-projection.md`](alignment-contract-projection.md)
- [`alignment-sequence-binding.md`](alignment-sequence-binding.md)
- [`alignment-dictionary-relationships.md`](alignment-dictionary-relationships.md)
- [`adr/0007-offline-capable-core.md`](adr/0007-offline-capable-core.md)

## Standards and provider references

- CRAM v3.1: <https://samtools.github.io/hts-specs/CRAMv3.pdf>
- pysam `AlignmentFile`: <https://pysam.readthedocs.io/en/latest/api.html>
- HTSlib/Samtools CRAM reference lookup: <https://www.htslib.org/doc/samtools.html>
