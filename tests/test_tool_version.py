"""Tests for tool-version provenance in measurement files and reports."""

from __future__ import annotations

import re

from display_report.device_info import DeviceInfo
from display_report.utilities import tool_identifier

# "display-report <version>", e.g. "display-report 0.0.1.dev0+g3ef8c24"
IDENTIFIER = re.compile(r"^display-report \S+$")


class TestToolIdentifier:
    def test_names_the_tool_and_a_version(self):
        assert IDENTIFIER.match(tool_identifier())

    def test_resolves_a_real_installed_version(self):
        """Guards the PackageNotFoundError fallback: a report stamped
        "unknown-version" carries no provenance at all."""
        version = tool_identifier().split(" ", 1)[1]

        assert version != "unknown-version"
        assert version[0].isdigit()

    def test_does_not_name_a_predecessor_project(self):
        """The stripper hardcoded "colour-workbench file stripper", writing a
        false provenance record naming a project this code left long ago."""
        identifier = tool_identifier().lower()

        assert "colour-workbench" not in identifier
        assert "ole" not in identifier.replace("display-report", "")


class TestReportHeader:
    """The rendered report states which version produced it."""

    def _header_text(self, device_info):
        from unittest.mock import MagicMock

        from display_report.pdf import plot_report_header
        from display_report.provenance import SignalContract

        axes = MagicMock()
        data = MagicMock()
        data.device_info = device_info
        data.shortname = "Panel A"
        # The header states the contract beside the version, and formats its
        # numbers, so this needs a real one rather than a mock.
        data.contract = SignalContract("gamma", 12, 2.35, 1800.0)
        data.provenance = {"protocol": {"name": "color-wrangler/characterize/3"}}

        plot_report_header(axes, data)

        return " ".join(
            str(arg)
            for call in axes.text.call_args_list
            for arg in call.args
            if isinstance(arg, str)
        )

    def test_version_shown_with_structured_device_info(self):
        info = DeviceInfo(led_processor="Brompton SX40", led_panel="ROE BP2V2")

        assert tool_identifier() in self._header_text(info)

    def test_version_shown_without_device_info(self):
        assert tool_identifier() in self._header_text(None)
