"""Tests for rendering a report to bytes (SPEC.md §spec:report-api)."""

from __future__ import annotations

import importlib

import matplotlib
import pytest

matplotlib.use("Agg")

from matplotlib import pyplot as plt


@pytest.fixture
def stub_page(monkeypatch: pytest.MonkeyPatch):
    """Stand in for the report page.

    Rendering the real page needs a full analysis, which needs a
    measurement file. What this workstream adds is the seam between a
    figure and the bytes a caller receives, so that is what is exercised
    here.
    """
    from display_report import pdf

    made: list = []

    def fake_page(color_data, reflectance_data=None):
        figure = plt.figure()
        figure.gca().plot([0, 1], [0, 1])
        made.append(figure)
        return figure

    monkeypatch.setattr(pdf, "generate_report_page", fake_page)
    return made


class TestRenderReportPdf:
    def test_returns_pdf_bytes(self, stub_page):
        from display_report import render_report_pdf

        data = render_report_pdf(object())

        assert isinstance(data, bytes)
        assert data.startswith(b"%PDF")

    def test_closes_the_figure(self, stub_page):
        """A server rendering report after report must not leak figures.

        pyplot keeps every unclosed figure alive, so a long-running
        process grows without bound and eventually warns then stalls.
        """
        from display_report import render_report_pdf

        before = set(plt.get_fignums())
        render_report_pdf(object())

        assert set(plt.get_fignums()) == before
        assert len(stub_page) == 1

    def test_closes_the_figure_when_saving_fails(
        self, stub_page, monkeypatch: pytest.MonkeyPatch
    ):
        """A failed render must not leak either."""
        from display_report import render_report_pdf

        def boom(*args, **kwargs):
            raise RuntimeError("no")

        before = set(plt.get_fignums())
        monkeypatch.setattr(plt.Figure, "savefig", boom)

        with pytest.raises(RuntimeError):
            render_report_pdf(object())

        assert set(plt.get_fignums()) == before

    def test_passes_reflectance_through(self, stub_page):
        from display_report import pdf, render_report_pdf

        seen = {}

        def capture(color_data, reflectance_data=None):
            seen["reflectance"] = reflectance_data
            return plt.figure()

        pdf.generate_report_page = capture
        sentinel = object()
        render_report_pdf(object(), sentinel)

        assert seen["reflectance"] is sentinel

    def test_two_renders_of_one_analysis_agree(self, stub_page):
        """The CLI and an in-process caller produce the same report."""
        from display_report import render_report_pdf

        first = render_report_pdf(object())
        second = render_report_pdf(object())

        assert len(first) == len(second)


class TestExported:
    def test_is_public(self):
        module = importlib.import_module("display_report")

        assert "render_report_pdf" in module.__all__
        assert callable(module.render_report_pdf)
