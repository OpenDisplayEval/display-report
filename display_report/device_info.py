"""Device metadata carried in a measurement file's notes.

``DeviceInfo`` round-trips LED hardware metadata through
``CSMF_Metadata.notes`` so the report header can name the display it is
reporting on. Reading only: the wizard that collected this at measurement
time left with the measure path (SPEC.md §spec:scope), and the tool that
writes the file now records it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

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
