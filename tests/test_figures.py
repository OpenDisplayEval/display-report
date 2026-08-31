"""Rendering one report diagram at a time (SPEC.md §spec:report-api).

The point of this surface is that a live view and the downloaded report
cannot disagree: both draw from the functions the page draws from, so a
figure changes only when the report changes.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

from matplotlib import pyplot as plt

FIXTURE = Path(__file__).parent / "fixtures" / "hybrid_session.csmf"


@pytest.fixture(scope="module")
def analysis():
    from display_report import analyze_measurements_from_file

    return analyze_measurements_from_file(str(FIXTURE))


class TestRenderFigure:
    def test_every_named_figure_renders(self, analysis) -> None:
        from display_report.figures import FIGURES, render_figure

        for name in FIGURES:
            data = render_figure(analysis, name)

            assert data[:4] == b"\x89PNG", f"{name} did not render a PNG"
            assert len(data) > 5_000, f"{name} rendered suspiciously small"

    def test_an_unknown_name_says_what_there_is(self, analysis) -> None:
        """A caller naming a figure that does not exist gets the list."""
        from display_report.figures import render_figure

        with pytest.raises(KeyError, match="chromaticity"):
            render_figure(analysis, "not_a_figure")

    def test_the_figure_is_closed(self, analysis) -> None:
        """A server renders one of these per view; pyplot holds every
        figure it makes until someone closes it."""
        from display_report.figures import render_figure

        before = set(plt.get_fignums())
        render_figure(analysis, "chromaticity")

        assert set(plt.get_fignums()) == before

    def test_the_figure_is_closed_when_drawing_fails(
        self, analysis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from display_report import figures

        def boom(*args, **kwargs):
            raise RuntimeError("no")

        monkeypatch.setitem(figures.FIGURES, "chromaticity", boom)
        before = set(plt.get_fignums())

        with pytest.raises(RuntimeError):
            figures.render_figure(analysis, "chromaticity")

        assert set(plt.get_fignums()) == before


class TestSharedWithTheReport:
    def test_the_figures_are_the_page_s_own_functions(self) -> None:
        """Not a second implementation that agrees until one changes."""
        from display_report import figures, pdf

        assert figures.FIGURES["chromaticity"] is pdf.plot_chromaticity_error
        assert figures.FIGURES["eotf"] is pdf.plot_eotf_accuracy

    def test_exported(self) -> None:
        module = importlib.import_module("display_report")

        assert "render_figure" in module.__all__
        assert callable(module.render_figure)
