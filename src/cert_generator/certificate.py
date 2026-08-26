"""Assemble the certificate: attestation, plus identity, plus what was left out.

## The honest template, which is the product rather than a caveat

A certificate here never says "100 % match", and the reason is commercial as much
as ethical. A flat pass tells an incoming-inspection team nothing they can audit:
it hides the denominator. This one says *N invariants checked over M entities; K
declined, each with a machine-readable reason; and here is what was not part of the
judgment at all.* A reader can act on that. A reader cannot act on a tick.

The `not_part_of_this_judgment` block is therefore mandatory and is emitted even
when every list in it is empty -- an absent section reads as "nothing was left
out", which is a claim, and not one this artifact is entitled to make.

## The one prohibition

Identity flows *into* the certificate and never back toward the audit inputs.
Nothing in this package constructs a walk, a configuration or a supplemental
declaration; the certificate is a projection of evidence that already existed
before the serial number was known. `tests/test_boundary.py` enforces it by
reading this package's imports, because a rule kept only by review is a rule that
survives exactly as long as the reviewer's attention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import CERTIFICATE_FORMAT, __version__
from . import coverage as coverage_module
from .identity import Identity

try:
    # The referee's *shipped* validators, not copies of its rules. A second
    # implementation of one format is a second implementation that will drift,
    # and the tool ships these precisely so a recipient can run them.
    from bmc_sensor_audit.detect.attestation import (ATTESTATION_FORMAT,
                                                     validate_attestation)
    from bmc_sensor_audit.inventory.redfish import validate_walk, walk_digest
except ImportError as error:                                 # pragma: no cover
    # The requirement is DERIVED from this package's own metadata, never
    # restated. It was restated once and went stale at the next release: the
    # string said `>=0.1.1,<0.2` while pyproject.toml said something else, and
    # the only reader who ever sees this line is somebody already stuck.
    def _declared() -> str:
        try:
            from importlib.metadata import requires
            for req in requires("odm-cert-generator") or ():
                if req.split(";")[0].strip().startswith("bmc-sensor-audit"):
                    return req.split(";")[0].strip()
        except Exception:                                    # pragma: no cover
            pass
        return "bmc-sensor-audit"
    raise ImportError(
        "cert-generator validates its input with the audit tool's own "
        "validate_attestation and walk_digest, so bmc-sensor-audit must be "
        f"installed: pip install '{_declared()}'") from error

__all__ = ["CertificateError", "Capture", "build_certificate",
           "capture_from_walk", "capture_from_digest", "ATTESTATION_FORMAT"]

#: A content handle: `sha256:` and sixty-four hex characters, the audit tool's
#: own shape. Held here so a malformed one is refused before it is printed.
_HANDLE = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class Capture:
    """Which walk a certificate was judged from, and how firmly we know it.

    **`verified` is the whole reason this is a pair rather than a string.** A
    handle computed here from a file this program read is a measurement; a handle
    typed in from a run log is a transcription. Both are legitimate -- a clean
    orchestrator run deletes its walks long before a certificate is rendered, so
    often the handle is all that survives -- and they support different claims, so
    the record carries which one it is rather than flattening them.
    """

    digest: str
    verified: bool


def capture_from_walk(path: str | Path) -> Capture:
    """Read the walk and compute its handle with the audit tool's own function.

    Refuses a file the tool's validator refuses. Reading a walk is not a boundary
    crossing -- a walk carries no identity by construction, because the audit tool
    serialises the parsed sensor set and never the raw payloads. Identity flows
    into this package and never back out toward an audit input.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise CertificateError(f"cannot read the walk at {path}: {error}") from None
    try:
        import json

        payload = json.loads(raw)
    except ValueError as error:
        raise CertificateError(
            f"{path} is not parseable as JSON: {error}") from None
    problems = validate_walk(payload)
    if problems:
        raise CertificateError(
            "the walk was refused by the audit tool's own validator, so this "
            "certificate will not cite it: " + "; ".join(problems))
    return Capture(digest=walk_digest(raw), verified=True)


def capture_from_digest(value: str) -> Capture:
    """Record a handle produced elsewhere. Nothing here checked it, and the
    certificate says so."""
    return Capture(digest=(value or "").strip(), verified=False)

# Words this document does not use about itself. Checked by test rather than by
# habit: the honest template is the differentiator, and the failure mode is a
# well-meaning edit that reintroduces a summary line reading "PASS".
FORBIDDEN_CLAIMS = ("100%", "100 %", "fully compliant", "all clear",
                    "certified compliant", "no issues", "passed all")


