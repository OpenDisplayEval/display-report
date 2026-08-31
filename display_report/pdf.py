"""PDF generation for the display fidelity report."""

# Annotations here name types imported only under TYPE_CHECKING. Without
# this, they evaluate at def time and the module is unimportable on any
# Python below 3.14 — where PEP 649 defers them and hides the breakage.
# This package supports 3.12 upward.
from __future__ import annotations

import importlib
import importlib.resources
import io
from typing import TYPE_CHECKING

import matplotlib
import matplotlib.colors
import matplotlib.font_manager
import numpy as np
from colour.colorimetry.datasets.illuminants.sds import SDS_ILLUMINANTS
from colour.colorimetry.tristimulus_values import sd_to_XYZ
from colour.models.cie_luv import Luv_to_uv, XYZ_to_Luv, xy_to_Luv_uv
from colour.models.rgb.datasets import RGB_COLOURSPACES
from colour.plotting.models import (
    plot_ellipses_MacAdam1942_in_chromaticity_diagram_CIE1976UCS,
)
from colour.temperature.ohno2013 import XYZ_to_CCT_Ohno2013
from matplotlib import pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import Polygon
from sklearn.cluster import KMeans

from display_report.fonts import Anuphan
from display_report.utilities import tool_identifier

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.gridspec import SubplotSpec
    from matplotlib.image import AxesImage

    from display_report.analysis import (
        ColourPrecisionAnalysis,
        ReflectanceData,
    )


def plot_chromaticity_error(data: ColourPrecisionAnalysis, ax: Axes | None = None):
    """Plot the ∆u'v' in the given axes. Generates a chromaticity plot.

    If no `ax` is supplied, one will be generated in a new figure window.

    Parameters
    ----------
    data : ColourPrecisionAnalysis
        The base color data for the plot.
    ax : Axes | None, optional
        Target axes, by default None

    Returns
    -------
    Axes
        The target or generated axes used.
    """
    if ax is None:
        _, ax = plot_ellipses_MacAdam1942_in_chromaticity_diagram_CIE1976UCS(
            show=False,
            diagram_opacity=0.3,
            title="CIE u'v' (1976) Average Error",
        )
    else:
        plot_ellipses_MacAdam1942_in_chromaticity_diagram_CIE1976UCS(
            show=False,
            diagram_opacity=0.3,
            axes=ax,
        )
    ax.set_title("CIE u'v' (1976) Average Error", fontsize=12)
    ax.set_xticks(np.arange(0, 0.7, 0.1), [])
    ax.set_yticks(np.arange(-0.1, 0.7, 0.1), [])

    for p in ax.patches[1:]:
        p.set_color((0, 0.6, 0.5))
        p.set_alpha(0.4)
        p.set_zorder(5)

    gamuts = [RGB_COLOURSPACES["P3-D65"], RGB_COLOURSPACES["ITU-R BT.2020"]]
    # fmt: off
    colors = np.array([
        [.8, 0, 0, .5],
        [0, .6, 0, .5],
        [0,  0, 0, .5]
    ])
    # fmt: on
    gamut_artists = []
    for idx, gamut in enumerate(gamuts):
        gamut_artists.append(
            ax.add_patch(
                Polygon(
                    xy_to_Luv_uv(gamut.primaries),
                    fc=[0, 0, 0, 0],
                    ec=colors[idx, :],
                    linewidth=1.5,
                    linestyle="--",
                    zorder=4,
                )
            )
        )
    native_gamut_artist = ax.add_patch(
        Polygon(
            Luv_to_uv(XYZ_to_Luv(data.primary_matrix.T)),
            fc=[0, 0, 0, 0],
            ec=colors[2, :],
            linewidth=1.5,
            zorder=4,
        )
    )

    Luv_to_uv(XYZ_to_Luv(data.primary_matrix.T))

    klusters = KMeans(n_clusters=14, n_init=20).fit(data.measured_colors["uvp"])  # type: ignore[reportArgumentType]
    normalize = matplotlib.colors.Normalize(0, 13)
    cmap = plt.get_cmap("nipy_spectral")
    labels = klusters.labels_
    assert labels is not None
    colors = cmap(normalize(labels))
    dist = data.measured_colors["uvp"] - data.expected_colors["uvp"]

    for idx in range(klusters.n_clusters):
        kmask = klusters.labels_ == idx
        kdist = np.mean(dist[kmask], axis=0) * 10
        ax.arrow(
            klusters.cluster_centers_[idx, 0],
            klusters.cluster_centers_[idx, 1],
            kdist[0],
            kdist[1],
            facecolor=[1, 0.25, 0.15],
            edgecolor=[0, 0, 0],
            width=0.004,
            linewidth=0.5,
            length_includes_head=True,
            zorder=6,
        )

    ax.set_ylim(-0.05, 0.64)
    ax.set_xlim(-0.02, 0.65)

    ax.text(
        0.63,
        -0.041,
        "Elipses show 10x SDCM (MacAdam, 1942)\nArrows show 10x avg. error in "
        "each region",
        horizontalalignment="right",
        verticalalignment="bottom",
        fontsize=8,
    )
    ax.legend(
        [*gamut_artists, native_gamut_artist],
        [*[g.name for g in gamuts], "Display Native"],
        loc=(0.60, 0.1),
        fontsize=8,
    )
    return ax


