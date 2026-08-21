"""Unit identity: the half of a certificate the referee refuses to carry.

`bmc-sensor-audit` keeps serial numbers out of every output it produces, and that
hygiene is deliberate -- an artifact uploaded from CI should not publish which
machine it came from. A QC certificate has the opposite obligation: a certificate
that cannot name the unit certifies nothing.

So identity enters here, at the presentation layer, and never travels the other
way. See `certificate.py` for the prohibition that keeps it one-directional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["Identity", "IdentityError", "load_identity", "REQUIRED", "OPTIONAL"]

# Required because a certificate without them is not a certificate. `serial`
# names the unit, `work_order` ties it to the job, `station` and `signer` say
# where and by whom -- the four a QC record is asked for in an audit.
REQUIRED = ("serial", "work_order", "station", "signer")

# Accepted and rendered when present. Nothing here is inferred: an absent field
# is absent, never guessed from a neighbouring one.
OPTIONAL = ("part_number", "model", "customer", "line", "notes")


class IdentityError(ValueError):
    """The identity block cannot be used. Carries every problem, not the first."""


@dataclass(frozen=True)
class Identity:
    serial: str
    work_order: str
    station: str
    signer: str
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        block = {name: getattr(self, name) for name in REQUIRED}
        block.update(self.extra)
        return block


def _problems(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return [f"the identity block is {type(raw).__name__}, not an object"]

    problems: list[str] = []
    for name in REQUIRED:
        value = raw.get(name)
        if value is None:
            problems.append(f"{name!r} is missing; a certificate must carry it")
        elif not isinstance(value, str):
            problems.append(f"{name!r} is {type(value).__name__}, not a string")
        elif not value.strip():
            # A blank string is worse than an absent one: it renders as an empty
            # field on the PDF and reads as though the question was answered.
            problems.append(f"{name!r} is blank; an empty field on a certificate "
                            f"reads as an answered question")

    unknown = sorted(set(raw) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        # Refused rather than passed through. An identity file is operator-written
        # and a typo in a key would otherwise vanish silently -- the field simply
        # would not appear, and nobody reads a certificate looking for what is not
        # on it.
        problems.append(
            "unknown identity field(s) " + ", ".join(repr(u) for u in unknown)
            + f"; accepted fields are {', '.join(REQUIRED + OPTIONAL)}")

    for name in OPTIONAL:
        if name in raw and not isinstance(raw[name], str):
            problems.append(f"{name!r} is {type(raw[name]).__name__}, not a string")

    return problems


def load_identity(source: Any) -> Identity:
    """Build an `Identity` from a path or an already-parsed object.

    Raises `IdentityError` listing every problem at once, so an operator fixes the
    file in one pass instead of learning one fault per run.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise IdentityError(f"no identity file at {path}") from error
        except json.JSONDecodeError as error:
            raise IdentityError(f"{path} is not valid JSON: {error}") from error
    else:
        raw = source

    problems = _problems(raw)
    if problems:
        raise IdentityError("; ".join(problems))

    return Identity(
        serial=raw["serial"].strip(),
        work_order=raw["work_order"].strip(),
        station=raw["station"].strip(),
        signer=raw["signer"].strip(),
        extra={k: raw[k].strip() for k in OPTIONAL if k in raw and raw[k].strip()},
    )
