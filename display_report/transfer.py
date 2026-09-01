"""Transfer fidelity and quantization headroom (§spec:gamut-visualization).

Two questions about the same ramp. Does the display follow the transfer
function its contract declares, and is the encoding precise enough that
a single code step stays invisible?

**Fidelity is measured; headroom is derived.** The protocol's rungs are
half-octave spaced — 16, 24, 32, 48 — so measured-against-declared is a
direct comparison at each rung, but a *code step* is never measured.
Headroom therefore fits the ramp and differentiates it, which answers
"given the response we measured, would a one-code step show" rather
than "we measured a step that shows". The view says so; a plot that
implied otherwise would be claiming a measurement nobody took.

**Why Barten.** Barten's contrast sensitivity function is the threshold
the eye can just detect, and it is what PQ was derived against. Using it
here asks the same question of any encoding — a gamma contract at 12
bits, a PQ contract at 10 — rather than asking whether a display tracks
one particular curve. That generality is the point: it is the metric
that survives changing the contract (§road:lut-transfer-probe).

Its threshold is not a hard line. Barten's model takes viewing distance,
field size and spatial frequency, and the value used here is the peak of
the sensitivity curve — the most favorable spatial frequency, which is
the conservative choice for a banding question. Real content is moving
and complex, which raises the detection threshold, so a rung marginally
over the line is a caution rather than a verdict.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

__all__ = [
    "HeadroomRow",
    "barten_threshold",
    "fitted_exponent",
    "gamma_step_contrast",
    "pq_step_contrast",
    "quantization_headroom",
    "transfer_residuals",
]

Ramp = list[tuple[int, float]] | tuple[tuple[int, float], ...]

# Readings at or under this are instrument noise rather than the display's
# response; fitting through them fits the noise (§road:instrument-floors).
FLOOR = 0.001

# The spatial frequency Barten's sensitivity peaks near, cycles per
# degree. Taken as a fixed observation condition rather than a knob: the
# peak is where a step is easiest to see, so judging there is the
# conservative choice.
PEAK_CPD = 4.0

# Angular field size, degrees. Barten's model is sensitive to it, and a
# large display fills far more of the visual field than a desktop one; 60° is
# colour-science's default and a reasonable stand-in for a viewer facing
# a large surface. Stated because it is an observation condition, not a
# property of the display.
FIELD_SIZE_DEGREES = 60

# The wire format the protocol drives (MEASUREMENT.md). A step at any
# other depth is expressed in multiples of one of these codes.
MEASURED_BIT_DEPTH = 12


@dataclass(frozen=True)
class HeadroomRow:
    """One rung's quantization step against the threshold to see it."""

    code: int
    luminance: float
    step_contrast: float
    threshold: float

    @property
    def headroom(self) -> float:
        """Step over threshold. Above 1.0 the step is predicted visible."""
        return self.step_contrast / self.threshold

    @property
    def above_threshold(self) -> bool:
        """The step exceeds the detection threshold at this level.

        Not the same as "visible". Barten's threshold is for a sinusoidal
        grating at the spatial frequency the eye is best at, viewed
        steadily — the most favorable detection condition there is.
        Finding a one-code step in a gradient is harder, and moving
        content harder still. A rung over the line is where banding
        could show, not a claim that it does.
        """
        return self.headroom > 1.0


def _usable(ramp: Ramp, floor_code: int = 0) -> list[tuple[int, float]]:
    return [(c, y) for c, y in ramp if y > FLOOR and c >= floor_code]


def fitted_exponent(ramp: Ramp, peak: float, *, floor_code: int = 768) -> float:
    """The power-law exponent the ramp fits above `floor_code`.

    Fitted rather than assumed, and reported with the window it was
    fitted over, because on this bench the exponent slides with the
    window — which is how a response says it is not a power law at all,
    as against a power law of some other exponent.
    """
    rows = _usable(ramp, floor_code)
    if len(rows) < 2:
        return float("nan")
    xs = [math.log(c / ramp[-1][0]) for c, _ in rows]
    ys = [math.log(y / peak) for _, y in rows]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    return numerator / denominator if denominator else float("nan")


def transfer_residuals(
    ramp: Ramp, peak: float, *, gamma: float
) -> list[tuple[int, float]]:
    """Fractional excess of measured luminance over a declared power law.

    Positive means the display emits more light than its contract predicts.
    Normalised to peak, so full drive is exact by construction and the
    residual describes the shape of the curve rather than its scale.
    """
    full = ramp[-1][0]
    out = []
    for code, measured in ramp:
        predicted = peak * (code / full) ** gamma
        out.append((code, (measured - predicted) / predicted if predicted else 0.0))
    return out