def plot_eotf_accuracy(data: ColourPrecisionAnalysis, ax: Axes | None = None) -> Axes:
    """Plot the EOTF measurements on a log/log axes. If no `ax` is provided, one
    will be generated in a new figure.

    Parameters
    ----------
    data : ColourPrecisionAnalysis
        The base color data for the plot.
    ax : Axes | None, optional
        Target axes, by default None

    Returns
    -------
    Axes
        The target or generated axes used.
    """
    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot()

    ax.scatter(
        data.grey["data_levels"],
        data.grey["luminance"],
        s=20,
        color=[0.2, 0.32, 0.6],
        zorder=100,
    )
    ax.set_yscale("log", base=2)
    ax.set_xscale("log", base=2)
    contract = data.contract
    peak_code = contract.peak_code
    ax.set_xlim(contract.eotf_inverse(0.1) * peak_code, peak_code + 1)  # type: ignore
    ax.set_ylim(bottom=0.1, top=10000)

    ax.set_yticks(2.0 ** np.arange(-3, 14))
    # Powers of two up to the declared depth: the ticks a code-value axis
    # wants, wherever that axis ends.
    decades = np.arange(6, contract.bit_depth + 1)
    code_ticks = (2.0**decades) - 1
    ax.set_xticks(code_ticks, [str(int(t)) for t in code_ticks])

    x_1000cd = contract.eotf_inverse(1000) * peak_code
    ax.plot([x_1000cd, x_1000cd], [0, 1000], color="#5a9c9e")
    ax.text(
        x_1000cd + 25,  # type: ignore
        0.15,
        "1000 cd/m² (nits)",
        fontsize=8,
        ha="left",
        color="#5a9c9e",
        rotation="vertical",
    )

    ax.plot(
        np.arange(0, peak_code),
        contract.eotf(np.arange(0, peak_code) / peak_code),
        color=[1, 0, 0],
    )
    # An axis labelled "10-bit" under a 12-bit session is a false statement
    # about the measurement, printed on the artifact a human judges from
    # (§spec:report-rendering). Both follow the declared contract.
    if contract.transfer_function == "gamma":
        transfer_name = f"Gamma {contract.gamma_value:g}"
    else:
        transfer_name = contract.transfer_function.upper()
    ax.set_title(f"{transfer_name} EOTF Performance")
    ax.set_xlabel(f"{contract.bit_depth}-bit Code Value (Log)")
    ax.set_ylabel("Luminance — cd/m² (nits), Log")

    max_luminance = np.max([m[0][1] for m in data.grey["avg_scale"]])

    ax.plot(
        [63, contract.eotf_inverse(max_luminance) * peak_code],  # type: ignore
        [max_luminance, max_luminance],
        color="#6f5481",
        zorder=50,
    )
    ax.text(
        64,
        max_luminance + 2**11 * 0.1,
        f"Display Max: {max_luminance:.0f} cd/m² (nits)",
        va="bottom",
        fontsize=8,
        color="#6f5481",
    )
    return ax


