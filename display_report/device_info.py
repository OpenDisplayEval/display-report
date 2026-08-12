"""Device information capture for LED display measurements.

Provides a structured ``DeviceInfo`` dataclass for LED hardware metadata and an
interactive TTY wizard that collects the information at measurement time.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from specio.serialization import CSMF_Metadata

from display_report.utilities import datetime_now, tool_identifier

if TYPE_CHECKING:
    from argparse import Namespace

_SEPARATOR = "---OLE-DEVICE-INFO---"
_FORMAT_VERSION = 1


@dataclass
class DeviceInfo:
    """Structured metadata for the device under test.

    Parameters
    ----------
    led_processor : str
        The LED processor / video controller driving the display.
    led_panel : str
        The LED panel model.
    receiver_card_firmware : str | None
        Receiver card firmware version, if known.
    driver_chip : str | None
        LED driver chip model, if known.
    led_type : str | None
        LED package type, if known.
    firmware_version : str | None
        General firmware or hardware version, if known.
    """

    led_processor: str
    led_panel: str
    receiver_card_firmware: str | None = None
    driver_chip: str | None = None
    led_type: str | None = None
    firmware_version: str | None = None

    @property
    def display_name(self) -> str:
        """Human-readable summary suitable for report headers."""
        return f"{self.led_processor} / {self.led_panel}"

    def to_notes_string(self) -> str:
        """Serialize to a string for ``CSMF_Metadata.notes``.

        Format::

            Novastar MX40 Pro / Absen PL2.5 Pro
            ---OLE-DEVICE-INFO---
            {"v": 1, ...}
        """
        payload = {k: v for k, v in asdict(self).items() if v is not None}
        payload["v"] = _FORMAT_VERSION
        return f"{self.display_name}\n{_SEPARATOR}\n{json.dumps(payload)}"

    def to_metadata(self) -> CSMF_Metadata:
        """Wrap into a ``CSMF_Metadata`` instance."""
        return CSMF_Metadata(notes=self.to_notes_string(), software=tool_identifier())

    @classmethod
    def from_notes_string(cls, notes: str) -> DeviceInfo | None:
        """Parse a ``CSMF_Metadata.notes`` value.

        Parameters
        ----------
        notes : str
            The raw notes string from a CSMF file.

        Returns
        -------
        DeviceInfo | None
            A ``DeviceInfo`` if the notes contain structured data, otherwise
            ``None`` (legacy plain-text notes).
        """
        if _SEPARATOR not in notes:
            return None
        parts = notes.split(_SEPARATOR, maxsplit=1)
        if len(parts) != 2:
            return None
        try:
            data = json.loads(parts[1].strip())
        except json.JSONDecodeError:
            return None
        return cls(
            led_processor=data.get("led_processor", ""),
            led_panel=data.get("led_panel", ""),
            receiver_card_firmware=data.get("receiver_card_firmware"),
            driver_chip=data.get("driver_chip"),
            led_type=data.get("led_type"),
            firmware_version=data.get("firmware_version"),
        )


def run_device_wizard() -> DeviceInfo:
    """Run an interactive TTY wizard to collect device metadata.

    Returns
    -------
    DeviceInfo
        Populated from user responses.
    """
    import questionary

    print("\nDevice Under Test")
    print("─────────────────")

    led_processor = questionary.text(
        "LED Processor (required):",
        validate=lambda val: len(val.strip()) > 0 or "This field is required.",
    ).unsafe_ask()

    led_panel = questionary.text(
        "LED Panel (required):",
        validate=lambda val: len(val.strip()) > 0 or "This field is required.",
    ).unsafe_ask()

    firmware_version = questionary.text(
        "Firmware / Hardware Version (if known):",
    ).unsafe_ask()

    receiver_card_firmware = questionary.text(
        "Receiver Card Firmware (if known):",
    ).unsafe_ask()

    driver_chip = questionary.text(
        "Driver Chip (if known):",
    ).unsafe_ask()

    led_type = questionary.text(
        "LED Type (if known):",
    ).unsafe_ask()

    return DeviceInfo(
        led_processor=led_processor.strip(),
        led_panel=led_panel.strip(),
        receiver_card_firmware=receiver_card_firmware.strip() or None,
        driver_chip=driver_chip.strip() or None,
        led_type=led_type.strip() or None,
        firmware_version=firmware_version.strip() or None,
    )


def resolve_device_metadata(args: Namespace) -> CSMF_Metadata:
    """Determine device metadata from CLI args or interactive wizard.

    Priority:
    1. ``--device-name`` provided → legacy plain-text notes.
    2. stdin is a TTY → run the interactive wizard.
    3. Non-interactive → timestamp default.

    Parameters
    ----------
    args : Namespace
        Parsed CLI arguments. Must contain ``device_name``, which is ``None``
        when the flag was not supplied.

    Returns
    -------
    CSMF_Metadata
    """
    if args.device_name is not None:
        return CSMF_Metadata(notes=args.device_name, software=tool_identifier())

    if sys.stdin.isatty():
        device_info = run_device_wizard()
        return device_info.to_metadata()

    return CSMF_Metadata(
        notes=datetime_now().strftime("Device Measurements %y-%m-%d %H:%M"),
        software=tool_identifier(),
    )
