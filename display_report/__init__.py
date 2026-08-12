"""Display measurement, analysis, and fidelity reporting.

Public names resolve lazily. Importing this package therefore costs nothing
beyond the standard library, and analysis-only users are not required to have
the DeckLink SDK installed — ``TPGController`` pulls in ``bmd_sg``, which loads
``libdecklink.dylib`` at import time.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

_EXPORTS = {
    "ColourPrecisionAnalysis": "display_report.analysis",
    "ReflectanceData": "display_report.analysis",
    "analyze_measurements_from_file": "display_report.analysis",
    "generate_report_page": "display_report.pdf",
    "DisplayMeasureController": "display_report.measurement_controllers",
    "ProgressCallback": "display_report.measurement_controllers",
    "ProgressPrinter": "display_report.measurement_controllers",
    "ProgressUpdate": "display_report.measurement_controllers",
    "PQ_TestColorsConfig": "display_report.test_colors",
    "TestColors": "display_report.test_colors",
    "TestColorsConfig": "display_report.test_colors",
    "generate_colors": "display_report.test_colors",
    "TPGController": "display_report.tpg_controller",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Import and cache a public name on first access (PEP 562)."""
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})


if TYPE_CHECKING:
    # Redundant-looking `X as X` is the PEP 484 explicit re-export form. It
    # tells ruff and pyright these are the package's public names, which they
    # cannot infer from a computed __all__.
    from display_report.analysis import (
        ColourPrecisionAnalysis as ColourPrecisionAnalysis,
    )
    from display_report.analysis import (
        ReflectanceData as ReflectanceData,
    )
    from display_report.analysis import (
        analyze_measurements_from_file as analyze_measurements_from_file,
    )
    from display_report.measurement_controllers import (
        DisplayMeasureController as DisplayMeasureController,
    )
    from display_report.measurement_controllers import (
        ProgressCallback as ProgressCallback,
    )
    from display_report.measurement_controllers import (
        ProgressPrinter as ProgressPrinter,
    )
    from display_report.measurement_controllers import (
        ProgressUpdate as ProgressUpdate,
    )
    from display_report.pdf import generate_report_page as generate_report_page
    from display_report.test_colors import (
        PQ_TestColorsConfig as PQ_TestColorsConfig,
    )
    from display_report.test_colors import (
        TestColors as TestColors,
    )
    from display_report.test_colors import (
        TestColorsConfig as TestColorsConfig,
    )
    from display_report.test_colors import (
        generate_colors as generate_colors,
    )
    from display_report.tpg_controller import TPGController as TPGController
