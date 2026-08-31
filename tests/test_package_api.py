"""Tests for the display_report package public API."""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys

import pytest

# No export needs a device. The measure path left with the session core
# (SPEC.md §spec:scope), so every public name resolves on any machine.
HARDWARE_EXPORTS: frozenset[str] = frozenset()


class TestPackageShape:
    """The package must be a regular package with a working public API."""

    def test_is_regular_package(self):
        """A stray space in the filename silently demotes this to a namespace
        package, which drops every re-export."""
        module = importlib.import_module("display_report")

        assert module.__file__ is not None
        assert module.__file__.endswith("/__init__.py")

    def test_declares_public_exports(self):
        module = importlib.import_module("display_report")

        assert module.__all__

    def test_every_export_is_mapped(self):
        module = importlib.import_module("display_report")

        assert set(module.__all__) == set(module._EXPORTS)

    def test_every_export_points_at_a_real_module(self):
        """Catches typos in the lazy table without importing the targets."""
        module = importlib.import_module("display_report")

        for name, module_name in module._EXPORTS.items():
            assert importlib.util.find_spec(module_name) is not None, (
                f"{name} maps to missing module {module_name}"
            )

    def test_software_exports_resolve(self):
        module = importlib.import_module("display_report")

        for name in set(module.__all__) - HARDWARE_EXPORTS:
            assert hasattr(module, name), f"{name} declared but not reachable"

    def test_dir_lists_lazy_exports(self):
        module = importlib.import_module("display_report")

        assert set(module.__all__) <= set(dir(module))


class TestHardwareFreeImport:
    """Reporting needs a file, not a rig (SPEC.md §spec:scope)."""

    def test_import_does_not_load_signal_backend(self):
        """`bmd_sg` loads libdecklink.dylib at import time, so a machine
        without the DeckLink SDK could not import a package that pulled it
        in. Nothing here depends on it now; this holds the line."""
        probe = "import display_report, sys; print('bmd_sg' in sys.modules)"
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "False"

    def test_analysis_exports_resolve(self):
        from display_report import (
            ColourPrecisionAnalysis,
            ReflectanceData,
            analyze_measurements_from_file,
            generate_report_page,
        )

        assert ColourPrecisionAnalysis is not None
        assert ReflectanceData is not None
        assert callable(analyze_measurements_from_file)
        assert callable(generate_report_page)

    def test_no_export_reaches_a_device(self):
        """The validator owns no measure path (SPEC.md §spec:scope).

        A device name back in the public API means the ungated path came
        back with it.
        """
        module = importlib.import_module("display_report")

        retired = {
            "TPGController",
            "DisplayMeasureController",
            "ProgressCallback",
            "ProgressPrinter",
            "ProgressUpdate",
            "PQ_TestColorsConfig",
            "TestColors",
            "TestColorsConfig",
            "generate_colors",
        }

        assert retired.isdisjoint(module.__all__)

    def test_cli_module_imports_without_signal_backend(self):
        probe = "import display_report.cli, sys; print('bmd_sg' in sys.modules)"
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "False"

    def test_unknown_attribute_raises_attribute_error(self):
        module = importlib.import_module("display_report")

        with pytest.raises(AttributeError, match="NotAThing"):
            _ = module.NotAThing


class TestCommandLine:
    """`display-report <command>` dispatch."""

    def test_no_arguments_prints_usage_and_fails(self, capsys):
        from display_report.cli import main

        assert main([]) == 2
        assert "usage: display-report <command>" in capsys.readouterr().err

    def test_help_succeeds_and_lists_every_command(self, capsys):
        from display_report.cli import COMMANDS, main

        assert main(["--help"]) == 0

        out = capsys.readouterr().out
        for name in COMMANDS:
            assert name in out

    def test_unknown_command_fails(self, capsys):
        from display_report.cli import main

        assert main(["bogus"]) == 2
        assert "unknown command 'bogus'" in capsys.readouterr().err

    def test_no_measure_command(self):
        """The measure loop left with the session core (SPEC.md §spec:scope)."""
        from display_report.cli import COMMANDS

        assert "measure" not in COMMANDS

    def test_every_command_targets_a_real_module(self):
        from display_report.cli import COMMANDS

        for name, (module_name, _) in COMMANDS.items():
            assert importlib.util.find_spec(module_name) is not None, (
                f"{name} maps to missing module {module_name}"
            )

    def test_dispatch_rewrites_and_restores_argv(self):
        from display_report import cli

        seen = []
        probe = type(sys)("_display_report_probe")
        probe.main = lambda: seen.append(list(sys.argv))

        sys.modules["_display_report_probe"] = probe
        cli.COMMANDS["_probe"] = ("_display_report_probe", "")
        before = list(sys.argv)
        try:
            assert cli.main(["_probe", "--flag", "value"]) == 0
        finally:
            del cli.COMMANDS["_probe"]
            del sys.modules["_display_report_probe"]

        assert seen == [["display-report _probe", "--flag", "value"]]
        assert sys.argv == before
