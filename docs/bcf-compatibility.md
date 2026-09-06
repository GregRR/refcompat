# Milestone 8 native BCF compatibility contract

**Status:** contract pinned; implementation pending.

Milestone 8 adds BCF2 as a first-class resource encoding while preserving the scientific semantics already established for VCF in RCHECK-050. The milestone is intentionally an encoding/parity milestone, not a new variant-compatibility reasoner.

Primary standards/provider references:

- GA4GH/Samtools HTS specifications index: <https://samtools.github.io/hts-specs/>
- VCF v4.5 / BCF v2.2 specification: <https://samtools.github.io/hts-specs/VCFv4.5.pdf>
- BCF2 quick reference: <https://github.com/samtools/hts-specs/blob/master/BCFv2_qref.tex>
- pysam `VariantFile` documentation: <https://pysam.readthedocs.io/en/latest/api.html>

## 1. Scientific identity of the format

BCF2 is the binary encoding of the VCF logical data model. For RefCompat's reference-coordinate question, the relevant facts remain the same logical facts already consumed from VCF:

- VCF header version and reference claims;
- ordered contig declarations;
- contig names, lengths, declared MD5 values, assembly labels, and URLs;
- actual record `CHROM` usage;
- logical record `POS`;
- `REF` sequence.

M8 therefore must not create parallel `Bcf*` requirements, evidence kinds, findings, conflict patterns, or verdicts merely because the bytes are encoded differently. BCF follows the existing RCHECK-050 reasoning path unless a future scientific requirement demonstrates that an encoding-specific fact changes reference compatibility.

The existing `Vcf*` domain names describe the VCF logical record/header model and remain valid for BCF-decoded logical values. They do not imply that every source artifact is textual VCF.

## 2. Resource kind and encoding authority

BCF is represented by a distinct `ResourceKind.BCF`. Text VCF (plain or BGZF-compressed) remains `ResourceKind.VCF`.

This distinction is deliberate. `ResourceKind` identifies the supplied artifact format; silently broadening `VCF` to mean both textual VCF and BCF would change the meaning of an existing public enum value and would hide a useful provenance fact.

The parser boundary uses `pysam.VariantFile`, which auto-detects VCF/BCF. The caller's declared resource kind and the provider-detected encoding must agree:

- declared `VCF` + provider `is_bcf == False` → accepted;
- declared `BCF` + provider `is_bcf == True` → accepted;
- declared `VCF` + provider `is_bcf == True` → input/format mismatch error;
- declared `BCF` + provider `is_bcf == False` → input/format mismatch error.

Filename extensions are not format authority. RefCompat does not silently reclassify a resource because its suffix disagrees with its bytes.

This mirrors the existing BAM/CRAM inspector invariant that the declared resource kind must agree with the parser-visible format.

## 3. Provider normalization boundary

RefCompat continues to copy primitive values out of pysam/HTSlib immediately. Provider-owned `VariantFile`, header, contig, or record objects must not leak into domain or report models.

For BCF, HTSlib exposes the decoded VCF logical header. `VcfHeaderData.file_format` therefore continues to represent the logical VCF header version such as `VCFv4.2`; it is not repurposed as a BCF encoding-version field. The binary encoding itself is represented by `ResourceKind.BCF`.

M8 does not promise a byte-faithful BCF-header or record-layout parser. BCF dictionary indexes/`IDX`, INFO/FORMAT/genotype binary representations, BGZF block structure, and other encoding mechanics are outside the compatibility observation surface unless later evidence shows that they materially affect the reference-coordinate question.

BCF1 is obsolete and is not an M8 target. M8 targets BCF2 as accepted by the pinned pysam/HTSlib provider boundary.

## 4. Coordinate semantics

This boundary requires an explicit off-by-one invariant.

BCF stores its encoded POS as a zero-based integer, while the VCF logical POS is one-based. `pysam.VariantRecord.pos` exposes the logical one-based VCF coordinate. RefCompat must copy that provider-normalized logical `pos` unchanged into `VcfRefRecord.position`.

The existing REF evaluator then performs its already-pinned conversion:

```text
start = POS - 1
end   = start + len(REF)
```

M8 must not subtract one in the BCF inspector and then allow the existing evaluator to subtract one again. Integration coverage must include a known BCF record whose FASTA match would fail under either a +1 or -1 error.

Telomere sentinel and ordinary REF-span semantics remain the existing RCHECK-050 semantics after decoding; BCF encoding does not create a new coordinate system for reasoning.

## 5. Exhaustive traversal and indexes

BCF record traversal remains exhaustive and sequential in source-file order. The compatibility path must not require CSI/tabix merely because BCF supports indexing.

`iter_vcf_ref_records()` continues to emit zero-based RefCompat file ordinals for traceability while preserving each record's native logical one-based POS. File ordinal and genomic coordinate remain separate concepts.

A provider error during open or sequential iteration is normalized through the existing VCF/BCF inspection error boundary and is never converted into biological incompatibility.

## 6. Reuse of RCHECK-050 reasoning

Once BCF has been decoded into the existing logical observations, the following behavior must be identical to VCF:

