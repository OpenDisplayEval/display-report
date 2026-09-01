"""Transfer fidelity and quantization headroom (§spec:gamut-visualization).

The bench display's own gray ramp, dark-room capture. Its declared contract
is a 2.35 power law and it does not follow one: the measured response
carries excess light through the low mids, reproducibly, across three
sessions under two calibrations.
"""

import pytest

from display_report.transfer import (
    barten_threshold,
    fitted_exponent,
    gamma_step_contrast,
    pq_step_contrast,
    quantization_headroom,
    transfer_residuals,
)

# ftg_bench_20260829: (code, luminance cd/m2), protocol order.
RAMP = [
    (16, 0.006723),
    (24, 0.019177),
    (32, 0.040686),
    (48, 0.107200),
    (64, 0.234500),
    (96, 0.425800),
    (128, 0.627000),
    (192, 1.690200),
    (256, 3.150300),
    (384, 8.062000),
    (512, 15.32000),
    (768, 33.28000),
    (1024, 61.29000),
    (1536, 152.1000),
    (2048, 294.7000),
    (3072, 755.9000),
    (4095, 1483.218),
]
PEAK = 1483.218


class TestFittedExponent:
    def test_the_clean_decade_fits_near_the_measured_value(self) -> None:
        """Reported at 2.24 across three sessions, against 2.35 declared."""
        assert fitted_exponent(RAMP, PEAK, floor_code=768) == pytest.approx(
            2.24, abs=0.06
        )

    def test_widening_the_window_lowers_it(self) -> None:
        """The exponent slides with the window, which is what says the
        response is not a power law rather than a power law of a
        different exponent."""
        wide = fitted_exponent(RAMP, PEAK, floor_code=256)
        narrow = fitted_exponent(RAMP, PEAK, floor_code=1024)
        assert wide < narrow


class TestResiduals:
    def test_the_shadow_excess_is_reported(self) -> None:
        """Codes 192-512 carry far more light than 2.35 predicts. This is
        the finding the report exists to surface."""
        residuals = dict(transfer_residuals(RAMP, PEAK, gamma=2.35))
        assert residuals[256] > 0.25
        assert residuals[384] > 0.25

    def test_full_drive_is_the_anchor(self) -> None:
        """The fit is normalised to peak, so the top rung is exact by
        construction and saying otherwise would be a bug."""
        residuals = dict(transfer_residuals(RAMP, PEAK, gamma=2.35))
        assert residuals[4095] == pytest.approx(0.0, abs=1e-9)


class TestBarten:
    def test_the_threshold_falls_as_luminance_rises(self) -> None:
        """Contrast sensitivity improves with adaptation luminance, so a
        step that hides at 1 cd/m2 may show at 100."""
        assert barten_threshold(100.0) < barten_threshold(1.0)

    def test_the_threshold_is_a_small_positive_contrast(self) -> None:
        for luminance in (0.1, 10.0, 1000.0):
            t = barten_threshold(luminance)
            assert 0.0 < t < 0.2


class TestHeadroom:
    def test_every_rung_reports_a_step_and_a_threshold(self) -> None:
        rows = quantization_headroom(RAMP, bit_depth=12)
        assert len(rows) == len(RAMP) - 1
        for row in rows:
            assert row.step_contrast > 0
            assert row.threshold > 0

    def test_headroom_is_the_ratio_of_step_to_threshold(self) -> None:
        rows = quantization_headroom(RAMP, bit_depth=12)
        for row in rows:
            assert row.headroom == pytest.approx(row.step_contrast / row.threshold)

    def test_the_threshold_flag_tracks_the_ratio(self) -> None:
        """Named `above_threshold` rather than `visible`: Barten's line is
        the most favourable detection condition, not a verdict on
        banding."""
        rows = quantization_headroom(RAMP, bit_depth=12)
        assert any(r.above_threshold is False for r in rows), "expected clean rungs"
        for row in rows:
            assert row.above_threshold == (row.headroom > 1.0)


class TestBitDepthComparison:
    """The same measured display, judged against a different encoding — the
    comparison §road:lut-transfer-probe needs."""

    def test_fewer_bits_make_every_step_coarser(self) -> None:
        twelve = {
            r.code: r.step_contrast for r in quantization_headroom(RAMP, bit_depth=12)
        }
        ten = {
            r.code: r.step_contrast for r in quantization_headroom(RAMP, bit_depth=10)
        }
        assert all(ten[c] > twelve[c] for c in twelve)

    def test_ten_bit_steps_are_four_twelve_bit_steps(self) -> None:
        twelve = {
            r.code: r.step_contrast for r in quantization_headroom(RAMP, bit_depth=12)
        }
        ten = {
            r.code: r.step_contrast for r in quantization_headroom(RAMP, bit_depth=10)
        }
        for code, step in twelve.items():
            assert ten[code] == pytest.approx(step * 4.0)


def test_pq_step_contrast_falls_with_more_bits() -> None:
    """A 12-bit PQ step is finer than a 10-bit one at the same level."""
    levels = [0.01, 1.0, 100.0]
    coarse = dict(pq_step_contrast(levels, bit_depth=10))
    fine = dict(pq_step_contrast(levels, bit_depth=12))
    for level in levels:
        assert fine[level] < coarse[level]


def test_pq_step_contrast_is_a_positive_weber_contrast() -> None:
    """Every step is a real, positive fraction of its own level."""
    for _, contrast in pq_step_contrast([0.005, 0.5, 50.0, 1000.0], bit_depth=12):
        assert 0.0 < contrast < 1.0


def test_pq_12bit_clears_barten_where_10bit_does_not() -> None:
    """The known quantity: 12-bit PQ sits under threshold in the shadows.

    This is what PQ was derived to do, and it is why the reference is
    worth drawing — it orients a reading of the measured curve.
    """
    level = 0.05
    threshold = barten_threshold(level)
    ((_, twelve),) = pq_step_contrast([level], bit_depth=12)
    ((_, ten),) = pq_step_contrast([level], bit_depth=10)
    assert twelve < threshold < ten


def test_gamma_step_contrast_is_coarser_at_lower_levels() -> None:
    """A power law spends its codes at the top, so shadows step coarsely."""
    rows = dict(
        gamma_step_contrast([0.1, 10.0, 1000.0], peak=1000.0, gamma=2.35, bit_depth=12)
    )
    assert rows[0.1] > rows[10.0] > rows[1000.0]


def test_gamma_step_contrast_matches_the_analytic_slope() -> None:
    """Weber contrast of one code under a power law is gamma / code."""
    peak, gamma, depth = 1000.0, 2.4, 12
    level = 100.0
    ((_, contrast),) = gamma_step_contrast(
        [level], peak=peak, gamma=gamma, bit_depth=depth
    )
    code = (2**depth - 1) * (level / peak) ** (1 / gamma)
    assert contrast == pytest.approx(gamma / code, rel=1e-6)


def test_more_bits_makes_a_finer_gamma_step() -> None:
    fine = dict(gamma_step_contrast([1.0], peak=1000.0, gamma=2.35, bit_depth=12))
    coarse = dict(gamma_step_contrast([1.0], peak=1000.0, gamma=2.35, bit_depth=10))
    assert fine[1.0] < coarse[1.0]
