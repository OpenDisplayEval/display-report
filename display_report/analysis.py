"""Plotting and analysis functions for the display fidelity report."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from textwrap import dedent
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from colour.colorimetry.spectrum import (
    MultiSpectralDistributions,
    SpectralDistribution,
)
from colour.colorimetry.tristimulus_values import sd_to_XYZ
from colour.difference.delta_e import delta_E_CIE2000
from colour.models.cie_lab import XYZ_to_Lab
from colour.models.cie_luv import Luv_to_uv, XYZ_to_Luv
from colour.models.cie_xyy import XYZ_to_xy, xy_to_XYZ
from colour.models.rgb.derivation import normalised_primary_matrix
from colour.models.rgb.ictcp import XYZ_to_ICtCp
from colour.plotting.common import XYZ_to_plotting_colourspace
from colour.temperature.ohno2013 import XYZ_to_CCT_Ohno2013
from specio.serialization import (
    CSMF_Data,
    CSMF_Metadata,
    load_csmf_file,
)

if TYPE_CHECKING:
    from colour.hints import NDArrayBoolean, NDArrayFloat

    from display_report.device_info import DeviceInfo


@dataclass
class ReflectanceData:
    """The reflectance characteristics for the measured display. These are
    measured separately from the color accuracy measurements. Reflectance is
    measured relative to a reference sample, such as a pressed PTFE puck or
    fluorilon which have a lambertian reflectance value of ~99.8%
    """

    reflectance_45_0: float
    reflectance_45_45: float

    @property
    def glossiness_ratio(self) -> float:
        """Calculate the ratio of 45:-45 to 45:0 measurements.

        A correlate rating of the glossiness of a display.
        """
        return self.reflectance_45_45 / self.reflectance_45_0

    def __str__(self) -> str:
        """Summarize reflectance data"""
        return dedent(
            f"""
            Reflectance Data:
                45:-45 (specular) -> {self.reflectance_45_45 * 100:0.2f}%
                45:0    (matte)   -> {self.reflectance_45_0 * 100:0.2f}%
                Glossiness Ratio  -> {self.glossiness_ratio:.1f}
            """
        )


class UnfilterableMeasurements(ValueError):
    """The analysis cannot tell which patches are above the noise floor.

    Raised rather than analyzing everything, because the alternative
    quietly changes which measurements a report is built from
    (SPEC.md §spec:report-input).
    """


class ColourPrecisionAnalysis:
    """Analyze a measurement list for various colorimetric properties, like
    dE2000 and dE ITP.

    The transfer function and bit depth come from the file's declared
    signal contract (SPEC.md §spec:contract-analysis), never from an
    assumption. Rows carrying no measured spectrum -- a disciplined
    session reads its dark end with a colorimeter, and a colorimeter has
    none -- are judged on the tristimulus they do carry, and named in
    `rows_without_spectra`.
    """

    @property
    def _spectral_mask(self) -> NDArrayBoolean:
        """Rows carrying a spectrum.

        A colorimeter reading has none at all, so every spectral
        computation runs over this subset and says so, rather than
        treating absence as zero (§spec:report-input).
        """
        if hasattr(self, "_spectral_mask_cache"):
            return self._spectral_mask_cache

        self._spectral_mask_cache = np.array(
            [hasattr(m, "spd") for m in self._data.measurements], dtype=bool
        )
        return self._spectral_mask_cache

    @property
    def rows_without_spectra(self) -> npt.NDArray:
        """Indices of rows an analysis needing a spectrum has to exclude."""
        return np.flatnonzero(~self._spectral_mask)

    def _check_requirements(self) -> None:
        """Refuse an artifact that does not carry what this analysis reads.

        Checked once, against the blocks the artifact records, rather
        than discovered as a missing key somewhere inside a figure. An
        artifact recording no blocks is not refused here: the reference
        format and third-party files carry none, and the analysis still
        judges those on what they do contain (§spec:report-input).
        """
        from display_report.requires import blocks_carried, check

        try:
            provenance = self.provenance
        except Exception:
            # No provenance block at all: the reference format, or a
            # third party's. Nothing to check against.
            return
        carried = blocks_carried(provenance)
        if carried is None:
            return
        check(carried)

    @property
    def provenance(self) -> dict:
        """The artifact's canonical projection, verified against its digest."""
        if not hasattr(self, "_provenance_cache"):
            from display_report.provenance import read_provenance

            self._provenance_cache = read_provenance(self._data)
        return self._provenance_cache

    @property
    def contract(self):
        """The signal contract this file was measured under.

        Read from the file's provenance block where it has one. A file
        without one -- the reference format, or a third party's -- falls
        back to what that format assumed, PQ at ten bits, and the contract
        records that it was assumed rather than declared
        (§spec:contract-analysis). Silence is the failure mode this seam
        exists to remove, so the fallback is announced, not hidden.
        """
        if not hasattr(self, "_contract_cache"):
            from display_report.provenance import (
                ASSUMED_CONTRACT,
                ProvenanceError,
                contract_from,
            )

            try:
                self._contract_cache = contract_from(self.provenance)
            except ProvenanceError:
                self._contract_cache = ASSUMED_CONTRACT
        return self._contract_cache

    @property
    def _snr_mask(self) -> NDArrayBoolean:
        """Mask to remove low-quality measurements from the analysis.

        Returns
        -------
        NDArrayBoolean
        """
        # The floor is the *spread* across repeated black readings, which
        # is why the protocol reads black twenty times. One reading has no
        # spread: the divisor becomes that reading's deviation from a
        # smoothed version of itself, which is zero to rounding and of
        # either sign, and every patch in the file is rejected.
        #
        # It is tempting to keep every row when the floor is not
        # computable. That is what this did, and it was wrong: it silently
        # widened the set of patches the whole report is computed from,
        # letting readings the instrument cannot separate from black into
        # the chromaticity diagram, where they have no chromaticity to
        # contribute. Two runs of one display then produce reports that
        # cannot be compared, with nothing on either to say they were
        # built differently. Refusing is the honest answer.
        black_spectral = [m for m in self.black["measurements"] if hasattr(m, "spd")]

        if self.black.get("spd") is not None and len(black_spectral) > 1:
            # The measured path, unchanged: spectral power against the
            # spread of the black spectra.
            noise = np.mean(
                np.max(
                    np.sum(
                        [m.spd.values for m in black_spectral]
                        - self.black["spd"].values,
                        axis=1,
                    ),
                    0,
                )
            )
            signal = np.asarray(
                [max(m.power - self.black["power"], 0) for m in self._data.measurements]
            )
        elif len(self.black["measurements"]) > 1:
            # A disciplined session routes its dark end to a colorimeter,
            # which has no spectrum. Luminance is measured either way, and
            # the floor is the same quantity in a different unit: the
            # spread of the repeated black readings. Same 3 dB threshold,
            # and the substitution is stated rather than silent
            # (§spec:report-input).
            black_Y = np.asarray([m.XYZ[1] for m in self.black["measurements"]])
            noise = float(np.max(np.abs(black_Y - np.mean(black_Y))))
            signal = np.asarray(
                [
                    max(m.XYZ[1] - self.black["XYZ"][1], 0)
                    for m in self._data.measurements
                ]
            )
        else:
            # Reached only by an artifact that records no blocks at all
            # -- the reference format, or a third party's. One that
            # records them is refused at load with the block named
            # (`display_report.requires`), which is actionable in a way
            # that discovering it here is not.
            raise UnfilterableMeasurements(
                "this file carries one black reading, and the noise floor "
                "the analysis filters patches against is the spread across "
                "repeated ones -- with a single reading the divisor is "
                "that reading's deviation from itself, which is zero to "
                "rounding and rejects every patch in the file. The "
                "`noise-floor` measurement block is what carries the "
                "repeats."
            )

        if not noise > 0:
            raise UnfilterableMeasurements(
                f"the black readings in this file vary by {noise:g}, so the "
                "noise floor is not a positive number to divide by. Either "
                "the readings are identical -- a fixed-clock reproduction "
                "run, or a double that returns a constant -- or the "
                "instrument reported no variation at all."
            )

        snr = 10 * np.log10(signal / noise)
        return snr > 3

    @property
    def _analysis_mask(self) -> NDArrayBoolean:
        """Mask to remove any low-quality or error measurements, such as those
        containing nan or inf values.

        Returns
        -------
        NDArrayBoolean
        """
        if hasattr(self, "_analysis_mask_cache"):
            return self._analysis_mask_cache

        # Every row is judged on its tristimulus; a row is judged on its
        # spectrum only if it has one (§spec:report-input).
        finite_spectrum = np.array(
            [
                bool(np.all(np.isfinite(m.spd.values))) if hasattr(m, "spd") else True
                for m in self._data.measurements
            ],
            dtype=bool,
        )
        t = np.all(
            (
                finite_spectrum,
                ~np.any(np.isnan([m.XYZ for m in self._data.measurements]), axis=1),
                ~np.any(np.isinf([m.XYZ for m in self._data.measurements]), axis=1),
            ),
            axis=0,
        )
        self._analysis_mask_cache = t & self._snr_mask
        return self._analysis_mask_cache

    @property
    def black(self) -> dict:
        """A dictionary containing data from to the black test color
        measurements.

        Returns
        -------
        dict
        """
        if hasattr(self, "_black"):
            return self._black

        from scipy.signal import savgol_filter

        mask = np.all(self._data.test_colors == (0, 0, 0), axis=1)

        tmp = self._black = {}
        tmp["measurements"] = measurements = self._data.measurements[mask]

        # A disciplined session reads its dark end with a colorimeter
        # (§spec:spectral-retention), so the black rows are exactly the ones
        # most likely to carry no spectrum. Black's tristimulus is measured
        # either way; the spectral fields are only available when a black
        # row carried a spectrum, and are None rather than zero when not --
        # a zero here would read as a perfectly black display.
        spectral = [m for m in measurements if hasattr(m, "spd")]

        if spectral:
            spd_shape = spectral[0].spd.shape
            tmp["values"] = np.transpose(np.array([m.spd.values for m in spectral]))
            tmp["spectral_stddev"] = np.std(tmp["values"], axis=1)
            tmp["power_stddev"] = np.std([m.power for m in spectral])

            smoothed = savgol_filter(
                np.mean(tmp["values"], axis=1), 5, 2, mode="nearest"
            )
            tmp["spd"] = SpectralDistribution(np.asarray(smoothed), domain=spd_shape)
            tmp["XYZ"] = sd_to_XYZ(SpectralDistribution(tmp["spd"], spd_shape), k=683)
            tmp["power"] = float(np.sum(tmp["spd"].values))
        else:
            tmp["values"] = None
            tmp["spectral_stddev"] = None
            tmp["power_stddev"] = None
            tmp["spd"] = None
            tmp["power"] = None
            tmp["XYZ"] = np.mean([m.XYZ for m in measurements], axis=0)

        return self._black

    @property
    def primary_matrix(self) -> npt.NDArray:
        """The npm of the display"""
        if hasattr(self, "_pm"):
            return self._pm

        color_masks = []
        color_masks.append(np.all(self._data.test_colors[:, (1, 2)] == 0, axis=1))
        color_masks.append(np.all(self._data.test_colors[:, (0, 2)] == 0, axis=1))
        color_masks.append(np.all(self._data.test_colors[:, (0, 1)] == 0, axis=1))
        color_masks.append(
            np.all(
                self._data.test_colors[:, (0)] == self._data.test_colors[:, (1, 2)].T,
                axis=0,
            )
        )

        from sklearn.covariance import EllipticEnvelope, EmpiricalCovariance

        xy = np.zeros((4, 2))
        for idx, m in enumerate(color_masks):
            color_measurements = self._data.measurements[m & self._analysis_mask]
            color_XYZ = [t.XYZ for t in color_measurements] - self.black["XYZ"]
            xys = XYZ_to_xy(color_XYZ)

            try:
                # Find mean chromaticity without being influenced by outliers
                cov = EllipticEnvelope().fit(xys)
                xy[idx, :] = cov.location_
            except ValueError:
                # Covariance fit failed, probably because the data is well
                # clustered, traditional covariance can be used instead.
                cov = EmpiricalCovariance().fit(xys)
                xy[idx, :] = cov.location_

        # Fit NPM using colour
        self._pm = normalised_primary_matrix(xy[0:3, :], xy[3, :])
        return self._pm

    @property
    def grey(self):
        """A dictionary containing data from to the grey test color
        measurements.

        Returns
        -------
        dict
        """
        if hasattr(self, "_grey"):
            return self._grey

        grey = self._grey = {}
        grey_mask = np.all(
            self._data.test_colors[:, (0)] == self._data.test_colors[:, (1, 2)].T,
            axis=0,
        )
        grey_mask = grey_mask & self._analysis_mask

        # Black is the reference every level is measured against, not a
        # level that tracks. Subtracting it from itself leaves no light and
        # therefore no chromaticity -- a CCT of six figures at a Duv of 0.3,
        # which drags the whitepoint plot's limits with it. It used to fall
        # out here incidentally, filtered by a signal-to-noise ratio derived
        # from its own spectrum; a session that reads black with a
        # colorimeter has no such spectrum, so the exclusion is stated.
        grey_mask = grey_mask & ~np.all(self._data.test_colors == (0, 0, 0), axis=1)

        grey["measurements"] = self._data.measurements[grey_mask]
        grey["data_levels"] = self._data.test_colors[grey_mask, 0]
        grey["cct"] = np.array([(m.cct, m.duv) for m in grey["measurements"]])
        grey["luminance"] = np.array(
            [m.XYZ[1] - self.black["XYZ"][1] for m in grey["measurements"]]
        )
        grey["uniques"] = np.unique(
            grey["data_levels"], return_inverse=True, return_counts=True
        )

        # Averaging the spectra and subtracting black's is the better path,
        # but it needs a spectrum on both sides. Where either is missing --
        # a colorimeter-routed row, or a dark end read without one -- the
        # tristimulus is measured and says the same thing about luminance
        # and chromaticity, so it stands in rather than dropping the level.
        black_spd = self.black.get("spd")
        black_XYZ = self.black["XYZ"]

        avg_scale = []
        for unique_idx, _ in enumerate(grey["uniques"][0]):
            umask = grey["uniques"][1] == unique_idx
            level = grey["measurements"][umask]
            spectral = [m for m in level if hasattr(m, "spd")]

            if spectral and black_spd is not None:
                spd = MultiSpectralDistributions(data=[m.spd for m in spectral])
                spd = (
                    SpectralDistribution(np.mean(spd.values, axis=1), spd.domain)
                    - black_spd
                )
                XYZ = sd_to_XYZ(spd, k=683)
            else:
                XYZ = np.mean([m.XYZ for m in level], axis=0) - black_XYZ

            RGB = XYZ_to_plotting_colourspace(xy_to_XYZ(XYZ_to_xy(XYZ)) * 0.9)
            CCT = XYZ_to_CCT_Ohno2013(XYZ)
            avg_scale.append((XYZ, RGB, CCT))

        grey["avg_scale"] = avg_scale

        return self._grey

    @property
    def white(self):
        """A dictionary containing data from to the white test color
        measurements.

        Returns
        -------
        dict
        """
        if hasattr(self, "_white"):
            return self._white

        white = self._white = {}

        white["xyz"] = self.primary_matrix.dot([1, 1, 1])

        peak_code = self.contract.peak_code
        single_color_idx = np.all(self._data.test_colors == [peak_code] * 3, axis=1)
        single_color_measurements = self._data.measurements[single_color_idx]
        white["peak"] = np.mean(
            [m.XYZ - self.black["XYZ"] for m in single_color_measurements],
            axis=0,
        )
        contract = self.contract
        white["luminance_quantized"] = contract.eotf(
            np.round(contract.eotf_inverse(white["peak"][1]) * peak_code) / peak_code
        )

        return self._white

    @property
    def test_colors(self) -> NDArrayFloat:
        """The test colors (from the Test Pattern Generator) used for this
        analysis.

        Returns
        -------
        NDArray
        """
        return self._data.test_colors[self._analysis_mask]

    @property
    def measurements(self) -> npt.NDArray:
        """
        The test colors (from the Test Pattern Generator) used for this
        analysis.
        """
        return self._data.measurements[self._analysis_mask]

    @property
    def test_colors_linear(self):
        """Test pattern colors linearized at the declared contract.

        The transfer function and the code-value scale both come from the
        file (§spec:contract-analysis). Linearizing under the wrong one is
        an error nothing downstream can detect: the chart renders, and the
        numbers on it are wrong.
        """
        if hasattr(self, "_test_colors_linear"):
            return self._test_colors_linear

        contract = self.contract
        tmp = self._test_colors_linear = contract.eotf(
            self.test_colors.T / contract.peak_code
        )
        clipping_mask = tmp > self.white["luminance_quantized"]
        tmp[clipping_mask] = self.white["luminance_quantized"]
        return self._test_colors_linear

    @property
    def measured_colors(self):
        """A dictionary containing data from all of the
        `ColourPrecisionAnalysis.test_colors` measurements.

        Keys
        ----
        "XYZ"
        "ICtCp"
        "Lab":
            with the `self.analysis_conditions` assumptions.
        "uvp":
            u'v' coordinates.
        """
        if hasattr(self, "_act"):
            return self._act
        act = {}
        act["XYZ"] = XYZ = (
            np.asarray([m.XYZ for m in self.measurements]) - self.black["XYZ"]
        )
        act["XYZ"][act["XYZ"] < 0] = 0
        act["ICtCp"] = XYZ_to_ICtCp(XYZ)
        act["Lab"] = XYZ_to_Lab(
            act["XYZ"] / self.analysis_conditions.adapting_luminance * 5
        )
        act["uvp"] = Luv_to_uv(XYZ_to_Luv(act["XYZ"]))
        self._act = act
        return self._act

    @property
    def expected_colors(self):
        """A dictionary containing expected data / estimates from all of the
        `ColourPrecisionAnalysis.test_colors` assuming perfect linear behavior with
        `ColourPrecisionAnalysis.primary_matrix` and the PQ transfer function.

        Keys
        ----
        "XYZ"
        "ICtCp"
        "Lab"
        "uvp"
        """
        if hasattr(self, "_est"):
            return self._est
        est = {}
        est["XYZ"] = self.primary_matrix.dot(self.test_colors_linear).T
        est["ICtCp"] = XYZ_to_ICtCp(est["XYZ"])
        est["Lab"] = XYZ_to_Lab(
            est["XYZ"] / self.analysis_conditions.adapting_luminance * 5
        )
        est["uvp"] = Luv_to_uv(XYZ_to_Luv(est["XYZ"]))
        self._est = est
        return self._est

    @property
    def error(self):
        """Calculated difference between the
        `ColourPrecisionAnalysis.measured_colors` and
        `ColourPrecisionAnalysis.expected_colors`

        Returns
        -------
        dict

        Keys
        ---
        "XYZ"
        "ICtCp"
            dITP
        "dI"
            Brightness error according to dITP (ICtCp)
        "dChromatic"
            Chromatic error according to dITP (ICtCp)
        "dE2000"
        """
        if hasattr(self, "_err"):
            return self._err
        norm = partial(np.linalg.norm, axis=1)
        err = {}
        err["XYZ"] = norm(self.measured_colors["XYZ"] - self.expected_colors["XYZ"])

        err["ICtCp"] = 720 * norm(
            (self.measured_colors["ICtCp"] - self.expected_colors["ICtCp"])
            * (1, 0.5, 1)
        )
        err["dI"] = 720 * norm(
            (self.measured_colors["ICtCp"] - self.expected_colors["ICtCp"]) * (1, 0, 0)
        )
        err["dChromatic"] = 720 * norm(
            (self.measured_colors["ICtCp"] - self.expected_colors["ICtCp"])
            * (0, 0.5, 1)
        )

        err["dE2000"] = delta_E_CIE2000(
            self.measured_colors["Lab"], self.expected_colors["Lab"]
        )

        self._err = err
        return self._err

    @property
    def metadata(self) -> CSMF_Metadata:
        """Measurement metadata.

        Returns
        -------
        CSMF_Metadata
            The metadata saved in the measurement file.
        """
        return self._data.metadata

    @metadata.setter
    def metadata(self, new_data: CSMF_Metadata):
        self._data.metadata = new_data

    @property
    def device_info(self) -> DeviceInfo | None:
        """Parsed structured device info from metadata, if available.

        Returns
        -------
        DeviceInfo | None
            ``None`` when the notes field contains legacy plain text.
        """
        from display_report.device_info import DeviceInfo

        if self.metadata.notes is None or self.metadata.notes == "":
            return None
        return DeviceInfo.from_notes_string(self.metadata.notes)

    @property
    def shortname(self) -> str:
        """A short name that can be used in UI elements to identify this set of
        display measurements. Usually a model name and or serial number. If no user
        set shortname is available in the measurement file, a quasi-unique one
        will be calculated based on the spectrometer results.

        Returns
        -------
        str
        """
        if self._shortname is not None:
            return self._shortname

        if self.metadata.notes is None or self.metadata.notes == "":
            return self._data.shortname

        info = self.device_info
        if info is not None:
            return info.display_name

        return self.metadata.notes

    @shortname.setter
    def shortname(self, name: str | None):
        self._shortname = name

    def __str__(self) -> str:
        """Summary string containing dXYZ, dITP and dE2000"""
        # fmt: off
        return dedent(
            f"""
            Error Data for {self.shortname}
                Mean dXYZ:   {np.mean(self.error["XYZ"]):>6.2f}    95% < {np.percentile((self.error["XYZ"]),95):>6.2f}
                Mean dITP:   {np.mean(self.error["ICtCp"]):>6.2f}    95% < {np.percentile((self.error["ICtCp"]),95):>6.2f}
                Mean dE2000: {np.mean(self.error["dE2000"]):>6.2f}    95% < {np.percentile((self.error["dE2000"]),95):>6.2f}
            """
        )
        # fmt: on

    @dataclass
    class AnalysisConditions:
        """The visual condition assumptions used to calculate dE2000 and Lab
        values.
        """

        adapting_luminance: float  # luminance of 20% grey object

    def __init__(self, measurements: CSMF_Data):
        self._data: CSMF_Data = measurements

        self.analysis_conditions = self.AnalysisConditions(
            adapting_luminance=500 / (5 * np.pi)
        )
        self.shortname = None
        if np.ptp(self._data.test_colors) > 4096:
            # Special case where a few data files were created with earlier
            # worse versions of specio
            self._data.test_colors = self._data.test_colors / 255.0

        # At construction, not at first figure. An artifact that cannot
        # be analyzed should say so before anything is computed from it.
        self._check_requirements()


def analyze_measurements_from_file(filename: str) -> ColourPrecisionAnalysis:
    """Load the file at `filename` and return the ColorPrecisionAnalysis

    Parameters
    ----------
    file : str
        file location to be opened. Should be the result of one of the
        measurement scripts in display_report.

    Returns
    -------
    ColourPrecisionAnalysis
    """
    measurements = load_csmf_file(filename)

    fundamentalData = ColourPrecisionAnalysis(measurements)
    return fundamentalData
