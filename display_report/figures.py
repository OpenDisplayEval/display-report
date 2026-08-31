"""The report's diagrams, one at a time (SPEC.md §spec:report-api).

`render_report_pdf` renders the whole page. A surface that shows a live
view of the same measurement wants the diagrams individually, and wants
them to *be* the report's -- not a second implementation that agrees with
it until one of them changes. So the page and the live view draw from the
same functions here, and a figure can only drift from the report by the
report itself changing.

Each figure is drawn on its own axes at its own size, so it is legible
alone rather than as a tile of a letter-sized page.

Vector by default. The report's own pages are vector -- real embedded
fonts and several thousand path operations, rasterizing only the
continuous colour gradients that cannot be anything else -- and a live
view of the same figure has no reason to be worse. A raster would also
break the moment anyone zoomed it.
"""

from __future__ import annotations

import importlib.resources
import io
from typing import TYPE_CHECKING

import matplotlib
import matplotlib.font_manager
from matplotlib import pyplot as plt
from matplotlib import rcParams

from display_report.fonts import Anuphan
from display_report.pdf import (
    plot_brightness_errors,
    plot_chromatic_error,
    plot_chromaticity_error,
    plot_eotf_accuracy,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from matplotlib.axes import Axes

    from display_report.analysis import ColourPrecisionAnalysis

__all__ = ["FIGURES", "render_figure"]


FIGURES: dict[str, Callable[..., object]] = {
    "chromaticity": plot_chromaticity_error,
    "eotf": plot_eotf_accuracy,
    "brightness_error": plot_brightness_errors,
    "chromatic_error": plot_chromatic_error,
}
"""The diagrams a caller can ask for by name.

Keyed by a stable name rather than the function, so a consumer names what
it wants and is not coupled to this module's internals.
"""


def _use_report_font() -> None:
    """Register the bundled typeface, as the page does.

    A figure that renders in a different face is not the report's figure.
    """
    matplotlib.font_manager.fontManager.addfont(
        str(importlib.resources.files(Anuphan).joinpath("Anuphan.ttf"))
    )
    rcParams["font.family"] = ["Anuphan", *rcParams["font.family"]]


def render_figure(
    analysis: ColourPrecisionAnalysis,
    name: str,
    *,
    fmt: str = "svg",
    size: tuple[float, float] = (6.5, 6.0),
    dpi: int = 130,
) -> bytes:
    """Render one report diagram.

    Parameters
    ----------
    analysis : ColourPrecisionAnalysis
        The analysis to draw, as `render_report_pdf` takes.
    name : str
        A key of `FIGURES`.
    fmt : str
        Any format matplotlib writes: "svg" (the default, and what a
        browser should be given), "pdf", or "png" for a caller that
        genuinely needs pixels. Text is drawn as paths, so the report's
        typeface survives into a viewer that has never seen the font.
    size : tuple[float, float]
        Figure size in inches. The default suits a single diagram on a
        web page rather than a tile of the printed page.
    dpi : int
        Resolution for the raster elements a vector format still has to
        embed -- the chromaticity diagram's colour field is a continuous
        gradient and cannot be paths.

    Returns
    -------
    bytes
        The diagram in `fmt`.

    Raises
    ------
    KeyError
        `name` is not a figure this report draws.
    """
    try:
        plot = FIGURES[name]
    except KeyError:
        raise KeyError(
            f"{name!r} is not a report figure; this report draws {sorted(FIGURES)}"
        ) from None

    _use_report_font()
    # Text as paths, so a browser that has never seen Anuphan still shows
    # the report's lettering rather than substituting its own.
    rcParams["svg.fonttype"] = "path"

    figure = plt.figure(figsize=size, facecolor=(1, 1, 1), dpi=dpi)
    try:
        ax: Axes = figure.add_subplot()
        plot(analysis, ax)
        buffer = io.BytesIO()
        # `bbox_inches="tight"` because the page's spacing is the page's,
        # not this figure's.
        figure.savefig(buffer, format=fmt, facecolor=(1, 1, 1), bbox_inches="tight")
    finally:
        # pyplot holds every figure it makes; a server rendering one per
        # view would grow without bound. Closed on the failure path too.
        plt.close(figure)

    return buffer.getvalue()
