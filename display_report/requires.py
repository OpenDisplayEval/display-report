"""What this analysis needs an artifact to carry (SPEC.md §spec:report-input).

The requirement lives here, with the code that reads it, and not in
display-measure. display-measure owns the measurement — which codes,
what spacing, under what conditions — because those satisfy invariants
a consumer does not know about. What a consumer owns is the statement
of what it cannot analyse without.

Stating it as data rather than as prose in an error message is the
point. The previous version of this was a string inside
`UnfilterableMeasurements` naming a protocol that had been renamed
since, which no test could catch and no reader could trust.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

# Block name -> the lowest version whose measurement this analysis can
# read. A block versions when its patches, their spacing, or the
# conditions it requires change, so a minimum is a real claim: it says
# this analysis was written against that measurement or a later one.
REQUIRES: dict[str, int] = {
    # Primaries, white point, black level, peak luminance. Everything
    # here is measured relative to these.
    "anchors": 1,
    # The spread across repeated black readings. The patch filter
    # divides by it; one reading has no spread and the filter rejects
    # every patch in the file.
    "noise-floor": 1,
    # The white point as a distribution, which the outlier-robust
    # primary-matrix fit needs points to be robust over.
    "white-repeat": 1,
    # Each channel against drive level. The EOTF and grey-tracking
    # pages are drawn against these.
    "response": 1,
    "tracking": 1,
    # The cube's interior. The chromaticity chart clusters measured
    # error through the volume, and clusters of an unmeasured volume
    # come back empty and duplicated, with the chart drawing anyway.
    "volume-mesh": 1,
}


# Artifacts written before blocks were recorded carry a protocol name
# instead. The names are few, released, and their block composition is
# known, so they map — which matters because every artifact measured to
# date is one of these, and a reader that shrugged at them would refuse
# nothing until the first new session.
LEGACY_PROTOCOL_BLOCKS: dict[str, dict[str, int]] = {
    "color-wrangler/characterize/1": {"anchors": 1, "response": 1, "additivity": 1},
    "color-wrangler/characterize/2": {"anchors": 1, "response": 1, "additivity": 1},
    "color-wrangler/characterize/3": {"anchors": 1, "response": 1, "additivity": 1},
}


class UnsupportedArtifact(ValueError):
    """The artifact does not carry what this analysis reads.

    Raised naming the blocks, because the operator's next action is to
    measure a suite that includes them, and a refusal that does not say
    which is a refusal they cannot act on.
    """


def parse_blocks(recorded: object) -> dict[str, int]:
    """Block name to version, from an artifact's `protocol.blocks`.

    An id is `name/version`. An unparseable entry is skipped rather than
    raising: a newer writer may record a form this reader predates, and
    the requirement check below reports what is missing either way.
    """
    blocks: dict[str, int] = {}
    if not isinstance(recorded, list | tuple):
        return blocks
    for entry in recorded:
        name, _, version = str(entry).partition("/")
        if name and version.isdigit():
            blocks[name] = int(version)
    return blocks


def blocks_carried(provenance: Mapping[str, object]) -> dict[str, int] | None:
    """What an artifact carries, or None when it says nothing about it.

    None is not "carries nothing": the reference format and third-party
    files record no protocol at all, and the analysis judges those on
    what it finds in them rather than refusing them for a field they
    never had.
    """
    protocol = provenance.get("protocol")
    if not isinstance(protocol, dict):
        return None
    recorded = protocol.get("blocks")
    if recorded is not None:
        return parse_blocks(recorded)
    name = protocol.get("name")
    if isinstance(name, str) and name in LEGACY_PROTOCOL_BLOCKS:
        return dict(LEGACY_PROTOCOL_BLOCKS[name])
    return None


def check(
    carried: Mapping[str, int], requires: Mapping[str, int] | None = None
) -> None:
    """Raise unless `carried` satisfies every requirement.

    Reports every shortfall at once. An operator who has to re-measure
    should learn the whole list on the first attempt, not one block per
    two-hour session.
    """
    requires = REQUIRES if requires is None else requires
    missing = sorted(name for name in requires if name not in carried)
    outdated = sorted(
        f"{name}/{carried[name]} (needs {minimum} or later)"
        for name, minimum in requires.items()
        if name in carried and carried[name] < minimum
    )
    if not missing and not outdated:
        return

    problems = []
    if missing:
        problems.append("does not carry " + ", ".join(missing))
    if outdated:
        problems.append("carries " + ", ".join(outdated))
    raise UnsupportedArtifact(
        "this artifact "
        + "; and ".join(problems)
        + ". The analysis reads "
        + ", ".join(sorted(requires))
        + " — measure a suite composing them "
        + "(`display-measure characterize --suite report`)."
    )
