"""Gamut arithmetic for the situational-awareness view (§spec:gamut-visualization).

The numbers here are the bench display's, measured under three different
panel configurations, because the arithmetic's job is to tell them apart
(§spec:report-metrics).
"""

import pytest

from display_report.gamut import (
    STANDARD_GAMUTS,
    coverage,
    primary_deficits,
    uv_from_xy,
)

# Measured on the bench rig. Aug 12 ran a calibration whose blue sits
# outside Rec.709's; Aug 29's factory calibration pulls it inside.
AUG12 = {"red": (0.6913, 0.3080), "green": (0.1780, 0.7405), "blue": (0.1348, 0.0540)}
AUG29 = {"red": (0.6831, 0.3095), "green": (0.1912, 0.7063), "blue": (0.1405, 0.0697)}


def triangle(primaries: dict[str, tuple[float, float]]) -> list[tuple[float, float]]:
    return [uv_from_xy(*primaries[c]) for c in ("red", "green", "blue")]


class TestChromaticity:
    def test_d65_converts_to_its_known_uv(self) -> None:
        u, v = uv_from_xy(0.3127, 0.3290)
        assert u == pytest.approx(0.1978, abs=1e-4)
        assert v == pytest.approx(0.4683, abs=1e-4)


class TestCoverage:
    """Coverage is bounded at 100%: it answers what fraction of a target
    the display reaches, never how much larger its triangle is."""

    def test_a_gamut_covers_itself_entirely(self) -> None:
        r709 = [uv_from_xy(*p) for p in STANDARD_GAMUTS["Rec.709"]]
        assert coverage(r709, r709) == pytest.approx(1.0, abs=1e-6)

    def test_coverage_never_exceeds_one(self) -> None:
        """The bench display's triangle is larger than Rec.709's by area and
        still cannot reproduce all of it — the distinction area ratios
        lose (§spec:report-metrics)."""
        for primaries in (AUG12, AUG29):
            for name in STANDARD_GAMUTS:
                target = [uv_from_xy(*p) for p in STANDARD_GAMUTS[name]]
                assert coverage(triangle(primaries), target) <= 1.0

    def test_the_factory_calibration_covers_less_of_rec709(self) -> None:
        """The measurement that motivated this: a calibration can buy
        luminance and white point by giving up gamut, and the report has
        to show that rather than hide it."""
        r709 = [uv_from_xy(*p) for p in STANDARD_GAMUTS["Rec.709"]]
        assert coverage(triangle(AUG29), r709) < coverage(triangle(AUG12), r709)


class TestPrimaryDeficits:
    """A scalar coverage figure hides where the shortfall is; the deficit
    per primary is the actionable form."""

    def test_a_reachable_primary_has_no_deficit(self) -> None:
        d = primary_deficits(triangle(AUG12), "Rec.709")
        assert d["red"] == 0.0
        assert d["green"] == 0.0

    def test_rec709_blue_is_unreachable_on_this_panel(self) -> None:
        """No LED display reaches it; both calibrations miss, the factory one
        by far more."""
        assert primary_deficits(triangle(AUG12), "Rec.709")["blue"] > 0.0
        assert (
            primary_deficits(triangle(AUG29), "Rec.709")["blue"]
            > primary_deficits(triangle(AUG12), "Rec.709")["blue"]
        )

    def test_the_deficit_is_a_uv_distance(self) -> None:
        d = primary_deficits(triangle(AUG29), "Rec.709")["blue"]
        assert d == pytest.approx(0.0254, abs=5e-4)


def test_densify_puts_points_along_each_edge() -> None:
    """Hover needs targets between the corners, not only at them."""
    from display_report.gamut import densify as _densify

    triangle = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    dense = _densify(triangle, per_edge=4)
    # Closed loop: three edges, four points each, plus the return corner.
    assert len(dense) == 13
    assert dense[0] == (0.0, 0.0)
    assert dense[-1] == (0.0, 0.0)
    assert (0.5, 0.0) in dense


def test_densify_keeps_every_original_corner() -> None:
    from display_report.gamut import densify as _densify

    triangle = [(0.1, 0.2), (0.7, 0.3), (0.2, 0.8)]
    dense = _densify(triangle, per_edge=5)
    for corner in triangle:
        assert corner in dense


def test_white_point_summary_reports_cct_with_its_duv() -> None:
    """CCT alone is a projection; Duv says how far off the locus it is.

    A chromaticity far from the Planckian locus still projects to some
    correlated temperature, so a bare kelvin figure can describe a white
    nobody would call white. The two travel together.
    """
    from display_report.gamut import white_point_summary

    summary = white_point_summary((0.325969327, 0.325306504))
    assert 5000 < summary.cct < 6500
    assert abs(summary.duv) < 0.05
    assert summary.duv != 0.0


def test_white_point_summary_separates_target_distance_from_locus_distance() -> None:
    """du'v' to D65 and Duv answer different questions.

    du'v' is distance from the target white; Duv is signed distance from
    the Planckian locus. A display can sit on the locus and far from
    D65, so one cannot substitute for the other.
    """
    from display_report.gamut import white_point_summary

    summary = white_point_summary((0.325969327, 0.325306504))
    assert summary.duv_from_target > 0.005
    assert summary.duv_from_target != summary.duv


def test_d65_reports_itself_as_d65() -> None:
    from display_report.gamut import white_point_summary

    summary = white_point_summary((0.3127, 0.3290))
    assert summary.duv_from_target < 1e-4
    assert 6400 < summary.cct < 6600
