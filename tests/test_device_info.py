"""Tests for display_report.device_info module."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from display_report.device_info import (
    DeviceInfo,
    resolve_device_metadata,
    run_device_wizard,
)


class TestDeviceInfoRoundTrip:
    """Serialization round-trip tests for DeviceInfo."""

    def test_round_trip_all_fields(self):
        info = DeviceInfo(
            led_processor="Novastar MX40 Pro",
            led_panel="Absen PL2.5 Pro",
            receiver_card_firmware="4.7.2.0",
            driver_chip="ICN2153",
            led_type="Nationstar 2727",
            firmware_version="V5.4.2.8",
        )
        notes = info.to_notes_string()
        parsed = DeviceInfo.from_notes_string(notes)

        assert parsed is not None
        assert parsed.led_processor == info.led_processor
        assert parsed.led_panel == info.led_panel
        assert parsed.receiver_card_firmware == info.receiver_card_firmware
        assert parsed.driver_chip == info.driver_chip
        assert parsed.led_type == info.led_type
        assert parsed.firmware_version == info.firmware_version

    def test_round_trip_required_only(self):
        info = DeviceInfo(led_processor="Brompton SX40", led_panel="ROE BP2V2")
        notes = info.to_notes_string()
        parsed = DeviceInfo.from_notes_string(notes)

        assert parsed is not None
        assert parsed.led_processor == "Brompton SX40"
        assert parsed.led_panel == "ROE BP2V2"
        assert parsed.receiver_card_firmware is None
        assert parsed.driver_chip is None
        assert parsed.led_type is None
        assert parsed.firmware_version is None

    def test_display_name(self):
        info = DeviceInfo(led_processor="Novastar MX40", led_panel="Absen PL2.5")
        assert info.display_name == "Novastar MX40 / Absen PL2.5"


class TestFromNotesString:
    """Parsing tests for DeviceInfo.from_notes_string."""

    def test_legacy_plain_text_returns_none(self):
        assert (
            DeviceInfo.from_notes_string("Device Measurements 24-01-15 10:30") is None
        )

    def test_empty_string_returns_none(self):
        assert DeviceInfo.from_notes_string("") is None

    def test_arbitrary_text_returns_none(self):
        assert DeviceInfo.from_notes_string("My Custom Display Name") is None

    def test_invalid_json_after_separator_returns_none(self):
        notes = "Some Name\n---OLE-DEVICE-INFO---\nnot-json"
        assert DeviceInfo.from_notes_string(notes) is None

    def test_structured_notes_parsed_correctly(self):
        notes = (
            "Novastar MX40 Pro / Absen PL2.5 Pro\n"
            "---OLE-DEVICE-INFO---\n"
            '{"v": 1, "led_processor": "Novastar MX40 Pro", '
            '"led_panel": "Absen PL2.5 Pro", '
            '"firmware_version": "V5.4.2.8"}'
        )
        info = DeviceInfo.from_notes_string(notes)
        assert info is not None
        assert info.led_processor == "Novastar MX40 Pro"
        assert info.led_panel == "Absen PL2.5 Pro"
        assert info.firmware_version == "V5.4.2.8"
        assert info.driver_chip is None


class TestToMetadata:
    """Test DeviceInfo.to_metadata produces valid CSMF_Metadata."""

    def test_to_metadata_contains_separator(self):
        info = DeviceInfo(led_processor="Test", led_panel="Panel")
        meta = info.to_metadata()
        assert "---OLE-DEVICE-INFO---" in meta.notes


class TestResolveDeviceMetadata:
    """Tests for resolve_device_metadata."""

    def test_device_name_flag_skips_wizard(self):
        args = Namespace(device_name="My Display")
        meta = resolve_device_metadata(args)
        assert meta.notes == "My Display"

    def test_non_tty_uses_timestamp_default(self):
        args = Namespace(device_name=None)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            meta = resolve_device_metadata(args)
        assert meta.notes.startswith("Device Measurements ")

    def test_non_tty_never_runs_wizard(self):
        args = Namespace(device_name=None)
        with (
            patch("sys.stdin") as mock_stdin,
            patch("display_report.device_info.run_device_wizard") as mock_wizard,
        ):
            mock_stdin.isatty.return_value = False
            resolve_device_metadata(args)
        mock_wizard.assert_not_called()

    def test_tty_runs_wizard(self):
        args = Namespace(device_name=None)
        fake_info = DeviceInfo(led_processor="TestProc", led_panel="TestPanel")
        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "display_report.device_info.run_device_wizard", return_value=fake_info
            ),
        ):
            mock_stdin.isatty.return_value = True
            meta = resolve_device_metadata(args)
        assert "TestProc / TestPanel" in meta.notes
        assert "---OLE-DEVICE-INFO---" in meta.notes

    def test_device_name_flag_skips_wizard_on_tty(self):
        args = Namespace(device_name="My Display")
        with (
            patch("sys.stdin") as mock_stdin,
            patch("display_report.device_info.run_device_wizard") as mock_wizard,
        ):
            mock_stdin.isatty.return_value = True
            meta = resolve_device_metadata(args)
        mock_wizard.assert_not_called()
        assert meta.notes == "My Display"


class TestRunDeviceWizard:
    """Tests for run_device_wizard with mocked questionary input."""

    def test_wizard_collects_all_fields(self):
        responses = iter(
            [
                "Novastar MX40",
                "Absen PL2.5",
                "V5.4.2.8",
                "4.7.2.0",
                "ICN2153",
                "Nationstar 2727",
            ]
        )
        with patch("questionary.text") as mock_text:
            mock_text.return_value.unsafe_ask.side_effect = lambda: next(responses)
            info = run_device_wizard()

        assert info.led_processor == "Novastar MX40"
        assert info.led_panel == "Absen PL2.5"
        assert info.firmware_version == "V5.4.2.8"
        assert info.receiver_card_firmware == "4.7.2.0"
        assert info.driver_chip == "ICN2153"
        assert info.led_type == "Nationstar 2727"

    def test_wizard_optional_fields_empty(self):
        responses = iter(["Brompton SX40", "ROE BP2V2", "", "", "", ""])
        with patch("questionary.text") as mock_text:
            mock_text.return_value.unsafe_ask.side_effect = lambda: next(responses)
            info = run_device_wizard()

        assert info.led_processor == "Brompton SX40"
        assert info.led_panel == "ROE BP2V2"
        assert info.firmware_version is None
        assert info.receiver_card_firmware is None
        assert info.driver_chip is None
        assert info.led_type is None
