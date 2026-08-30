# display-report — Roadmap

This layer's roadmap. Cross-repo coordination and the pipeline-wide
sequencing live in
[color-wrangler](https://github.com/Fuse-Technical-Group/color-wrangler);
workstreams there are addressed by slug in backticks and resolve in
that repository's ROADMAP.md.

## Contract-driven analysis §road:contract-analysis-impl

The analysis reads the encoding from the file instead of assuming PQ
at ten bits.


### Report an SDR 12-bit session §road:sdr-12bit-report

Produce a report from a 12-bit gamma bench session measured on the
bench rig rather than against the display double.
§spec:contract-analysis, §spec:report-rendering.

**Verify:** a 12-bit gamma file and a 10-bit PQ file each analyze
correctly and neither is silently interpreted as the other; the report
names the protocol and transfer function it was measured under; a file
declaring an unimplemented contract is refused by name; a hybrid
file's reconstructed rows are named and excluded from analyses needing
a measured spectrum.