def barten_threshold(luminance: float, *, cycles_per_degree: float = PEAK_CPD) -> float:
    """Just-detectable Michelson contrast at an adaptation luminance.

    The reciprocal of Barten's contrast sensitivity. Delegated to
    colour-science rather than reimplemented: the model has a dozen
    parameters and getting one wrong yields a plausible curve that is
    quietly wrong.
    """
    # Deferred: colour is a heavy import that the artifact view does not
    # need until a transfer plot is asked for.
    from colour.contrast import (
        contrast_sensitivity_function_Barten1999,
        pupil_diameter_Barten1999,
        retinal_illuminance_Barten1999,
    )

    # The model works in retinal illuminance, so luminance goes through
    # the pupil first: sensitivity at 1000 cd/m² differs from sensitivity
    # at 1 partly because the pupil closes. Passing luminance where
    # trolands are expected would give a plausible curve that is wrong by
    # two orders of magnitude at the dark end.
    level = max(luminance, 1e-6)
    diameter = pupil_diameter_Barten1999(level, FIELD_SIZE_DEGREES)
    illuminance = retinal_illuminance_Barten1999(level, diameter)
    sensitivity = float(
        contrast_sensitivity_function_Barten1999(
            u=cycles_per_degree, E=illuminance, X_0=FIELD_SIZE_DEGREES
        )
    )
    return 1.0 / sensitivity if sensitivity > 0 else float("inf")


def quantization_headroom(
    ramp: Ramp, *, bit_depth: int = MEASURED_BIT_DEPTH
) -> list[HeadroomRow]:
    """Per-rung contrast of a one-code step, against the threshold to see it.

    The step is derived: adjacent rungs are many codes apart, so the
    local slope between them stands in for the derivative, scaled to a
    single code. That is interpolation between measured points, and the
    view labels it as such.

    `bit_depth` asks the question of a different encoding than the one
    measured. The ramp is driven at 12-bit codes, so a step at 10 bits
    is four of them: this is how one contract's quantization gets
    compared against another's on the same measured display, which is what
    §road:lut-transfer-probe needs to settle whether a PQ-like LUT
    contract beats the 12-bit gamma one.
    """
    codes_per_step = 2.0 ** (MEASURED_BIT_DEPTH - bit_depth)
    rows: list[HeadroomRow] = []
    for (low_code, low), (high_code, high) in pairwise(ramp):
        if low <= FLOOR or high <= FLOOR or high_code == low_code:
            continue
        # Luminance per code across this span, then one step's worth of
        # it as a Weber contrast against the local level.
        per_code = (high - low) / (high_code - low_code)
        level = (high + low) / 2.0
        rows.append(
            HeadroomRow(
                code=low_code,
                luminance=level,
                step_contrast=abs(per_code) * codes_per_step / level
                if level
                else float("inf"),
                threshold=barten_threshold(level),
            )
        )
    return rows


def pq_step_contrast(
    luminances: list[float], *, bit_depth: int
) -> list[tuple[float, float]]:
    """A one-code PQ step as Weber contrast, per adaptation luminance.

    The reference curve the measured display is read against, in the same
    role Rec.709 and DCI-P3 play on the chromaticity diagram: a known
    quantity, not a target. PQ is the useful one to draw because it was
    derived against this very threshold — so 12-bit PQ tracks under
    Barten by construction, and 10-bit PQ crossing it in the shadows is
    the textbook result rather than a defect of any display.

    Ideal in the sense that only the encoding is modelled: a display
    tracking PQ exactly, with no panel non-linearity, dither, or noise.
    """
    # Deferred with the rest of colour: the artifact view should not pay
    # for it until a transfer plot is asked for.
    from colour.models import eotf_inverse_ST2084, eotf_ST2084

    step = 1.0 / (2.0**bit_depth - 1.0)
    out: list[tuple[float, float]] = []
    for level in luminances:
        if level <= 0.0:
            continue
        code = float(eotf_inverse_ST2084(level))
        higher = float(eotf_ST2084(min(code + step, 1.0)))
        out.append((level, (higher - level) / level))
    return out


def gamma_step_contrast(
    luminances: list[float], *, peak: float, gamma: float, bit_depth: int
) -> list[tuple[float, float]]:
    """A one-code step under a power law, as Weber contrast.

    The contract this session actually drove, drawn beside the PQ
    references so the measured curve can be read against the encoding it
    was made under rather than only against encodings it was not.

    Analytic rather than sampled: under L = peak·(c/c_max)^gamma the
    Weber contrast of one code is exactly gamma/c, so there is nothing
    to approximate.

    A power law spends its code space at the top, which is the whole
    reason this curve rises so steeply in the shadows: the same one code
    buys a far larger fraction of the level down there.
    """
    top = 2.0**bit_depth - 1.0
    out: list[tuple[float, float]] = []
    for level in luminances:
        if level <= 0.0 or peak <= 0.0:
            continue
        code = top * (level / peak) ** (1.0 / gamma)
        if code > 0:
            out.append((level, gamma / code))
    return out
