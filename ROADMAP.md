# display-report — Roadmap

This layer's roadmap. Cross-repo coordination and the pipeline-wide
sequencing live in
[color-wrangler](https://github.com/Fuse-Technical-Group/color-wrangler);
workstreams there are addressed by slug in backticks and resolve in
that repository's ROADMAP.md.

## Contract-driven analysis §road:contract-analysis-impl

The analysis reads the encoding from the file instead of assuming PQ
at ten bits. Every workstream here is blocked on display-measure
emitting the seam file (`§road:emit-csmf` there); unblocked when a
file written by `display-measure characterize` carries the provenance
block.

### Read the seam file §road:read-seam-file

Load the measurement seam file and its provenance block — declared
contract, protocol name, attested panel state, input hashes — in
`display_report/analysis.py`, refusing a file whose provenance block
is absent or unreadable. §spec:report-input.

### Read the contract §road:analysis-reads-contract

Take transfer function and bit depth from the declared contract rather
than the hardcoded `st_2084` and 1023 denominators in
`display_report/analysis.py`, refusing a declared contract the
analysis does not implement. §spec:contract-analysis. Depends on
§road:read-seam-file.

### Name the rows without a measured spectrum §road:spectral-row-provenance

Carry each row's spectral provenance through the analysis and report
which rows an analysis excluded and why, in
`display_report/analysis.py`. §spec:report-input. Depends on
§road:read-seam-file.

### Render at the declared contract §road:pdf-contract-axes

Parameterize the transfer-function plots, their tick placement, axis
labels and code-value bounds by the declared contract in
`display_report/pdf.py`. §spec:report-rendering. Depends on
§road:analysis-reads-contract.

### Report an SDR 12-bit session §road:sdr-12bit-report

Produce a report from a 12-bit gamma bench session and state the
contract it read on the page. §spec:contract-analysis,
§spec:report-rendering. Depends on §road:pdf-contract-axes.

**Verify:** a 12-bit gamma file and a 10-bit PQ file each analyze
correctly and neither is silently interpreted as the other; the report
names the protocol and transfer function it was measured under; a file
declaring an unimplemented contract is refused by name; a hybrid
file's reconstructed rows are named and excluded from analyses needing
a measured spectrum.

## Report surface §road:report-surface

What the operator UI calls. The browser generates the report from a
loaded artifact (`§spec:web-ui`), and the consuming half lives in
color-wrangler (`§road:ui-report` there).

### Render the report to bytes §road:report-to-bytes

Add the importable surface returning the rendered report as PDF bytes
for a caller that supplies an analysis, in `display_report/pdf.py` and
`display_report/__init__.py`, and reduce
`display_report/scripts/analyze_display_measurements.py` to a caller
of it. §spec:report-api.

**Verify:** an in-process caller produces report bytes from a file
path with no subprocess and no temporary file it did not choose;
`display-report analyze` writes the same bytes for the same input.
