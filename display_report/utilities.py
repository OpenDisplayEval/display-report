"""
display-report utilities
"""

import logging
import re
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version

BASE_LOGGER_NAME = "display_report"
DISTRIBUTION_NAME = "display-report"

__all__ = ["get_logger", "get_valid_filename", "tool_identifier"]


def tool_identifier() -> str:
    """Name and version of this tool, for measurement-file provenance.

    Written to ``CSMF_Metadata.software`` and shown on the report header so a
    result can be traced back to the code that produced it. The version comes
    from git tags via hatch-vcs.

    Returns
    -------
    str
        For example ``"display-report 0.2.1"``.
    """
    try:
        return f"{DISTRIBUTION_NAME} {version(DISTRIBUTION_NAME)}"
    except PackageNotFoundError:
        # Running from a source tree that was never installed.
        return f"{DISTRIBUTION_NAME} unknown-version"


class SuspiciousFileOperationError(Exception):
    """Generated when a user does something suspicious with file names"""


def get_valid_filename(name: str) -> str:
    """Clean / validate filename string

    Parameters
    ----------
    name : str
        The string to be cleaned for file name validity

    Returns
    -------
    str
        A clean filename

    Raises
    ------
    SuspiciousFileOperation
        if the cleaned string looks like a spooky filepath (i.e. '/', '.', etc...)
    """
    s = str(name).strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    s = re.sub(r"_+-+_+", "__", s)
    if s in {"", ".", ".."}:
        raise SuspiciousFileOperationError(f"Could not derive file name from '{name}'")
    return s


def get_logger(name: str = "") -> logging.Logger:
    """Create a logger for the display_report package

    Parameters
    ----------
    name : str, default ""
        Names a sub-logger for level management. Default "" returns the base
        logger for display_report

    Returns
    -------
    logging.Logger
    """
    if name == "":
        return logging.getLogger(f"{BASE_LOGGER_NAME}")
    return logging.getLogger(f"{BASE_LOGGER_NAME}.{name}")


SYSTEM_TIME_ZONE = tz = datetime.now().astimezone().tzinfo


def datetime_now() -> datetime:
    """Return time zone aware datetime object

    Returns
    -------
    datetime
    """

    return datetime.now(tz=SYSTEM_TIME_ZONE)


BASE_LOGGER = get_logger()
BASE_LOGGER.setLevel("INFO")
BASE_LOGGER.addHandler(logging.StreamHandler(sys.stdout))
