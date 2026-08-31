"""Display analysis and fidelity reporting.

Reporting is a pure function of a measurement file (SPEC.md §spec:scope): no
name here reaches an instrument or a signal generator. Public names resolve
lazily, so importing this package costs nothing beyond the standard library.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

_EXPORTS = {
    "ColourPrecisionAnalysis": "display_report.analysis",
    "ReflectanceData": "display_report.analysis",
    "analyze_measurements_from_file": "display_report.analysis",
    "generate_report_page": "display_report.pdf",
    "render_report_pdf": "display_report.pdf",
    "FIGURES": "display_report.figures",
    "render_figure": "display_report.figures",
    "SignalContract": "display_report.provenance",
    "ProvenanceError": "display_report.provenance",
    "read_provenance": "display_report.provenance",
    "contract_from": "display_report.provenance",
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
    from display_report.figures import FIGURES as FIGURES
    from display_report.figures import render_figure as render_figure
    from display_report.pdf import generate_report_page as generate_report_page
    from display_report.pdf import render_report_pdf as render_report_pdf
    from display_report.provenance import ProvenanceError as ProvenanceError
    from display_report.provenance import SignalContract as SignalContract
    from display_report.provenance import contract_from as contract_from
    from display_report.provenance import read_provenance as read_provenance
