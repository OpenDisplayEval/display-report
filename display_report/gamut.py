"""Gamut arithmetic for the situational-awareness view (§spec:gamut-visualization).

Everything here works in CIE 1976 u'v'. The 1931 xy diagram exaggerates
green distances and crushes blue ones, which misleads exactly where
narrow-band LED primaries land; artifacts record xy and views convert
(§spec:gamut-visualization).

**Coverage, never area ratio.** The fraction of a target a display can
actually reproduce is bounded above by 1.0. The ratio of triangle areas
is not, and it flatters a display that is large in a direction no
content uses: the bench display measures 131.6% of Rec.709 by area and
cannot reach Rec.709 blue (§spec:report-metrics).

**A scalar hides where the shortfall is.** Coverage weights by
chromaticity area, so a thin slice of unreachable colour reads as a
small number however visible it is. `primary_deficits` reports the
distance to each target primary instead, which is the form that says
which primary to raise with a panel vendor and which rendering intent
will hurt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

__all__ = [
    "STANDARD_GAMUTS",
    "WhitePointSummary",
    "coverage",
    "primary_deficits",
    "uv_from_xy",
    "white_point_summary",
]

Point = tuple[float, float]

# Standard gamut primaries as (red, green, blue) in CIE 1931 xy, the form
# the standards state them in. Converted on use rather than stored in
# u'v' so the published numbers stay greppable against the documents.
STANDARD_GAMUTS: dict[str, tuple[Point, Point, Point]] = {
    "Rec.709": ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060)),
    "DCI-P3": ((0.680, 0.320), (0.265, 0.690), (0.150, 0.060)),
    "Rec.2020": ((0.708, 0.292), (0.170, 0.797), (0.131, 0.046)),
}

PRIMARY_NAMES = ("red", "green", "blue")

# Roughly one just-noticeable difference in u'v'. Used for reporting
# only — u'v' is uniform enough to compare distances in, not uniform
# enough to convert them to a JND count, which is why the view shows the
# distance and leaves the judgement to the reader.
JND_UV = 0.004


def uv_from_xy(x: float, y: float) -> Point:
    """CIE 1931 xy as CIE 1976 u'v'."""
    denominator = -2.0 * x + 12.0 * y + 3.0
    return (4.0 * x / denominator, 9.0 * y / denominator)


def _area(polygon: list[Point]) -> float:
    """The shoelace area, unsigned."""
    total = 0.0
    for i, (x, y) in enumerate(polygon):
        nx, ny = polygon[(i + 1) % len(polygon)]
        total += x * ny - nx * y
    return abs(total) / 2.0


def _side(point: Point, edge_start: Point, edge_end: Point) -> float:
    """Which side of a directed edge the point falls on, as a signed area."""
    return (edge_end[0] - edge_start[0]) * (point[1] - edge_start[1]) - (
        edge_end[1] - edge_start[1]
    ) * (point[0] - edge_start[0])


def _counterclockwise(triangle: list[Point]) -> list[Point]:
    return (
        triangle if _side(triangle[2], triangle[0], triangle[1]) > 0 else triangle[::-1]
    )


def _clip(subject: list[Point], clipper: list[Point]) -> list[Point]:
    """Sutherland-Hodgman: `subject` clipped to the convex `clipper`.

    Both are triangles here, so the classic algorithm applies without
    the degenerate cases a general polygon would bring.
    """
    output = list(subject)
    clipper = _counterclockwise(clipper)
    for i in range(len(clipper)):
        if not output:
            break
        start, end = clipper[i], clipper[(i + 1) % len(clipper)]
        candidates, output = output, []
        for j, current in enumerate(candidates):
            previous = candidates[j - 1]
            side_current, side_previous = (
                _side(current, start, end),
                _side(previous, start, end),
            )
            if side_current >= 0:
                if side_previous < 0:
                    output.append(
                        _intersect(previous, current, side_previous, side_current)
                    )
                output.append(current)
            elif side_previous >= 0:
                output.append(
                    _intersect(previous, current, side_previous, side_current)
                )
    return output


def _intersect(a: Point, b: Point, side_a: float, side_b: float) -> Point:
    t = side_a / (side_a - side_b)
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def coverage(display: list[Point], target: list[Point]) -> float:
    """The fraction of `target` the `display` triangle contains, 0.0-1.0.

    Both arguments are u'v' triangles in (red, green, blue) order. The
    result cannot exceed 1.0 by construction — it is the intersection's
    area over the target's, so a display larger than the target scores
    1.0 and no more.
    """
    target_area = _area(target)
    if target_area <= 0.0:
        return 0.0
    return _area(_clip(target, display)) / target_area


def _inside(point: Point, triangle: list[Point]) -> bool:
    sides = [_side(point, triangle[i], triangle[(i + 1) % 3]) for i in range(3)]
    return all(s >= -1e-12 for s in sides) or all(s <= 1e-12 for s in sides)


def _distance_to_edge(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = dx * dx + dy * dy
    t = (
        0.0
        if length == 0
        else max(
            0.0,
            min(
                1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length
            ),
        )
    )
    return math.hypot(point[0] - (start[0] + t * dx), point[1] - (start[1] + t * dy))


def primary_deficits(display: list[Point], standard: str) -> dict[str, float]:
    """How far each of a standard's primaries sits outside the display, u'v'.

    Zero means reachable. A non-zero value is the shortest distance from
    that primary to the display's gamut boundary — the quantity that
    says which primary falls short and by how much, where a coverage
    percentage says only that something does.

    Read against the display's own native primaries rather than a
    standard's wherever the question is what a *configuration* costs: no
    display reaches Rec.709 blue, so that shortfall is a property of
    the emitter and discriminates nothing between calibrations
    (§spec:report-metrics).
    """
    target = [uv_from_xy(*p) for p in STANDARD_GAMUTS[standard]]
    deficits = {}
    for name, primary in zip(PRIMARY_NAMES, target, strict=True):
        if _inside(primary, display):
            deficits[name] = 0.0
        else:
            deficits[name] = min(
                _distance_to_edge(primary, display[i], display[(i + 1) % 3])
                for i in range(3)
            )
    return deficits


# The reference white the pipeline targets, and what a report compares
# a measured white against unless a show declares otherwise.
D65_XY = (0.3127, 0.3290)


@dataclass(frozen=True)
class WhitePointSummary:
    """A measured white described three ways, because one is not enough.

    `cct` is the temperature of the closest point on the Planckian
    locus, and on its own it can name a temperature for a white nobody
    would call white — every chromaticity projects onto the locus
    somewhere. `duv` is the signed distance from that locus, which is
    what says whether the projection means anything: positive is green
    of it, negative is magenta.

    `duv_from_target` answers a different question again — how far the
    measured white sits from the white the pipeline aims at, in u'v'.
    A display can sit exactly on the locus and still be far from D65,
    so this cannot be recovered from the other two.
    """

    xy: tuple[float, float]
    cct: float
    duv: float
    duv_from_target: float
    target_xy: tuple[float, float]
    target_cct: float


def white_point_summary(
    xy: tuple[float, float], *, target: tuple[float, float] = D65_XY
) -> WhitePointSummary:
    """Describe a measured white against the white the pipeline targets."""
    # Deferred: colour is heavy and the artifact view should not pay for
    # it until a white point is asked about.
    import numpy as np
    from colour.models import UCS_to_uv, XYZ_to_UCS, xy_to_Luv_uv, xy_to_XYZ
    from colour.temperature import uv_to_CCT_Ohno2013, xy_to_CCT

    def _uv_1960(point: tuple[float, float]) -> np.ndarray:
        # Ohno's method is defined on the CIE 1960 UCS diagram. Feeding
        # it 1976 u'v' returns a confident, wrong answer — D65 comes back
        # as 3087 K — because 1960 v is two thirds of 1976 v'.
        return np.asarray(UCS_to_uv(XYZ_to_UCS(xy_to_XYZ(np.asarray(point)))))

    def _uv_1976(point: tuple[float, float]) -> np.ndarray:
        # Distance to the target is quoted in 1976 u'v', which is where
        # the JND scaling this pipeline uses elsewhere lives.
        return np.asarray(xy_to_Luv_uv(np.asarray(point)))

    cct, duv = uv_to_CCT_Ohno2013(_uv_1960(xy))
    return WhitePointSummary(
        xy=xy,
        cct=float(cct),
        duv=float(duv),
        duv_from_target=float(np.hypot(*(_uv_1976(xy) - _uv_1976(target)))),
        target_xy=target,
        target_cct=float(xy_to_CCT(np.asarray(target), "McCamy 1992")),
    )


def densify(
    points: list[tuple[float, float]], *, per_edge: int = 24
) -> list[tuple[float, float]]:
    """Close a polygon and put `per_edge` samples along every edge.

    Gamut arithmetic, not a plotting detail, which is why it lives here:
    a renderer that hovers or hit-tests a trace answers on the trace's
    points rather than on the line drawn between them, so a triangle of
    three vertices responds only at its corners. Sampling the edges
    gives the line something to answer with; it draws identically.
    """
    loop = [*points, points[0]]
    dense: list[tuple[float, float]] = []
    for (x0, y0), (x1, y1) in pairwise(loop):
        for i in range(per_edge):
            t = i / per_edge
            dense.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    dense.append(loop[-1])
    return dense