- actual `CHROM` usage creates mandatory sequence-presence requirements;
- used declared contig lengths create mandatory length requirements;
- syntactically valid used-contig MD5 declarations create mandatory sequence-identity requirements and may support conservative verified cross-name binding under the existing full-anchor uniqueness/length rules;
- exhaustive `REF` comparison is authoritative pair-derived evidence against the explicitly selected FASTA anchor;
- any directly proven REF mismatch remains a Tier-A hard contradiction;
- unresolved sequence or out-of-bounds-only cases remain unresolved rather than becoming fabricated contradiction/support;
- mismatch distribution uses the existing threshold-free `NONE` / `ISOLATED` / `LOCALIZED` / `DISTRIBUTED` / `SYSTEMATIC` / `UNCLASSIFIED` interpretation;
- generic bundle reasoning, evidence aggregation, findings, conditions, conflict cores, and the four compatibility verdicts remain unchanged.

No BCF record may receive a stronger or weaker scientific result solely because its logical VCF record was encoded as BCF rather than text.

## 7. Scope, binding, and profile behavior

Explicit evaluation scope retains the same semantics for BCF resources as for VCF resources. Scope may limit the requested evaluation but must not manufacture sequence-identity uniqueness or hide alternatives needed by a complete-anchor proof.

Verified BCF cross-name bindings reuse the same declared-MD5 and profile-authorized `SequenceBinding` machinery as VCF. Familiar names remain insufficient without the existing evidence requirements.

The UCSC preflight profile may consume a BCF peer through the same variant path only after the UCSC provider target is independently content-bound to the selected FASTA anchor. BCF encoding must not increase the authority of provider naming evidence.

## 8. Stable report and schema versioning

M7 froze `ResourceKind` as a closed enum in the stable report family. Its versioning rules explicitly classify adding or removing an existing enum value as a MAJOR schema change.

M8 must honor that promise. When `ResourceKind.BCF = "bcf"` becomes serializable:

- current stable schema advances from `1.1.0` to `2.0.0`;
- exact `1.0.0` and `1.1.0` schema files and known-answer fixtures remain retained and unchanged;
- schema `2.0.0` may otherwise preserve the existing report body shape while widening the resource-kind enum;
- a BCF report must identify its resource kind as `bcf`, not masquerade as `vcf` to remain acceptable to a `1.x` validator;
- exact-version schema validation remains the rule;
- non-BCF reports emitted by the current serializer also identify the current schema version rather than pretending to be old-version reports.

The provisional draft report revision also advances when BCF becomes emit-able because the allowed resource-kind value set changes even if no object field is added.

A future decision to offer explicit down-rendering to an older stable schema is separate work; M8 does not silently relabel current reports as `1.x`.

## 9. Error and analysis-status boundary

Malformed/unreadable BCF, parser incompatibility, or declared-vs-detected format mismatch is an input/execution problem, not an `INCOMPATIBLE` biological verdict.

If a future production `CompatibilityReport` assembler handles such failures, it must preserve the M7 separation between `INVALID_INPUT`, `PARTIAL`, and scientific compatibility. M8 does not create format-specific workflow exit codes.

## 10. Fixture and validation strategy

M8 should use small synthetic BCF inputs whose logical VCF source is transparent. Prefer generating BCF through the pinned pysam/HTSlib boundary inside integration setup or checking in clearly redistributable synthetic fixtures with documented provenance.

Coverage must include at least:

- VCF/BCF declared-kind versus detected-encoding mismatch in both directions;
- equivalent VCF and BCF logical inputs producing equivalent context and REF facts apart from resource kind/provenance;
- a coordinate-sensitive exact REF match that detects BCF POS off-by-one mistakes;
- declared contig MD5 cross-name binding;
- direct REF mismatch/incompatible output;
- unresolved sequence/indeterminate output;
- explicit scope behavior;
- UCSC-profile authoritative-alias reuse;
- stable schema `2.0.0` acceptance of `bcf` and rejection by retained exact `1.x` schemas;
- retained exact `1.0.0` and `1.1.0` schema/fixture immutability;
- deterministic stable JSON, human rendering, and workflow exit behavior.

The ordinary test gate remains network-independent.

## 11. Non-goals

M8 does not:

- add BCF1 support;
- inspect genotype/sample compatibility;
- validate INFO/FORMAT field semantics beyond what HTSlib must decode to expose the logical record;
- validate CSI/tabix index integrity;
- infer reference identity from BCF dictionary indexes or binary layout;
- add BED support;
- add reference-free comparison;
- introduce a portable reference manifest;
- freeze the general profile/plugin interface;
- perform liftover, renaming, allele rewriting, normalization, filtering, repair, or mutation.

## 12. Review checkpoints

After the first compatible and incompatible BCF end-to-end report paths are implemented, perform an internal scientific/API review focused on:

- encoding mismatch handling;
- coordinate normalization;
- VCF/BCF logical parity;
- accidental BCF-specific evidence/verdict behavior;
- stable schema major-version correctness and retained `1.x` immutability.

Close M8 only after an adversarial exit suite and independent milestone-boundary review are clean.