def plot_wp_accuracy(
    data: ColourPrecisionAnalysis,
    fig_spec: tuple[Figure, SubplotSpec] | None = None,
) -> tuple[Axes, Axes]:
    """Plot the white point accuracy over luminance values.

    If no figure and subgrid spec is provided, one will be generated.

    Parameters
    ----------
    data : ColourPrecisionAnalysis
        The base color data for this plot
    fig_spec : tuple[Figure, SubplotSpec] | None, optional
        A (Figure, SubplotSpec) with room for 2 axes, by default None. None will
        generate a new figure.

    Returns
    -------
    tuple[Axes, Axes]
        The two axes used for this plot.
    """
    if fig_spec is None:
        fig, axs = plt.subplots(2, 1)
    else:
        fig = fig_spec[0]
        temp_spec = fig_spec[1].subgridspec(2, 1, hspace=0.15)
        axs = [fig.add_subplot(temp_spec[0]), fig.add_subplot(temp_spec[1])]

    contract = data.contract
    peak_code = contract.peak_code
    xticks = contract.eotf_inverse(10.0 ** np.arange(-1, 5)) * peak_code
    xtick_labels = ["0.1"] + [f"{(10.0**m):.0f}" for m in np.arange(0, 5)]
    xtick_minor = (
        contract.eotf_inverse(
            (
                np.arange(2, 10).reshape(1, -1)
                * [10.0] ** np.arange(-1, 4).reshape(-1, 1)
            ).flatten()
        )
        * peak_code
    )

    tgt_XYZ = sd_to_XYZ(SDS_ILLUMINANTS["D65"], k=683)
    tgt_XYZ *= 100 / tgt_XYZ[1]
    tgt_cct = XYZ_to_CCT_Ohno2013(tgt_XYZ)

    # ANSI C78.377 implied SDCM (standard deviation color matching) values. I.e. 1
    # MacAdam Ellipse size. JND @ 50% detection threshold is @ 1.18 * 1 SCDM
    cct_tolerance = (
        1.19e-8 * tgt_cct[0] ** 3
        - 1.5434e-4 * tgt_cct[0] ** 2
        + 0.7168 * tgt_cct[0]
        - 902.55
    ) / 7
    duv_tolerance = 0.0060 / 7

    cct_list = np.array(list(zip(*data.grey["avg_scale"], strict=False))[2])

    def plot_max_luminance_line(ax: Axes) -> tuple[float, float]:
        max_luminance = np.max([m[0][1] for m in data.grey["avg_scale"]])
        x_max_luminance = contract.eotf_inverse(max_luminance) * peak_code

        ax.set_xlim(left=float(contract.eotf_inverse(0.1) * peak_code), right=peak_code)
        ax.set_xticks(
            xtick_minor,
            [],
            minor=True,
        )
        ax.plot([x_max_luminance, x_max_luminance], ax.get_ylim(), color="#6f5481")
        return (max_luminance, float(x_max_luminance))

    def plot_wp_cct(ax: Axes) -> None:
        y_lim = (5500, 7500)
        ax.set_ylim(*y_lim)

        ax.set_title("Whitepoint Error")
        ax.set_ylabel("CCT (°K)\n<- Warmer / Cooler ->")
        ax.set_xticks(xticks, [])
        ax.plot(ax.get_xlim(), (tgt_cct[0], tgt_cct[0]))

        ax.text(
            float(contract.eotf_inverse(0.11) * peak_code * 0.99),
            6540,
            "D65",
            fontsize=8,
        )
        plot_max_luminance_line(ax)
        _plot_y_tolerance_bg(
            ax,
            tol_bounds=[
                y_lim[0],
                tgt_cct[0] - 6 * cct_tolerance,
                tgt_cct[0] - 4 * cct_tolerance,
                tgt_cct[0] - 1 * cct_tolerance,
                tgt_cct[0] + 1 * cct_tolerance,
                tgt_cct[0] + 4 * cct_tolerance,
                tgt_cct[0] + 6 * cct_tolerance,
                y_lim[1],
            ],
            colors="rryggyrr",
            aspect_multiplier=0.5,
        )

        ax.scatter(data.grey["uniques"][0], cct_list[:, 0])

        arrow_size = abs(np.diff(ax.get_ylim()))[0] * 0.15
        # fmt: off
        mask = (
            (cct_list[:, 0] > ax.get_ylim()[1]).astype(np.int32)
            - (cct_list[:, 0] < ax.get_ylim()[0]).astype(np.int32)
        )
        # fmt: on
        for idx in np.where(mask != 0)[0]:
            ax.arrow(
                x=data.grey["uniques"][0][idx],
                y=ax.get_ylim()[int(mask[idx] == 1)] - mask[idx] * (arrow_size + 0),
                dx=0,
                dy=arrow_size * mask[idx],
                width=7,
                head_length=arrow_size / 3.5,
                length_includes_head=True,
                ec=[0, 0, 0, 0],
            )

    plot_wp_cct(axs[0])

    def plot_wp_duv(ax: Axes) -> None:
        y_lim = np.array((-0.012, 0.012)) + 0.003
        ax.set_ylim(*y_lim)
        ax.set_yticks(
            [-0.005, 0.000, 0.005, 0.010, 0.015],
            labels=["-0.005", "0.000", "0.005", "0.010", "0.015"],
            rotation=55,
        )

        ax.set_ylabel("∆uv (CIE 1960)\n← Magenta / Green →")

        ax.set_xticks(xticks, xtick_labels)

        ax.plot(ax.get_xlim(), (tgt_cct[1], tgt_cct[1]))
        ax.text(
            float(contract.eotf_inverse(0.11) * peak_code * 0.99),
            0.004,
            "D65",
            fontsize=8,
        )

        x_max_luminance = plot_max_luminance_line(ax)
        ax.scatter(data.grey["uniques"][0], cct_list[:, 1])
        _plot_y_tolerance_bg(
            ax,
            tol_bounds=[
                y_lim[0],
                tgt_cct[1] - 6 * duv_tolerance,
                tgt_cct[1] - 4 * duv_tolerance,
                tgt_cct[1] - 1 * duv_tolerance,
                tgt_cct[1] + 1 * duv_tolerance,
                tgt_cct[1] + 4 * duv_tolerance,
                tgt_cct[1] + 6 * duv_tolerance,
                y_lim[1],
            ],
            colors="rryggyrr",
            aspect_multiplier=0.5,
        )
        # fmt: off
        mask = (
            (cct_list[:, 1] > ax.get_ylim()[1]).astype(np.int32)
            - (cct_list[:, 1] < ax.get_ylim()[0]).astype(np.int32)
        )
        # fmt: on
        arrow_size = abs(np.diff(ax.get_ylim()))[0] * 0.15
        for idx in np.where(mask != 0)[0]:
            ax.arrow(
                x=data.grey["uniques"][0][idx],
                y=ax.get_ylim()[int(mask[idx] == 1)] - mask[idx] * (arrow_size + 0),
                dx=0,
                dy=arrow_size * mask[idx],
                width=7,
                head_length=arrow_size / 3.5,
                length_includes_head=True,
                ec=[0, 0, 0, 0],
            )

        ax.text(
            x_max_luminance[1] - 25,
            ax.get_ylim()[0] + 0.001,
            f"Display Max: {x_max_luminance[0]:.0f} cd/m² (nits)",
            fontsize=8,
            ha="right",
            color="#6f5481",
        )

    plot_wp_duv(axs[1])
    return axs[0], axs[1]


