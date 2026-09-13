# Milestone 8 fixtures

Milestone 8 introduces BCF2 as a distinct resource encoding while preserving the
existing VCF logical compatibility model.

`stable-bcf-invalid-input-report-2.0.0.json` is the first schema-2.0.0 known
answer. It deliberately carries `analysis.status = invalid_input` and no
scientific result: Slice 2 pins the new `bcf` resource-kind wire value and exact
schema boundary independently of the Slice 3 RCHECK-050 scientific-parity proof. The same
payload is rejected by retained exact schema 1.1.0 because that schema's closed
resource-kind enum predates BCF support.

Real BCF observation fixtures are generated during integration tests through the
pinned pysam/HTSlib provider boundary so no binary fixture provenance is hidden.

Slice 4 keeps the executable BCF report cases generated at test time rather than checking in
binary BCF fixtures. The reporting integration covers scoped conditional success, hard REF
incompatibility, unresolved-sequence indeterminacy, UCSC authoritative-alias resolution, and
both declared/detected VCF↔BCF mismatch directions through exact schema 2.0.0, human rendering,
and workflow exits.

Slice 5 internal review does not rewrite any retained stable fixture. Tests pin the exact bytes of the final-M7 `1.0.0`/`1.1.0` schemas and stable known answers and prove schema `2.0.0` is exactly the `1.1.0` contract plus its new version identity and the single `bcf` resource-kind value.

External-review follow-up keeps binary corruption fixtures generated at test time: integration tests write real BCF and BGZF-compressed VCF through pinned pysam, corrupt an interior BGZF checksum, and require the shared inspector to retain the normalized parse/input boundary even if provider close also fails. No corrupted binary fixture is checked into the repository.
