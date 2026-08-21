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

from datetime import datetime, timezone
from typing import Any

from . import CERTIFICATE_FORMAT, __version__
from . import coverage as coverage_module
from .identity import Identity

try:
    # The referee's *shipped* validator, not a copy of its rules. A second
    # implementation of one format is a second implementation that will drift,
    # and the tool ships this one precisely so a recipient can run it.
    from bmc_sensor_audit.detect.attestation import (ATTESTATION_FORMAT,
                                                     validate_attestation)
except ImportError as error:                                 # pragma: no cover
    raise ImportError(
        "cert-generator validates its input with the audit tool's own "
        "validate_attestation, so bmc-sensor-audit must be installed: "
        "pip install 'bmc-sensor-audit>=0.1.0,<0.2'") from error

__all__ = ["CertificateError", "build_certificate", "ATTESTATION_FORMAT"]

# Words this document does not use about itself. Checked by test rather than by
# habit: the honest template is the differentiator, and the failure mode is a
# well-meaning edit that reintroduces a summary line reading "PASS".
FORBIDDEN_CLAIMS = ("100%", "100 %", "fully compliant", "all clear",
                    "certified compliant", "no issues", "passed all")


class CertificateError(ValueError):
    """The certificate cannot be built. Carries every reason at once."""


def build_certificate(attestation: Any, identity: Identity, *,
                      coverage: Any = None,
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
            "name": "cert-generator",
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