class CertificateError(ValueError):
    """The certificate cannot be built. Carries every reason at once."""


def build_certificate(attestation: Any, identity: Identity, *,
                      coverage: Any = None,
                      capture: Capture | None = None,
                      now: datetime | None = None) -> dict:
    """Refuse a shapeless artifact; otherwise project it into a certificate.

    Validation happens before anything is rendered, and the artifact is refused
    rather than decorated -- a certificate built on an artifact nobody could parse
    would be a document whose authority came entirely from its layout.
    """
    problems = validate_attestation(attestation)
    if problems:
        raise CertificateError(
            "the attestation was refused by the audit tool's own validator, so "
            "nothing was rendered: " + "; ".join(problems))

    stamped = (now or datetime.now(timezone.utc)).replace(microsecond=0)

    if capture is not None and not _HANDLE.fullmatch(capture.digest or ""):
        raise CertificateError(
            f"the capture handle {capture.digest!r} is not `sha256:` followed by "
            f"sixty-four hex characters. A certificate that printed an unusable "
            f"handle would look like proof and match nothing")

    if coverage is None:
        diff = coverage_module.absent()
    else:
        diff = coverage_module.summarise(coverage)

    findings = [dict(f) for f in attestation["findings"]]
    declined = [dict(d) for d in attestation["not_checked"]]
    checked = attestation.get("checked") or {}
    invariants = checked.get("invariants")
    entities = checked.get("entities")

    return {
        "format": CERTIFICATE_FORMAT,
        "generator": {
            # The DISTRIBUTION name, not the command. A recipient checking where
            # a certificate came from needs a string that resolves on an index,
            # and the two differ here: PyPI refuses `cert-generator` as too
            # similar to an existing `certgenerator`, so the project publishes
            # as `odm-cert-generator` while the command it installs stays
            # `cert-generator`.
            "name": "odm-cert-generator",
            "version": __version__,
            "rendered_at": stamped.isoformat(),
        },
        "identity": identity.to_dict(),
        "judgment": {
            "verdict": "findings recorded" if findings else "no findings recorded",
            "invariants_checked": invariants,
            "entities_checked": entities,
            "finding_count": len(findings),
            "declined_count": len(declined),
            "statement": _statement(invariants, entities, len(findings),
                                    len(declined)),
            "findings": findings,
            "declined": declined,
            "measurements": [dict(e) for e in attestation["evidence"]],
        },
        # Mandatory, and emitted even when empty. See the module docstring.
        "not_part_of_this_judgment": {
            "engine_boundary": (attestation.get("engine") or {}).get("boundary"),
            "unattested": list(attestation.get("unattested") or []),
            "unread_feeds": list(attestation.get("unread_feeds") or []),
            "declaration_diff": diff,
        },
        "source": {
            "attestation_format": attestation.get("format"),
            "engine_schema_version": (attestation.get("engine") or {}).get(
                "schema_version"),
            "target_label": attestation.get("target"),
            # Which CAPTURE this judgment was made from, when the caller supplied
            # one. `None` rather than absent when it did not: a certificate that
            # silently omits the key reads like one whose capture is beyond doubt.
            "walk_digest": capture.digest if capture else None,
            # Whether THIS program computed the handle from a file it read, or was
            # handed the value. Both are legitimate -- the walk is often deleted
            # long before a certificate is rendered -- and they are not the same
            # claim, so the record says which.
            "walk_digest_verified": capture.verified if capture else None,
        },
    }


def _statement(invariants: Any, entities: Any, findings: int,
               declined: int) -> str:
    """The denominator, in one sentence, with nothing rounded away."""
    if invariants is None or entities is None:
        # Reported rather than defaulted to zero. A missing count is not a count
        # of none, and writing 0 here would turn an unknown into a measurement.
        head = "the attestation does not record how many invariants were checked"
    else:
        head = (f"{invariants} invariant(s) checked over {entities} entit(ies)")
    return (f"{head}; {findings} finding(s) recorded; "
            f"{declined} check(s) declined and therefore not judged")


def has_findings(certificate: dict) -> bool:
    return bool(certificate["judgment"]["findings"])


def has_coverage_regression(certificate: dict) -> bool:
    """A declared sensor that never appeared is a regression the unit owns.

    Read off the scrubbed diff rather than the audit tool's exit code, because the
    certificate is built from artifacts and may be rendered long after the run.
    """
    diff = certificate["not_part_of_this_judgment"]["declaration_diff"]
    return bool(diff.get("present")) and any(
        f.get("regression") for f in diff.get("findings", []))
