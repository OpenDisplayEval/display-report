"""
Implements control of external test pattern generators.
"""

import numpy as np
import requests
from numpy.typing import ArrayLike

from ole.utilities import get_logger

TPG_LOG = get_logger(__name__)


class TPGController:
    """A controller class to send display commands to a bmd-signal-gen server.

    bmd-signal-gen outputs test patterns via a Blackmagic DeckLink card,
    bypassing OS/GPU color management for deterministic signal output.

    See https://github.com/OpenLEDEval/bmd-signal-gen
    """

    @property
    def ip(self) -> str:
        """IP address of the TPG server

        Returns
        -------
        str
            IP string
        """
        return self._ip

    def __init__(self, ip: str, port: int = 4844):
        """Create a controller object for a bmd-signal-gen server.

        Parameters
        ----------
        ip : str
            IP address of the bmd-signal-gen server
        port : int, optional
            Port number, by default 4844
        """
        self._ip = ip
        self._port = port
        self._base_url = f"http://{ip}:{port}"
        TPG_LOG.info(f"Setting up TPG Controller for {self._base_url}")

    def send_color(self, color: tuple[float, float, float] | ArrayLike):
        """Send a color to the bmd-signal-gen server. Color values should be
        integers in the device's native bit depth (e.g. 0-255 for 8-bit,
        0-1023 for 10-bit, 0-4095 for 12-bit).

        Parameters
        ----------
        color : tuple[float, float, float] | np.ndarray
            The color to set as an RGB 3-vector.

        Raises
        ------
        ValueError
            if the requested color is not a valid 3-vector
        ConnectionError
            from any other exceptions
        """
        color = np.asarray(color, np.float64)
        if color.shape != (3,):
            raise ValueError("color must be a 3 vector!")

        try:
            url = f"{self._base_url}/update_color"
            payload = {"colors": [[color[0], color[1], color[2]]]}

            requests.post(url, json=payload, timeout=5)
            TPG_LOG.debug(
                f"Sending color: {color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f}"
            )
        except Exception as e:
            raise ConnectionError("Could not send test color.") from e
