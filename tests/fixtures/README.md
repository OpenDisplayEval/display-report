# Fixtures

## `hybrid_session.csmf`

The seam file (§spec:report-input), written by the tool that writes it in
production rather than built here:

```sh
display-measure characterize --out hybrid_session.csmf --instrument doubles-hybrid
```

72 rows from the `color-wrangler/characterize/3` protocol against
display-measure's deterministic display double, under a GAMMA 2.4 contract.
71 rows are spectral; the black row is colorimetric and carries no spectrum
at all, because a disciplined session reads its dark end with a colorimeter
(§spec:spectral-retention). That row is the point of the fixture — it is the
shape the analysis has to tolerate, and no hand-built file would have
produced it.

Regenerate it from display-measure when the protocol or the seam format
changes. Do not hand-edit it.

## `spectral_session.csmf`

A spectroradiometer-only session, every row spectral including black:

```sh
display-measure characterize --out spectral_session.csmf --instrument doubles
```

The analysis filters patches by their signal-to-noise ratio against the spread
of the black *spectra* (§spec:report-input). A hybrid session routes black to a
colorimeter, which has no spectrum, so that floor cannot be computed and the
analysis refuses. This fixture is the case that can be analyzed;
`hybrid_session.csmf` is the case that shall be refused, and both are worth
holding onto.

## report_session.csmf

A report-grade session from the doubles:

```sh
display-measure characterize --instrument doubles --suite report \
  --assume-attested --out report_session.csmf
```

795 rows across every measurement block plus the `first-light/1` probe.
This is the fixture the analysis tests read, because it is the
measurement this analysis declares it requires
(`display_report.requires`).

## hybrid_report_session.csmf

A report-grade session through the disciplined-colorimeter path:

```sh
display-measure characterize --instrument doubles-hybrid --suite report \
  --assume-attested --out hybrid_report_session.csmf
```

Its dark rows are colorimetric and carry no spectrum, because a
disciplined session reads its dark end with a colorimeter -- which is
exactly the shape that broke the analysis, and exactly what no
hand-rolled fixture would have produced.

## spectral_session.csmf, hybrid_session.csmf

Verify-grade sessions, kept because they exercise the refusal. Both
carry `anchors`, `response` and `additivity` and no more, so the
analysis refuses them by naming the blocks they lack — the case that
matters most and the one no hand-built fixture would produce.
