"""Reading the measurement seam file (SPEC.md §spec:report-input).

The fixture is a real `display-measure characterize` artifact, not a
hand-built one. Its black row is colorimetric and carries no spectrum,
because a disciplined session reads its dark end with a colorimeter --
which is exactly the shape that broke the analysis, and exactly what no
hand-rolled fixture would have produced.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "hybrid_session.csmf"


@pytest.fixture(scope="module")
def analysis():
    from display_report import analyze_measurements_from_file

    return analyze_measurements_from_file(str(FIXTURE))


class TestLoadsEveryRow:
    def test_fixture_exists(self):
        assert FIXTURE.is_file(), "regenerate per tests/fixtures/README.md"

    def test_every_row_survives_the_reader(self, analysis):
        """The released colour-specio loader reads only the legacy spectral
        list, so a hybrid file came back with zero measurements and no
        error at all. The failure then surfaced far from its cause."""
        assert len(analysis._data.measurements) == 72

    def test_the_dark_row_is_colorimetric(self, analysis):
        """A colorimeter has no spectrum. If this row ever arrives with
        one, the fixture stopped exercising the case it exists for."""
        kinds = [type(m).__name__ for m in analysis._data.measurements]

        assert kinds.count("ColorimeterMeasurement") == 1
        assert kinds.count("SPDMeasurement") == 71


class TestToleratesRowsWithoutSpectra:
    def test_analysis_mask_does_not_require_a_spectrum(self, analysis):
        """Every row is judged; a row without a spectrum is judged on the
        tristimulus it does carry."""
        import numpy as np

        assert int(np.sum(analysis._analysis_mask)) > 0

    def test_black_resolves_without_a_black_spectrum(self, analysis):
        """The black patch is the colorimetric row here, so black has a
        measured tristimulus and no spectrum."""
        black = analysis.black

        assert black["XYZ"] is not None
        assert float(black["XYZ"][1]) >= 0

    def test_reports_which_rows_lack_a_measured_spectrum(self, analysis):
        """§spec:report-input: an analysis needing a spectrum reports what
        it excluded and why, rather than treating absence as zero."""
        excluded = analysis.rows_without_spectra

        assert len(excluded) == 1


class TestRendersTheReport:
    def test_renders_a_pdf_from_the_seam_file(self, analysis):
        """The end the whole seam exists for."""
        import matplotlib

        matplotlib.use("Agg")
        from display_report import render_report_pdf

        data = render_report_pdf(analysis)

        assert data.startswith(b"%PDF")
        assert len(data) > 10_000


class TestReadsTheContract:
    def test_provenance_block_is_available(self, analysis):
        """The file states what produced it (§spec:report-input)."""
        provenance = analysis.provenance

        assert provenance is not None

    def test_names_its_protocol(self, analysis):
        assert analysis.provenance["protocol"]["name"] == (
            "color-wrangler/characterize/3"
        )

    def test_names_its_transfer_function(self, analysis):
        """A 12-bit gamma session shall not be read as 10-bit PQ."""
        contract = analysis.contract

        assert contract.transfer_function == "gamma"
        assert contract.bit_depth == 12


class TestStatesItsContract:
    def test_page_names_the_contract_it_read(self, analysis):
        """§road:sdr-12bit-report: the report says what it was measured
        under, so a reader can check it against the session."""
        from display_report.pdf import _contract_line

        line = _contract_line(analysis)

        assert "gamma 2.4" in line
        assert "12-bit" in line
        assert "color-wrangler/characterize/3" in line
        assert "declared by the file" in line

    def test_an_assumed_contract_says_so(self):
        """A file with no provenance still analyzes -- and the page says
        the encoding was assumed, never silently applied."""
        from display_report.provenance import ASSUMED_CONTRACT

        assert ASSUMED_CONTRACT.declared is False
        assert ASSUMED_CONTRACT.transfer_function == "pq"
        assert ASSUMED_CONTRACT.bit_depth == 10


class TestExported:
    def test_public_names(self):
        module = importlib.import_module("display_report")

        for name in ("SignalContract", "read_provenance"):
            assert name in module.__all__, f"{name} is not public"
