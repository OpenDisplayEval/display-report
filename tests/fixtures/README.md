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
