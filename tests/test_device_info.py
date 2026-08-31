"""Tests for display_report.device_info module."""

from __future__ import annotations

from display_report.device_info import (
    DeviceInfo,
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
