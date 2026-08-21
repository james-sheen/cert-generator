"""The declaration diff, which `attestation/1` does not carry.

**The gap this module exists for, stated plainly.** An attestation records what
the engine judged: invariants checked, findings, declines, evidence. It does not
record what was *declared and never showed up*. Run the audit tool against a board
declaring four sensors where one is absent and the artifact reads
`checked: {invariants: 6, entities: 3}` -- three, with nothing on the artifact
saying three of four. The absent sensor is the single most important QC fact about
that unit and the attestation is silent on it.

So the certificate takes a second, optional input: the JSON from the tool's
`coverage --json`, a public surface that does carry the diff. Optional because
requiring it would make a certificate impossible for anyone who has only the
attestation; and when it is absent the certificate says so rather than letting the
smaller denominator pass as the whole picture.

**Filed upstream** as a request for a coverage block in a future attestation
format. Until that exists, this is the honest arrangement rather than the tidy one.

## Two fields are dropped, and dropping them is the point

`coverage --json` is written for a CI log, not for a customer. It carries
`target` -- the BMC's URL, which names an internal machine -- and `declared_in` /
`live_path`, filesystem paths from whatever host ran the walk. None of those
belong on a document that leaves the building. The audit tool already learned this
lesson once: `--attest-target-label` exists so an attestation can name a target
without publishing its hostname. This module applies the same rule to the input
that has no such flag.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["CoverageError", "load_coverage", "summarise", "DROPPED_FIELDS",
           "ABSENT_REASON"]

# Named as a constant so the privacy test asserts against one list rather than
# re-deriving what should have been removed.
DROPPED_FIELDS = ("target", "declared_in", "live_path")

ABSENT_REASON = (
    "no declaration diff was supplied, so this certificate cannot state how many "
    "declared sensors were present; the attestation counts only entities that "
    "reached the engine")

# The finding kinds the tool emits, mapped to prose a reader outside the project
# can act on. Unknown kinds are carried through verbatim rather than dropped --
# a kind this build has not seen is still a fact about the unit.
_KINDS = {
    "declared_absent": "declared in the configuration and not reported at all",
    "present_not_reading": "reported by the machine but carrying no reading",
    "undeclared_present": "reported by the machine and not declared anywhere",
    "not_a_sensor": "matched an entry that does not describe a sensor",
    "unrecognised_type": "declared with a type this build does not recognise",
}


class CoverageError(ValueError):
    """The coverage artifact cannot be used."""


def load_coverage(source: Any) -> dict:
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CoverageError(f"no coverage file at {path}") from error
        except json.JSONDecodeError as error:
            raise CoverageError(f"{path} is not valid JSON: {error}") from error
    else:
        raw = source

    if not isinstance(raw, dict):
        raise CoverageError(
            f"the coverage artifact is {type(raw).__name__}, not an object")
    counts = raw.get("counts")
    if not isinstance(counts, dict):
        raise CoverageError(
            "'counts' is missing or is not an object; without it the artifact "
            "carries no denominator, which is the only reason to read it here")
    if not isinstance(raw.get("findings"), list):
        raise CoverageError("'findings' is missing or is not a list")
    return raw


def summarise(raw: dict) -> dict:
    """The scrubbed declaration diff, ready to render.

    Every path and hostname the input carried is left behind here. See the module
    docstring: this is the whole reason the coverage artifact does not go into the
    certificate unchanged.
    """
    counts = raw["counts"]
    findings = []
    for finding in raw["findings"]:
        if not isinstance(finding, dict):
            continue
        kind = finding.get("kind")
        findings.append({
            "sensor": finding.get("sensor", "?"),
            "kind": kind,
            "statement": _KINDS.get(kind) or finding.get("detail")
                         or f"reported as {kind!r}",
            "regression": bool(finding.get("regression")),
        })

    declared = counts.get("declared")
    matched = counts.get("matched")
    return {
        "present": True,
        "declared": declared,
        "matched": matched,
        "reading": counts.get("reading"),
        "declared_absent": counts.get("declared_absent"),
        "present_not_reading": counts.get("present_not_reading"),
        "undeclared_present": counts.get("undeclared_present"),
        "walk_complete": bool(raw.get("walk_complete", False)),
        "findings": findings,
    }


def absent() -> dict:
    """What the certificate carries when no coverage artifact was supplied."""
    return {"present": False, "reason": ABSENT_REASON}
