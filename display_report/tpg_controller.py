"""
Implements control of a Blackmagic DeckLink device for test pattern generation.

Uses the bmd-signal-gen library to drive the DeckLink card directly, bypassing
OS/GPU colour management for deterministic signal output.

See https://github.com/OpenDisplayEval/bmd-signal-gen
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import bmd_sg
import numpy as np

from display_report.utilities import get_logger

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

TPG_LOG = get_logger(__name__)

# Preferred pixel formats in descending priority order.
# 12-bit RGB is preferred over 10-bit RGB for higher precision.
_PREFERRED_FORMATS = ("FORMAT_12BIT_RGB", "FORMAT_10BIT_RGB")


class TPGController:
    """A controller for driving a Blackmagic DeckLink card as a test pattern
    generator. Wraps ``bmd_sg.BMDDeckLink`` and ``bmd_sg.PatternGenerator``
    to send solid-colour test patches to a display.
    """

    @property
    def bit_depth(self) -> int:
        """Bit depth of the active pixel format.

        Returns
        -------
        int
            Bit depth (e.g. 8, 10, 12).
        """
        return self._pixel_format.bit_depth

    @property
    def max_color_value(self) -> int:
        """Maximum integer colour value for the active pixel format.

        Returns
        -------
        int
            ``2**bit_depth - 1`` (e.g. 1023 for 10-bit, 4095 for 12-bit).
        """
        return int(2**self.bit_depth - 1)

    def __init__(
        self,
        device_index: int = 0,
        pixel_format: str | None = None,
        width: int = 1920,
        height: int = 1080,
        hdr_metadata: bmd_sg.HDRMetadata | None = None,
    ) -> None:
        """Open a DeckLink device and prepare it for test pattern output.

        Parameters
        ----------
        device_index : int, optional
            Index of the DeckLink device to open, by default 0.
        pixel_format : str | None, optional
            Pixel format name (e.g. ``"FORMAT_12BIT_RGB"``). When ``None``,
            the highest-precision supported RGB format is auto-selected.
        width : int, optional
            Frame width in pixels, by default 1920.
        height : int, optional
            Frame height in pixels, by default 1080.
        hdr_metadata : HDRMetadata | None, optional
            HDR metadata to configure on the output. When ``None``, PQ
            metadata with default luminance values is applied if the device
            supports HDR.

        Raises
        ------
        RuntimeError
            If the device cannot be opened or configured.
        """
        self._decklink = bmd_sg.BMDDeckLink(device_index=device_index)
        TPG_LOG.info(f"Opened DeckLink device {device_index}")

        # Select pixel format
        if pixel_format is not None:
            self._pixel_format = bmd_sg.PixelFormatType[pixel_format]
        else:
            self._pixel_format = self._auto_select_pixel_format()

        self._decklink.pixel_format = self._pixel_format
        TPG_LOG.info(
            f"Pixel format: {self._pixel_format.name} "
            f"({self._pixel_format.bit_depth}-bit)"
        )

        # Configure HDR metadata
        if hdr_metadata is not None:
            self._decklink.set_hdr_metadata(hdr_metadata)
        elif self._decklink.supports_hdr:
            self._decklink.set_hdr_metadata(bmd_sg.HDRMetadata())
            TPG_LOG.info("Applied default PQ HDR metadata")

        self._decklink.start_playback()

        # Set up the pattern generator for solid-colour patches
        self._pattern_gen = bmd_sg.PatternGenerator(
            bit_depth=self._pixel_format.bit_depth,
            width=width,
            height=height,
        )
        self._width = width
        self._height = height

    def _auto_select_pixel_format(self) -> bmd_sg.PixelFormatType:
        """Choose the highest-precision supported RGB pixel format.

        Returns
        -------
        PixelFormatType
            The selected pixel format.

        Raises
        ------
        RuntimeError
            If no supported RGB format is found on the device.
        """
        supported = self._decklink.get_supported_pixel_formats()
        supported_names = {fmt.name for fmt in supported}

        for name in _PREFERRED_FORMATS:
            if name in supported_names:
                return bmd_sg.PixelFormatType[name]

        # Fall back to first supported format
        if supported:
            return supported[0]

        raise RuntimeError(
            "DeckLink device has no supported pixel formats. "
            "Check that DeckLink drivers are correctly installed."
        )

    def send_color(self, color: tuple[float, float, float] | ArrayLike) -> None:
        """Send a solid colour to the display. Colour values should be
        integers in the device's native bit depth (e.g. 0-255 for 8-bit,
        0-1023 for 10-bit, 0-4095 for 12-bit).

        Parameters
        ----------
        color : tuple[float, float, float] | ArrayLike
            The colour to display as an RGB 3-vector.

        Raises
        ------
        ValueError
            If the colour is not a valid 3-vector.
        ConnectionError
            If the frame cannot be sent to the device.
        """
        color = np.asarray(color, np.float64)
        if color.shape != (3,):
            raise ValueError("color must be a 3 vector!")

        try:
            frame = self._pattern_gen.generate(
                [color.tolist()],
            )
            self._decklink.display_frame(frame)
            TPG_LOG.debug(
                f"Sending color: {color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f}"
            )
        except Exception as e:
            raise ConnectionError("Could not send test color.") from e

    def close(self) -> None:
        """Stop playback and close the DeckLink device."""
        if hasattr(self, "_decklink") and self._decklink.is_open:
            self._decklink.stop_playback()
            self._decklink.close()
            TPG_LOG.info("DeckLink device closed")

    def __enter__(self) -> TPGController:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
