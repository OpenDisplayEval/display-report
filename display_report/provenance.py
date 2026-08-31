"""The provenance block that rides with the seam file.

The measurement file states what produced it (SPEC.md §spec:report-input):
the protocol, the declared signal contract, the attested panel state and
the hash chain. CSMF models none of that, so it travels in the reserved
`ancillary` field the format sets aside for exactly this, and the seam
stays one file.

Reading it is the whole reason the analysis need not assume an encoding
(§spec:contract-analysis). A reporting tool that hardcodes one can only
report on displays configured that way, and silently misreports the rest.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from specio.serialization.csmf import CSMF_Data

# The envelope: a header naming the schema and the digest, the marker, then
# the canonical projection the digest covers.
_MARKER = "\n---\n"

PROVENANCE_SCHEMA = "color-wrangler/measurements-provenance/1"


class ProvenanceError(ValueError):
    """The provenance block is absent, unreadable, or does not verify."""


@dataclass(frozen=True)
class SignalContract:
    """What the display was driven at, as the file declares it.

    `transfer_function` is lowercase and vendor-neutral: "pq" or "gamma".
    `gamma_value` is the exponent where the transfer function is a pure
    power law, and None otherwise -- PQ takes no exponent. PQ is absolute
    and needs no peak; a power law is relative, so `peak_luminance`
    anchors it.

    `declared` is False for the fallback a file without a provenance block
    gets. The report says which, because an assumed encoding that is not
    announced is the failure this whole seam exists to prevent.
    """

    transfer_function: str
    bit_depth: int
    gamma_value: float | None = None
    peak_luminance: float | None = None
    declared: bool = True

    @property
    def peak_code(self) -> int:
        """The largest code the declared depth can carry.

        The analysis normalizes code values by this. A fixed 1023 is the
        same error as a fixed transfer function, and quieter: the curve
        still renders, at the wrong place.
        """
        return (1 << self.bit_depth) - 1

    def _power_law(self) -> tuple[float, float]:
        """The exponent and peak a power-law contract needs, or a refusal.

        PQ is absolute and carries its own anchor; a power law is relative
        and is meaningless without both.
        """
        if self.gamma_value is None:
            raise ProvenanceError(
                "a power-law contract needs its exponent, and this file declares none"
            )
        if self.peak_luminance is None:
            raise ProvenanceError(
                "a power-law contract needs the peak luminance it is "
                "relative to, and this file declares none"
            )
        return self.gamma_value, self.peak_luminance

    def eotf(self, normalized: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """Absolute luminance (cd/m2) for normalized code values."""
        if self.transfer_function == "pq":
            from colour.models.rgb.transfer_functions import st_2084 as pq

            return np.asarray(pq.eotf_ST2084(normalized), dtype=np.float64)

        gamma, peak = self._power_law()
        clipped = np.clip(np.asarray(normalized, dtype=np.float64), 0.0, None)
        return np.power(clipped, gamma) * peak

    def eotf_inverse(self, luminance: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """Normalized code values for absolute luminance (cd/m2)."""
        if self.transfer_function == "pq":
            from colour.models.rgb.transfer_functions import st_2084 as pq

            return np.asarray(pq.eotf_inverse_ST2084(luminance), dtype=np.float64)

        gamma, peak = self._power_law()
        relative = np.clip(np.asarray(luminance, dtype=np.float64) / peak, 0.0, None)
        return np.power(relative, 1.0 / gamma)


# What the reference format assumed before files said what they were. A file
# with no provenance block still analyzes, under this, and the report says it
# was assumed rather than read (§spec:contract-analysis).
ASSUMED_CONTRACT = SignalContract("pq", 10, declared=False)


def _split_envelope(text: str) -> tuple[str, str]:
    head, marker, projection = text.partition(_MARKER)
    if not marker:
        raise ProvenanceError(
            "the provenance block carries no projection marker, so its "
            "digest covers nothing"
        )
    return head, projection


def read_provenance(data: CSMF_Data) -> dict[str, Any]:
    """Return the artifact's canonical projection, parsed and verified.

    Raises
    ------
    ProvenanceError
        The block is missing, malformed, or its recorded digest does not
        match the projection it travels with.
    """
    import yaml

    raw = getattr(data, "ancillary", b"") or b""
    if not raw:
        raise ProvenanceError(
            "this measurement file carries no provenance block, so it does "
            "not say what protocol or signal contract produced it"
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ProvenanceError(f"the provenance block is not UTF-8: {e}") from e

    head_text, projection = _split_envelope(text)

    try:
        head = yaml.safe_load(head_text) or {}
        document = yaml.safe_load(projection) or {}
    except yaml.YAMLError as e:
        raise ProvenanceError(f"the provenance block is not valid YAML: {e}") from e

    schema = head.get("schema")
    if schema != PROVENANCE_SCHEMA:
        raise ProvenanceError(
            f"unknown provenance schema {schema!r}; this reader understands "
            f"{PROVENANCE_SCHEMA!r}"
        )

    # The digest covers the projection, never the file bytes: protobuf
    # guarantees round-trip, not canonical encoding, so a digest over the
    # container would rotate on a library upgrade rather than on a change
    # to the measurement.
    recorded = head.get("projection_sha256")
    computed = hashlib.sha256(projection.encode("utf-8")).hexdigest()
    if recorded != computed:
        raise ProvenanceError(
            "the provenance block does not verify: recorded "
            f"{recorded} but the projection hashes to {computed}"
        )

    return document


def contract_from(document: dict[str, Any]) -> SignalContract:
    """The declared signal contract, read rather than assumed.

    Raises
    ------
    ProvenanceError
        The document declares no contract, or one this analysis does not
        implement. Refusing by name beats approximating: an encoding
        guessed wrong produces a plausible chart and a wrong number.
    """
    processor_state = document.get("processor_state") or {}
    eotf = processor_state.get("eotf") or {}
    wire = document.get("wire_encoding") or {}

    declared = eotf.get("type")
    if declared is None:
        raise ProvenanceError(
            "the file declares no transfer function, so the analysis cannot "
            "linearize its code values without assuming one"
        )

    bit_depth = wire.get("bit_depth")
    if bit_depth is None:
        raise ProvenanceError(
            "the file declares no bit depth, so its code values have no scale"
        )

    peak_luminance = (document.get("luminance") or {}).get("peak_luminance")

    name = str(declared).strip().lower()
    if name in {"gamma", "power"}:
        gamma_value = eotf.get("gamma_value")
        if gamma_value is None:
            raise ProvenanceError("the file declares a gamma contract with no exponent")
        return SignalContract(
            "gamma",
            int(bit_depth),
            float(gamma_value),
            None if peak_luminance is None else float(peak_luminance),
        )
    if name in {"pq", "st2084", "st_2084", "smpte2084"}:
        return SignalContract(
            "pq",
            int(bit_depth),
            None,
            None if peak_luminance is None else float(peak_luminance),
        )

    raise ProvenanceError(
        f"this analysis does not implement the declared transfer function "
        f"{declared!r}; it implements PQ and pure-power gamma"
    )
