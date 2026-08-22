"""Check a rendered PDF against the certificate JSON it claims to project.

Shipped, not kept in a CI script, for the same reason `bmc-sensor-audit` ships its
attestation validator: the person who *receives* a certificate is the one who
needs to check it, and checking logic that lives inside a `run:` block cannot be
called by them, cannot be tested, and cannot be versioned alongside the thing it
checks.

**What it proves:** every number on the page also appears in the JSON. That is a
real property -- it catches a figure typed into the layout, a stale render left
beside an updated record, or a PDF paired with the wrong unit's JSON.

**What it does not prove:** that the JSON is true. Nothing here re-audits the
machine. The certificate's authority comes from the attestation, and the
attestation's from the engine; this checks only that the presentation layer did
not add to either.

**Reading a PDF needs a reader, and not finding one is not a pass.** If neither
poppler's `pdftotext` nor `pypdf` is available this raises, and the CLI turns that
into exit 2 -- could-not-complete. A missing reader must never leave by the same
door as a clean check.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

__all__ = ["VerificationError", "pdf_text", "numbers_in", "verify_projection"]

# Integers and decimals. Deliberately not matching a leading sign: a hyphen in
# this document is a dash, and treating "-- 3" as negative three would invent a
# number neither side wrote.
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class VerificationError(RuntimeError):
    """The check could not be run. Distinct from the check failing."""


def pdf_text(path: str | Path) -> str:
    """The PDF's text, via whichever reader is installed.

    `pdftotext` first: it is poppler, it is not ours, and an independent reader is
    the only kind worth checking your own output with.
    """
    path = Path(path)
    if not path.exists():
        raise VerificationError(f"no PDF at {path}")

    binary = shutil.which("pdftotext")
    if binary:
        result = subprocess.run([binary, "-layout", str(path), "-"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise VerificationError(
                f"pdftotext could not read {path}: "
                f"{result.stderr.strip() or 'no message'}")
        return result.stdout

    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise VerificationError(
            # The DISTRIBUTION name, which is not this command's. Naming the
            # command here would hand the reader something that fails: PyPI
            # refuses `cert-generator` as too similar to an existing project.
            "no PDF reader available: install poppler-utils for pdftotext, or "
            "pip install 'odm-cert-generator[verify]' for pypdf. A certificate "
            "that could not be read has not been checked") from error

    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def numbers_in(text: str) -> list[str]:
    return _NUMBER.findall(text)


def _scalars(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _scalars(value)
    elif isinstance(node, list):
        for item in node:
            yield from _scalars(item)
    elif node is not None and not isinstance(node, bool):
        yield str(node)


def verify_projection(certificate: dict | str | Path,
                      pdf: str | Path) -> list[str]:
    """Numbers on the page that are absent from the JSON, or an empty list."""
    if isinstance(certificate, (str, Path)):
        certificate = json.loads(Path(certificate).read_text(encoding="utf-8"))

    allowed: set[str] = set()
    for scalar in _scalars(certificate):
        allowed.update(_NUMBER.findall(scalar))

    unbacked: list[str] = []
    for number in numbers_in(pdf_text(pdf)):
        if number not in allowed and number not in unbacked:
            unbacked.append(number)
    return unbacked
