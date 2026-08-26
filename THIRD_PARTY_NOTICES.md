# Third-party notices

RefCompat includes small third-party test fixtures and known-answer values used
only to verify standards-compatible behavior. RefCompat's own source code is
licensed under Apache-2.0; the materials identified below remain under their
upstream licenses.

## refget v0.12.0 compliance fixture

The following RefCompat test material is derived from the `refget` v0.12.0
compliance fixtures:

- `tests/fixtures/fasta/ga4gh_base.fa` reproduces `test_fasta/base.fa`.
- Known-answer refget/SeqCol digest values asserted in
  `tests/integration/test_refget_identity.py` are taken from
  `test_fasta/test_fasta_digests.json`.

Upstream project: <https://github.com/refgenie/refget>

Upstream fixture version: `v0.12.0`

- <https://github.com/refgenie/refget/blob/v0.12.0/test_fasta/base.fa>
- <https://github.com/refgenie/refget/blob/v0.12.0/test_fasta/test_fasta_digests.json>

License: BSD-2-Clause

Copyright 2024 Nathan Sheffield

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## HTSlib `faidx(5)` example

The following RefCompat fixtures reproduce the FASTA and Unix-style FAI example
from HTSlib's `faidx(5)` manual page:

- `tests/fixtures/fai/htslib_example.fa`
- `tests/fixtures/fai/htslib_example.fa.fai`

Upstream project: <https://github.com/samtools/htslib>

Upstream manual: <https://www.htslib.org/doc/faidx.html>

Pinned source used for attribution: <https://github.com/samtools/htslib/blob/1.22/faidx.5>

License: MIT/Expat

Copyright (C) 2013, 2015, 2018 Genome Research Ltd.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
