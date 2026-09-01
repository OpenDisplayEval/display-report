"""The reproducible set as a solid (§spec:gamut-visualization).

A chromaticity triangle is one slice of a three-dimensional set, and it
hides the thing that decides whether a colour is usable: the luminance
it is available at. This display can make its red primary, but only at
422 cd/m2 — not at the 1483 its white reaches. The triangle says the
first and not the second.

The solid is a model, and the measurement that licenses it is
additivity: this display's channels sum to within 0.75% of measured white,
so XYZ(r,g,b) = R(r) + G(g) + B(b) is a fair description of it. On a
display where additivity failed, this would be fiction.
"""

import pytest

from display_report.volume import (
    NonAdditiveDisplay,
    channel_response,
    gamut_solid,
    solid_extent,
)

# ftg_bench_20260829 full-drive per channel, absolute XYZ.
PRIMARIES = {
    "red": (930.544, 421.859, 9.882),
    "green": (255.743, 947.095, 137.312),
    "blue": (76.935, 125.520, 1336.0),
}
WHITE_Y = 1483.218

# Two rungs per channel is enough to exercise the interpolation; the
# real curves carry seventeen.
RAMPS = {
    "red": [(0, (0.0, 0.0, 0.0)), (4095, PRIMARIES["red"])],
    "green": [(0, (0.0, 0.0, 0.0)), (4095, PRIMARIES["green"])],
    "blue": [(0, (0.0, 0.0, 0.0)), (4095, PRIMARIES["blue"])],
}


class TestChannelResponse:
    def test_full_drive_returns_the_measured_primary(self) -> None:
        response = channel_response(RAMPS["red"])
        assert response(4095) == pytest.approx(PRIMARIES["red"], rel=1e-9)

    def test_zero_drive_is_black(self) -> None:
        assert channel_response(RAMPS["green"])(0) == pytest.approx((0.0, 0.0, 0.0))

    def test_it_interpolates_between_measured_rungs(self) -> None:
        mid = channel_response(RAMPS["blue"])(2048)
        assert 0 < mid[2] < PRIMARIES["blue"][2]


class TestAdditivityLicense:
    def test_a_display_that_sums_to_white_is_modelled(self) -> None:
        solid = gamut_solid(RAMPS, white_luminance=WHITE_Y, samples=4)
        assert len(solid) > 0

    def test_a_display_whose_channels_do_not_sum_is_refused(self) -> None:
        """The solid is only a description of a display where the channels
        add. Drawing one for a display where they do not would be
        inventing a capability nobody measured."""
        with pytest.raises(NonAdditiveDisplay, match="additivity"):
            gamut_solid(RAMPS, white_luminance=WHITE_Y * 2.0, samples=4)


class TestExtent:
    def test_the_solid_reaches_white_at_the_top(self) -> None:
        extent = solid_extent(RAMPS, white_luminance=WHITE_Y)
        assert extent.peak_luminance == pytest.approx(
            sum(PRIMARIES[c][1] for c in ("red", "green", "blue")), rel=1e-6
        )

    def test_a_primary_is_available_far_below_peak(self) -> None:
        """The finding the triangle hides: saturated red exists only in
        the bottom third of the luminance range."""
        extent = solid_extent(RAMPS, white_luminance=WHITE_Y)
        assert extent.red_luminance < extent.peak_luminance / 2
