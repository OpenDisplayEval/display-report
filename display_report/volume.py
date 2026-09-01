"""The reproducible set as a solid (§spec:gamut-visualization).

A chromaticity triangle is one slice of a three-dimensional set, and it
hides what decides whether a colour is usable: the luminance it is
available at. This bench display can make its red primary — at 422 cd/m²,
not at the 1483 its white reaches. The triangle asserts the first and
says nothing about the second, which is how a display can look capable
on paper and clip in use.

**What licenses the model.** The solid is computed, not measured: every
point is `XYZ(r,g,b) = R(r) + G(g) + B(b)` from the three measured
channel responses. That is a fair description of a display whose
channels add, and a fiction on one whose channels do not — so
`gamut_solid` checks the artifact's own additivity first and refuses
rather than drawing a capability nobody measured. This display sums to
within 0.75% of its measured white, which is what earns the picture.

**Why CIELAB.** §spec:report-metrics asks for a luminance-inclusive
volume in a perceptually uniform space, so that equal distances in the
picture mean roughly equal perceived differences and the solid's shape
carries information rather than the space's distortion. L* is relative
to the display's own white, which is the right reference for judging
what this display can do against itself; absolute luminance stays on
the 2D view and in the extent figures.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "NonAdditiveDisplay",
    "SolidExtent",
    "channel_response",
    "gamut_solid",
    "solid_extent",
]

XYZ = tuple[float, float, float]
Ramp = list[tuple[int, XYZ]]

# How far the channel sum may sit from measured white before the
# additive model stops describing the display. Generous against a bench
# that closes to 0.75%: the check is for a display that is not additive,
# not a tolerance on one that is.
MAX_ADDITIVITY_ERROR = 0.05


class NonAdditiveDisplay(RuntimeError):
    """The channels do not sum to white, so the solid would be invented."""


@dataclass(frozen=True)
class SolidExtent:
    """The corners of the solid worth quoting beside the picture."""

    peak_luminance: float
    red_luminance: float
    green_luminance: float
    blue_luminance: float


def channel_response(ramp: Ramp) -> Callable[[float], XYZ]:
    """A channel's measured XYZ at any code, linearly between rungs.

    Linear rather than fitted: the rungs are dense enough through the
    range that matters, and a fit would smooth over the shape the
    measurement is there to capture.
    """
    codes = [c for c, _ in ramp]
    values = [v for _, v in ramp]

    def at(code: float) -> XYZ:
        if code <= codes[0]:
            return values[0]
        if code >= codes[-1]:
            return values[-1]
        i = bisect_left(codes, code)
        lo_c, hi_c = codes[i - 1], codes[i]
        lo, hi = values[i - 1], values[i]
        t = (code - lo_c) / (hi_c - lo_c)
        return (
            lo[0] + t * (hi[0] - lo[0]),
            lo[1] + t * (hi[1] - lo[1]),
            lo[2] + t * (hi[2] - lo[2]),
        )

    return at


def _check_additive(ramps: dict[str, Ramp], white_luminance: float) -> None:
    total = sum(ramps[c][-1][1][1] for c in ("red", "green", "blue"))
    if total <= 0:
        raise NonAdditiveDisplay("the channels measure no light")
    error = abs(white_luminance - total) / total
    if error > MAX_ADDITIVITY_ERROR:
        raise NonAdditiveDisplay(
            f"the channels sum to {total:.4g} cd/m² against a measured white "
            f"of {white_luminance:.4g} — {error * 100:.1f}% apart, past the "
            f"{MAX_ADDITIVITY_ERROR * 100:.0f}% an additive model describes. "
            "A solid drawn from these channels would assert a capability the "
            "additivity measurement contradicts"
        )


def _cube_surface(samples: int) -> list[tuple[float, float, float]]:
    """Points on the RGB cube's six faces, normalised 0-1.

    The surface alone: the solid's boundary is the cube's boundary under
    an additive map, so filling the interior would multiply the point
    count without adding a fact.
    """
    grid = [i / (samples - 1) for i in range(samples)]
    points: set[tuple[float, float, float]] = set()
    for a in grid:
        for b in grid:
            for fixed in (0.0, 1.0):
                points.add((fixed, a, b))
                points.add((a, fixed, b))
                points.add((a, b, fixed))
    return sorted(points)


def gamut_solid(
    ramps: dict[str, Ramp], *, white_luminance: float, samples: int = 12
) -> list[XYZ]:
    """The reproducible set's boundary, as absolute XYZ.

    Refuses a display whose channels do not sum to its measured white.
    """
    _check_additive(ramps, white_luminance)
    full = ramps["red"][-1][0]
    response = {c: channel_response(ramps[c]) for c in ("red", "green", "blue")}
    solid: list[XYZ] = []
    for r, g, b in _cube_surface(samples):
        red = response["red"](r * full)
        green = response["green"](g * full)
        blue = response["blue"](b * full)
        solid.append(
            (
                red[0] + green[0] + blue[0],
                red[1] + green[1] + blue[1],
                red[2] + green[2] + blue[2],
            )
        )
    return solid


def solid_extent(ramps: dict[str, Ramp], *, white_luminance: float) -> SolidExtent:
    """Peak and per-primary luminance — the numbers the picture shows.

    Reads the full-drive rows rather than sampling: the extremes of an
    additive solid are its corners, so there is nothing to search for.
    """
    _check_additive(ramps, white_luminance)
    return SolidExtent(
        peak_luminance=sum(ramps[c][-1][1][1] for c in ("red", "green", "blue")),
        red_luminance=ramps["red"][-1][1][1],
        green_luminance=ramps["green"][-1][1][1],
        blue_luminance=ramps["blue"][-1][1][1],
    )
