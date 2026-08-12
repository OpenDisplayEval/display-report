# display-report

display-report measures displays and produces a standardized, open-source fidelity
report. It sends hundreds of known code values to a display, captures the
resulting light output with a spectroradiometer, and compares the two to
quantify reproduction accuracy.

## Where this fits

LED display calibration is a complex, per-pixel process handled by LED
processors. display-report does not calibrate — it
**reports on the results** of that vendor calibration. The more accurate a display's
native calibration is, the easier it is for downstream tools to
build on top of it — creative LUTs, colour space transforms, and camera-match
workflows all benefit from a predictable starting point.

## Why open-source measurement reports?

Traditional display spec sheets describe _capability_ — peak brightness, gamut
coverage, contrast ratio. They do not show whether a display tracks its target
EOTF, holds a neutral grey scale, or reproduces colours accurately inside the
gamut boundary. The numbers are best-case snapshots, not distributions, and they
are not independently verifiable.

display-report's report format is open source. The metrics it presents, the
visualizations it uses, the tolerance thresholds it applies, and the way it
surfaces information to non-specialist readers are all visible in the codebase.
Anyone can review those design choices, propose improvements, or adapt the
format for their own context.

The report summarizes accuracy as distributions (mean + 95th percentile), not
cherry-picked values. Results are comparable across vendors and display
technologies because the report format and analysis are identical for every
display measured.

## Reading the report

The report is a single-page PDF. Each section uses a traffic-light tolerance
scheme: green indicates performance within one JND (just noticeable difference),
yellow indicates marginal performance, and red indicates clearly visible error.

### Summary statistics

The top of the report shows aggregate colour difference metrics:

- **Mean dE 2000** and **95th percentile** — perceptual colour difference
  weighted for typical viewing conditions. Good for judging how a human observer
  would perceive the display.
- **Mean dE ITP** and **95th percentile** — perceptual colour difference in
  ICtCp space (ITU BT.2124). More sensitive than dE 2000, especially at low
  luminance. Good for understanding physical error across the full dynamic
  range.
- **Reflectance** and **glossiness ratio** (if supplied) — 45:0 and 45:45
  reflectance factors that determine real-world black level and contrast ratio
  under ambient light.

### Chromaticity error (CIE u'v')

Shows the measured colour error plotted on the CIE 1976 u'v' chromaticity
diagram alongside MacAdam ellipses. The diagram clusters all test patches into
14 regions and draws an arrow from each cluster centre showing the mean error
direction and magnitude, magnified 10x (same scale as the ellipses). If an arrow
is roughly the same size as the nearby ellipse, the error in that region is
approximately 1 standard deviation of colour matching (SDCM).

Three gamut outlines are overlaid for reference: P3-D65 (red dashed), BT.2020
(green dashed), and the display's estimated native gamut (black solid).

### PQ EOTF performance

Plots the ideal PQ transfer function (red curve) against measured grey-ramp
luminance values (blue dots) on log-log axes. The x-axis shows 10-bit code
values; the y-axis shows luminance in cd/m² (nits). Two reference lines mark 1000 cd/m² (nits)
(teal) and the display's measured maximum luminance (purple). A display tracking PQ
correctly will have its dots fall directly on the red curve up to the display
maximum, then clip above it.

### White point stability

Two vertically stacked subplots show how the display's white point drifts across
luminance levels:

- **CCT** (top) — correlated colour temperature in Kelvin. The target is D65
  (6504 K). Drift above the line means cooler/bluer; below means
  warmer/yellower.
- **Duv** (bottom) — green/magenta offset from the Planckian locus (CIE 1960).
  Positive values shift green; negative values shift magenta.

Both subplots use tolerance bands derived from ANSI C78.377 SDCM values: green
is within 1 SDCM of D65, yellow within 4 SDCM, and red beyond 6 SDCM.

### Brightness error (dI)

Plots per-patch brightness error derived from the intensity channel of ICtCp.
Positive values mean the display is brighter than expected; negative values mean
darker. Each dot is coloured by its test patch RGB value, making it easy to spot
whether specific colours or luminance ranges are affected.

Tolerance bands: green for less than 1 JND, yellow for 1-8 JND, red for greater
than 8 JND. The y-axis uses a symmetric log scale.

### Chromatic error

Plots the combined hue and saturation error from ICtCp, with brightness removed.
This isolates colour reproduction error from brightness error. Only the
magnitude is shown (no sign), so all values are zero or positive.

Same tolerance scheme as brightness error: green below 1 JND, yellow 1-8, red
above 8. Dots are coloured by test patch RGB value.

### Tolerance reference

| Band   | Threshold | Meaning                                        |
| ------ | --------- | ---------------------------------------------- |
| Green  | < 1 JND   | Not perceptible under normal viewing           |
| Yellow | 1 - 8 JND | Marginal — may be visible in demanding content |
| Red    | > 8 JND   | Clearly visible distortion                     |

A JND (just noticeable difference) is the smallest colour or brightness change a
typical observer can detect under controlled conditions. In practice, moving or
complex imagery raises the detection threshold, so yellow-zone errors are often
acceptable.

## Quick start

```bash
git clone https://github.com/OpenDisplayEval/display-report.git
cd display-report
uv sync
uv run display-report measure --max-luminance 1500 --bit-depth 10 --save-directory ./measurements
uv run display-report analyze ./measurements/<file>.csmf
```

See [USAGE.md](USAGE.md) for hardware setup, full CLI reference, and development
instructions.

## License

See [LICENSE](LICENSE) for details.