def plot_brightness_errors(
    data: ColourPrecisionAnalysis, ax: Axes | None = None
) -> Axes:
    """Plot the dI errors according to dITP. If no `ax` is provided one will be
    generated in a new figure.

    Parameters
    ----------
    data : ColourPrecisionAnalysis
        The base color data for this plot.
    ax : Axes | None, optional
        Target axes, by default None

    Returns
    -------
    Axes
        The target axes used or generated for the plot.
    """
    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot()

    deltaI = data.error["dI"]

    ax.scatter(
        data.measured_colors["ICtCp"][:, 0],
        deltaI,
        color=[0.5, 0.5, 0.5],
        s=120,
    )
    ax.scatter(
        data.measured_colors["ICtCp"][:, 0],
        deltaI,
        c=data.test_colors[:] / data.contract.peak_code,
        s=50,
    )
    ax.set_yscale("symlog", base=2)
    ax.set_ylim(-(2**5), 2**5)
    ax.set_yticks((([[2, 2]] ** np.arange(0, 6).reshape(-1, 1)) * [1, -1]).flatten())
    contract = data.contract
    ax.set_xlim(contract.eotf_inverse(0.1), 1)  # type: ignore

    xticks = contract.eotf_inverse(10.0 ** np.arange(-1, 5))
    xtick_labels = ["0.1"] + [f"{(10.0**m):.0f}" for m in np.arange(0, 5)]
    xticks_minor = contract.eotf_inverse(
        (
            np.arange(2, 10).reshape(1, -1) * [10.0] ** np.arange(-1, 4).reshape(-1, 1)
        ).flatten()
    )

    max_luminance = np.max([m[0][1] for m in data.grey["avg_scale"]])
    x_max_luminance = contract.eotf_inverse(max_luminance)

    ax.set_xticks(xticks, xtick_labels)
    ax.set_xticks(xticks_minor, minor=True)

    ax.plot(
        [x_max_luminance, x_max_luminance], ax.get_ylim(), zorder=-1, color="#6f5481"
    )
    ax.text(
        x_max_luminance - 0.02,  # type: ignore
        ax.get_ylim()[0] + 1.5**4,
        f"Display Max: {max_luminance:.0f} cd/m² (nits)",
        ha="right",
        zorder=-1,
        fontsize=8,
        color="#6f5481",
    )

    ax.set_title("Brightness Error (∆ICtCp)")
    _plot_y_tolerance_bg(
        ax,
        tol_bounds=[-(2**5), -(2**3), -2, -1, 1, 2, 2**3, 2**5],
        colors=["r", "r", "y", "g", "g", "y", "r", "r"],
        aspect_multiplier=2,
    )
    return ax


