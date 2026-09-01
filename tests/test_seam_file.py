"""Reading the measurement seam file (SPEC.md §spec:report-input).

The fixture is a real `display-measure characterize` artifact, not a
hand-built one -- a report-grade session, carrying the blocks this
analysis declares it requires (`display_report.requires`). Fixtures
measured for something else are kept beside it and exercise the
refusal, which is the case no hand-rolled fixture would have produced.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "report_session.csmf"


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
        assert len(analysis._data.measurements) == 795

    def test_the_black_readings_repeat(self, analysis):
        """The noise floor is their spread, and one reading has none."""
        import numpy as np

        blacks = np.all(analysis._data.test_colors == (0, 0, 0), axis=1)

        assert int(blacks.sum()) == 20


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

    def test_reports_which_rows_lack_a_measured_spectrum(self):
        """A disciplined session routes its dark end to a colorimeter,
        which has no spectrum. Those rows are named rather than treated
        as zero, which would read as a perfectly black display."""
        from display_report import analyze_measurements_from_file

        hybrid = Path(__file__).parent / "fixtures" / "hybrid_report_session.csmf"
        analysis = analyze_measurements_from_file(str(hybrid))

        # §spec:report-input: an analysis needing a spectrum reports
        # what it excluded, rather than treating absence as zero.
        assert len(analysis.rows_without_spectra) > 0
        assert len(analysis.rows_without_spectra) < len(analysis._data.measurements)


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

    def test_names_the_blocks_it_measured(self, analysis):
        """What a consumer matches on. A bundle name says nothing about
        what an artifact carries; the block ids say exactly that."""
        blocks = analysis.provenance["protocol"]["blocks"]

        assert "anchors/1" in blocks
        assert "noise-floor/1" in blocks

    def test_the_blocks_satisfy_what_this_analysis_declares(self, analysis):
        from display_report.requires import REQUIRES, blocks_carried, check

        carried = blocks_carried(analysis.provenance)

        assert carried is not None
        assert set(REQUIRES) <= set(carried)
        check(carried)

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
        # The blocks, not a bundle name: two artifacts under one name
        # can hold different measurements once blocks version apart.
        assert "anchors/1" in line
        assert "noise-floor/1" in line
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


class TestRefusesAnArtifactMeasuredForSomethingElse:
    """A config-grade artifact is readable and complete; it just carries
    a different measurement. Saying so by name is what lets an operator
    act -- the alternative was discovering it as a rejected patch mask
    deep inside a figure.
    """

    def test_a_verify_grade_artifact_is_refused_by_block_name(self):
        from display_report import analyze_measurements_from_file
        from display_report.requires import UnsupportedArtifact

        older = Path(__file__).parent / "fixtures" / "spectral_session.csmf"

        with pytest.raises(UnsupportedArtifact, match="noise-floor"):
            analyze_measurements_from_file(str(older))

    def test_the_refusal_names_every_shortfall_at_once(self):
        """An operator who has to re-measure should learn the whole list
        on the first attempt, not one block per two-hour session."""
        from display_report.requires import UnsupportedArtifact, check

        with pytest.raises(UnsupportedArtifact) as raised:
            check({"anchors": 1})

        for block in ("noise-floor", "tracking", "volume-mesh", "white-repeat"):
            assert block in str(raised.value)

    def test_an_artifact_recording_no_blocks_is_not_refused(self):
        """The reference format carries no protocol block at all, and is
        judged on what it does contain."""
        from display_report.requires import blocks_carried

        assert blocks_carried({"colorimetry": {}}) is None
