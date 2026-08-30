# display-report — Specification

This layer's specification. The pipeline-wide architecture and the
artifact chain live in
[color-wrangler](https://github.com/Fuse-Technical-Group/color-wrangler);
sections there are addressed by slug in backticks and resolve in that
repository's SPEC.md.

## Scope §spec:scope

*Status: complete*

display-report reads a measurement file and reports on it. It opens no
serial port and no DeckLink, imports no device driver, and needs no
rig: a machine that reports needs a file and nothing else.

One tool touches instruments and signal hardware, and it is
display-measure (`§spec:session-ownership`). This repository consumes
what that tool emits.

**Why the validator owns no measure path.** display-report validates
either this pipeline or a display-side calibration, and its value is
that it has no stake in the correction under test. A second measure
path living inside it would be an ungated one — the session gates
(`§spec:signal-contract`) live in display-measure, and a path that
skips them measures a display in an undeclared state and renders a
well-formed report of it. That is the failure the gates exist to
prevent, reintroduced in the repository whose independence is the
reason they matter.

**Reproducibility is a property of the seam, not of a bundled loop.**
A third party reproduces a report by writing the seam file from
whatever instrument they own and running this analysis over it. The
format and the analysis are what make the report reproducible; a
second device path inside the validator was never what delivered it.

Not owned here: instrument and signal-generator access
(display-measure), OCIO semantics and config generation
(ocio-display-gen), the show manifest and the promotion decision
(color-wrangler).

## Report input §spec:report-input

*Status: not started*

The report's input is one file: the measurement seam file
(`§spec:measurement-seam`), carrying the measurements, the spectra
behind them, the protocol that produced them, the declared signal
contract, the attested panel state, and the hash chain.

Analysis is a pure function of that file. Two runs over one file
produce one report.

**The file states what it is; the reader does not guess.** A report
names the protocol and the transfer function it was measured under,
reading both from the file. A file measured at one contract is never
silently analyzed as another — where the file does not say, the
analysis refuses rather than assuming, because an assumed encoding
produces a wrong number in a plausible-looking chart and no check
catches it.

**Rows without a measured spectrum are legible as such.** A
disciplined session reads its dark end with a colorimeter, and those
rows carry a reconstructed spectrum or none (`§spec:spectral-retention`).
An analysis needing a measured spectrum reports which rows it excluded
and why, rather than treating a scaled estimate as a measurement.

## Contract-driven analysis §spec:contract-analysis

*Status: not started*

Transfer function and bit depth come from the file's declared signal
contract. Neither is hardcoded, and neither is inferred from the data.

**Why this is the section that matters most.** The analysis linearizes
code values to compare measured light against intent, and linearizing
under the wrong transfer function is an error nothing downstream can
detect. A 12-bit code value linearized as though it were 10-bit PQ
yields a plausible curve, a plausible ΔE, and a wrong report. The
reference format assumed PQ at ten bits because that is what the
displays in front of it ran; the bench runs 12-bit RGB at a gamma
contract. Both are valid contracts, the file states which, and the
analysis reads it.

Observable behavior:

- The analysis linearizes at the transfer function and bit depth the
  file declares.
- A report states the contract it read.
- A 12-bit gamma file and a 10-bit PQ file each analyze correctly, and
  neither is interpreted as the other.
- A file declaring a contract the analysis does not implement is
  refused by name, not approximated.

**Code values are normalized, not assumed 10-bit.** Quantization
behavior — the step a report shows at the dark end — is a function of
the declared depth. A fixed 1023 denominator is the same error as a
fixed transfer function, quieter.

## Report rendering §spec:report-rendering

*Status: not started*

The report is a rendered page whose plots are parameterized by the
declared contract: transfer-function axes, their tick placement, and
the code-value range all follow from what the file says, not from a
constant.

**Why the axes are part of the contract work and not cosmetics.** An
axis labelled "10-bit Code Value" under a 12-bit session is a false
statement about the measurement, printed on the artifact a human
judges from. Plot bounds derived from a hardcoded PQ inverse place the
measured points wrongly on a gamma session's page — the chart renders,
and it is wrong.

The page's content — what figures it carries and what they
discriminate — is specified in `§spec:report-metrics`.

## Programmatic surface §spec:report-api

*Status: not started*

Analysis and rendering are importable: a caller supplies a file path
and receives the analysis, and supplies the analysis and receives the
rendered report as bytes. The command-line entry point is a caller
like any other and holds no logic of its own.

**Why an importable surface.** The operator's surface is a browser
served from the session host (`§spec:web-ui`), and it generates the
report from a loaded artifact without the operator leaving the page or
learning a second tool. A caller reduced to shelling out to a CLI and
scraping a path cannot report a failure precisely.
display-report remains the only thing that decides what a report says;
which surface invokes it is a separate question.

Importing this package costs nothing beyond the standard library —
public names resolve lazily — so a caller that only renders never pays
for what it does not use.