def _plot_y_tolerance_bg(
    ax: Axes,
    tol_bounds: list[float],
    colors: Sequence[str],
    aspect_multiplier: float = 1,
) -> AxesImage:
    """Create a y axis background gradient based on the stops and colors in
    `tol_bounds` and `colors`
    """
    from scipy.interpolate import Akima1DInterpolator

    color_dict = {
        "r": [1.0, 0.85, 0.8],
        "y": [1.0, 1.0, 0.8],
        "g": [0.8, 1.0, 0.8],
    }
    bg_image = Akima1DInterpolator(
        tol_bounds,
        [color_dict[c] for c in colors],
    )(np.linspace(tol_bounds[-1], tol_bounds[0], 1000))
    bg_image = bg_image.reshape(-1, 1, 3)
    return ax.imshow(
        bg_image,
        extent=(*ax.get_xlim(), *ax.get_ylim()),
        # `np.diff` returns a one-element array, and NumPy 2 refuses to
        # convert anything but a 0-d array to a scalar. Index it, as the
        # arrow sizing above already does.
        aspect=float(
            aspect_multiplier
            * abs(np.diff(ax.get_xlim()))[0]
            / abs(np.diff(ax.get_ylim()))[0]
        ),
    )


def plot_chromatic_error(data: ColourPrecisionAnalysis, ax: Axes | None = None) -> Axes:
    """Plot dChromatic based on dITP.

    Parameters
    ----------
    data : ColourPrecisionAnalysis
        The base color data
    ax : Axes | None, optional
        The axis to use. If None is provided, a new figure and axis will be
        created (default).

    Returns
    -------
    Axes
        The target or generated axes that was used for plotting
    """
    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot()

    delta_cr = data.error["dChromatic"]

    ax.scatter(
        data.measured_colors["ICtCp"][:, 0],
        delta_cr,
        color=[0.5, 0.5, 0.5],
        s=120,
    )
    ax.scatter(
        data.measured_colors["ICtCp"][:, 0],
        delta_cr,
        c=data.test_colors / data.contract.peak_code,
        s=50,
    )
    ax.set_yscale("symlog", base=2)
    ax.set_ylim(0, 2**5)
    ax.set_yticks(2 ** np.arange(0, 6))
    contract = data.contract
    ax.set_xlim(contract.eotf_inverse(0.1), 1)  # type: ignore

    xticks = contract.eotf_inverse(10.0 ** np.arange(-1, 5))
    xtick_labels = ["0.1"] + [f"{(10.0**m):.0f}" for m in np.arange(0, 5)]
    xticks_minor = contract.eotf_inverse(
        (
            np.arange(2, 10).reshape(1, -1) * [10.0] ** np.arange(-1, 4).reshape(-1, 1)
        ).flatten()
    )
    x_max_luminance = contract.eotf_inverse(data.white["luminance_quantized"])

    ax.set_xticks(xticks, xtick_labels)
    ax.set_xticks(xticks_minor, minor=True)

    ax.plot([x_max_luminance, x_max_luminance], ax.get_ylim(), zorder=-1)

    ax.set_title("Chromatic Error (∆ICtCp)")

    _plot_y_tolerance_bg(
        ax,
        tol_bounds=[0, 1, 2, 2**3, 2**5],
        colors=["g", "g", "y", "r", "r"],
    )
    return ax


def plot_report_header(ax: Axes, data: ColourPrecisionAnalysis):
    """Plot the report header / title bar.

    When structured device info is available, the display name is shown as the
    main title with optional hardware details rendered as smaller secondary text.
    Legacy plain-text notes fall back to a single-line header.

    Parameters
    ----------
    ax : Axes
        The target axes
    data : ColourPrecisionAnalysis
        The base color data
    """
    ax.set_ylim(0, 1)
    ax.set_axis_off()

    # Provenance: tolerances and metrics change between versions, so a report
    # states which build produced it.
    ax.text(
        1,
        0.15,
        tool_identifier(),
        va="bottom",
        ha="right",
        fontsize=8,
        color="0.4",
    )

    info = data.device_info
    if info is None:
        ax.text(0, 0.15, f"{data.shortname}", va="bottom", fontsize=16)
        ax.text(0, 0.05, _contract_line(data), va="top", fontsize=8, color="0.4")
        return

    ax.text(0, 0.15, info.display_name, va="bottom", fontsize=16)

    detail_parts: list[str] = []
    if info.firmware_version:
        detail_parts.append(f"FW: {info.firmware_version}")
    if info.receiver_card_firmware:
        detail_parts.append(f"Receiver FW: {info.receiver_card_firmware}")
    if info.driver_chip:
        detail_parts.append(f"Driver: {info.driver_chip}")
    if info.led_type:
        detail_parts.append(f"LED: {info.led_type}")

    detail_parts.append(_contract_line(data))
    ax.text(
        0,
        0.05,
        "  |  ".join(detail_parts),
        va="top",
        fontsize=8,
        color="0.4",
    )


def _contract_line(data: ColourPrecisionAnalysis) -> str:
    """One line naming what the report was measured and read under.

    A report that does not say which contract it read cannot be checked
    against the session that produced it, and a file measured at one
    contract analyzed as another is the failure the seam exists to prevent
    (§spec:contract-analysis). Saying it out loud is what makes that
    guarantee visible to the person holding the page.
    """
    contract = data.contract
    if contract.transfer_function == "gamma":
        transfer = f"gamma {contract.gamma_value:g}"
    else:
        transfer = contract.transfer_function.upper()

    parts = [f"{transfer}, {contract.bit_depth}-bit"]
    if contract.peak_luminance:
        parts.append(f"{contract.peak_luminance:g} cd/m²")

    try:
        protocol = (data.provenance.get("protocol") or {}).get("name")
    except Exception:
        protocol = None
    if protocol:
        parts.append(str(protocol))

    parts.append(
        "declared by the file"
        if contract.declared
        else "ASSUMED — the file declares no contract"
    )
    return "  |  ".join(parts)


def plot_error_statistics(
    data: ColourPrecisionAnalysis,
    reflectance: ReflectanceData | None = None,
    ax: Axes | None = None,
):
    """Plot the error statistics including mean and 95th percentile for dITP and
    dE2000.

    Optionally this also plots the reflectance information.

    Parameters
    ----------
    data : ColourPrecisionAnalysis
        The base color data
    reflectance : ReflectanceData | None, optional
        The reflectance data, by default None
    ax : Axes | None, optional
        Target axes, by default None
    """
    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot()
    ax.set_ylim(5, 0)
    ax.set_xlim(0, 1)
    ax.set_facecolor("None")
    ax.set_axis_off()

    text_settings = {"va": "top"}

    ax.text(
        0,
        0,
        "Mean ∆E 2000:",
        **text_settings,  # type: ignore
    )
    ax.text(
        0.35,
        0,
        f"{np.mean(data.error['dE2000']):.01f}",
        **text_settings,  # type: ignore
    )
    ax.text(
        0.5,
        0,
        f"95th percentile: {np.percentile(data.error['dE2000'], 95):.01f}",
        **text_settings,  # type: ignore
    )

    ax.text(
        0,
        1,
        "Mean ∆ICtCp:",
        **text_settings,  # type: ignore
    )
    ax.text(
        0.35,
        1,
        f"{np.mean(data.error['ICtCp']):.01f}",
        **text_settings,  # type: ignore
    )
    ax.text(
        0.5,
        1,
        f"95th percentile:  {np.percentile(data.error['ICtCp'], 95):.01f}",
        **text_settings,  # type: ignore
    )

    if reflectance is None:
        return
    ax.text(
        0,
        2,
        "45°:0° Reflectance:",
        **text_settings,  # type: ignore
    )
    ax.text(
        0.5,
        2,
        f"{reflectance.reflectance_45_0 * 100:.2f}%",
        **text_settings,  # type: ignore
    )
    ax.text(
        0,
        3,
        "45°:45° Reflectance:",
        **text_settings,  # type: ignore
    )
    ax.text(
        0.5,
        3,
        f"{reflectance.reflectance_45_45 * 100:.2f}%",
        **text_settings,  # type: ignore
    )

    ax.text(0, 4, "Glossiness Ratio:", **text_settings)  # type: ignore
    ax.text(
        0.5,
        4,
        f"{reflectance.glossiness_ratio:.2f}",
        **text_settings,  # type: ignore
    )


def generate_report_page(
    color_data: ColourPrecisionAnalysis,
    reflectance_data: ReflectanceData | None = None,
) -> Figure:
    """Given the `color_data` and `reflectance_data` plot a report page
    summarizing display performance. This can be saved to pdf.

    Parameters
    ----------
    color_data : ColourPrecisionAnalysis
        The base color data
    reflectance_data : ReflectanceData | None, optional
        Reflectance data, usually measured separately from the color precision
        data by default None

    Returns
    -------
    Figure
        the `matplotlib.figure.Figure` containing analysis plots.
    """
    matplotlib.font_manager.fontManager.addfont(
        str(importlib.resources.files(Anuphan).joinpath("Anuphan.ttf"))
    )
    rcParams["font.family"] = ["Anuphan", *rcParams["font.family"]]

    fig = plt.figure(
        "Display Fidelity Report",
        figsize=np.asarray((8.5, 11)),
        facecolor=(1, 1, 1),
        constrained_layout=True,
        dpi=100,
    )
    outer_gs = fig.add_gridspec(2, 1, height_ratios=[1, 20])
    outer_gs.update()
    title_ax = fig.add_subplot(outer_gs[0])
    plot_report_header(title_ax, color_data)
    columns_gs = outer_gs[1].subgridspec(1, 2, width_ratios=[1, 1])

    left_col_gs = columns_gs[0].subgridspec(
        4, 1, height_ratios=[0.3, 0.8125 + 0.21625, 0.6, 0.1]
    )
    right_col_gs = columns_gs[1].subgridspec(4, 1, height_ratios=[1, 1, 0.35, 0.5])

    ######################################

    plot_wp_accuracy(color_data, (fig, right_col_gs[0]))

    ax = fig.add_subplot(right_col_gs[1])
    plot_brightness_errors(color_data, ax)
    ax = fig.add_subplot(right_col_gs[2])
    plot_chromatic_error(color_data, ax)

    ax = fig.add_subplot(left_col_gs[1])
    plot_chromaticity_error(color_data, ax)
    fig.set_facecolor((1, 1, 1))  # Why does `colour` set this!?

    ax = fig.add_subplot(left_col_gs[2])
    plot_eotf_accuracy(color_data, ax)

    ax: Axes = fig.add_subplot(left_col_gs[0])
    plot_error_statistics(color_data, reflectance_data, ax)

    ######################################

    plt.show(block=False)
    return fig


def render_report_pdf(
    color_data: ColourPrecisionAnalysis,
    reflectance_data: ReflectanceData | None = None,
) -> bytes:
    """Render the report page and return it as PDF bytes.

    The in-process surface behind `display-report analyze`
    (SPEC.md §spec:report-api). A caller holding an analysis gets the
    report without a subprocess, a temporary file it did not choose, or a
    path to scrape for failures.

    Parameters
    ----------
    color_data : ColourPrecisionAnalysis
        The analysis to report on.
    reflectance_data : ReflectanceData | None, optional
        Reflectance data, measured separately from the colour precision
        data, by default None.

    Returns
    -------
    bytes
        The report as a PDF document.
    """
    figure = generate_report_page(
        color_data=color_data, reflectance_data=reflectance_data
    )
    # pyplot holds every figure it creates, so a server rendering report
    # after report grows without bound unless each one is closed. The
    # close belongs in a finally: a failed render leaks just as well.
    try:
        buffer = io.BytesIO()
        figure.savefig(buffer, format="pdf", facecolor=(1, 1, 1))
    finally:
        plt.close(figure)

    return buffer.getvalue()
