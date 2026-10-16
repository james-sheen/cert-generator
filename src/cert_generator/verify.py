"""Check a rendered PDF against the certificate JSON it claims to project.

Shipped, not kept in a CI script, for the same reason `bmc-sensor-audit` ships its
attestation validator: the person who *receives* a certificate is the one who
needs to check it, and checking logic that lives inside a `run:` block cannot be
called by them, cannot be tested, and cannot be versioned alongside the thing it
checks.

**What it proves, in both directions.** Every number on the page also appears in
the JSON -- a figure typed into the layout, a stale render left beside an updated
record, a PDF paired with the wrong unit's JSON. And every statement the record
must show is on a page: the unit, the scope, every finding and decline, every
declared sensor that was absent, the engine's boundary and the capture handle.

**The second direction is the one 0.2.5 lacked, and it is why it exists.** A
certificate with 26 findings drew its *Not part of this judgment* section below
the page's edge, and this check passed it: every number a person could see was in
the record, and nothing asked whether the record had reached the page. Asking only
whether the page added to the record lets a page that drops what the record says
pass as faithful, and what a page drops is what it exists to carry.

**The page is what is drawn on it.** Each page is read on its own and only for
what lies inside its edges, by either reader: poppler keeps to the page already,
and `pypdf`, which reads the content stream, is held to the page's box here. Its
page line -- *page 2 of 3* -- is layout, not data: it is checked against the
document it is in, and taken out before numbers are counted.

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

__all__ = ["VerificationError", "pdf_pages", "pdf_text", "numbers_in", "handles_in",
           "verify_projection", "missing_from_page", "page_line_problems",
           "verify_document"]

# Integers and decimals. Deliberately not matching a leading sign: a hyphen in
# this document is a dash, and treating "-- 3" as negative three would invent a
# number neither side wrote.
_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# A content handle: `sha256:` and sixty-four hex characters. Removed from BOTH
# sides before numbers are counted, and compared whole instead.
#
# **Not an exemption -- a category correction, and it makes the check stronger.**
# A digest is an identifier that happens to contain digits. Left in, its hex would
# contribute dozens of short digit runs to the set of numbers the page is allowed
# to print, so a stray `83` anywhere on the certificate would be "backed" by a
# fragment of a hash. That silently weakens the one check standing between the
# document and a number nothing supports. Taken out and matched as a whole token,
# it is verified more strictly than any number is.
_HANDLE = re.compile(r"\bsha256:[0-9a-f]{64}\b")

# A page's own line, `render.footer_line`. Layout: checked against the document,
# never counted as a number the record must back.
_PAGE_LINE = re.compile(r"\bpage (\d+) of (\d+)\b")

# A one-word statement -- a sensor, a serial -- must stand alone, not inside a
# longer name: `P12V_AUX` is not on a page that prints only `P12V_AUX_HSC:vin`.
# A colon, dot or hyphen joins a name only when a word follows it -- `SLED1_HSC:vin`
# is one name; in `FAN0_TACH_IL: declared ...` the colon is punctuation.
_ALONE = r"(?<!\w)(?<!\w[:.\-]){}(?!\w)(?![:.\-]\w)"


class VerificationError(RuntimeError):
    """The check could not be run. Distinct from the check failing."""


def available_reader() -> str | None:
    """Which independent PDF reader is installed, or None.

    Exported so a caller -- including this package's own tests -- can ask
    whether the projection check CAN run before treating its answer as one.
    They used to answer that question by running the check and reading the
    failure, which reports *this certificate is wrong* for an environment that
    never opened it. `pdf_text` below selects through this same function, so the
    predicate cannot drift away from the behaviour it describes.
    """
    if shutil.which("pdftotext"):
        return "pdftotext"
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return None
    return "pypdf"


def pdf_pages(path: str | Path) -> list[str]:
    """Each page's text, only what is drawn inside that page, via whichever reader
    is installed.

    `pdftotext` first: it is poppler, it is not ours, and an independent reader is
    the only kind worth checking your own output with. It separates pages with a
    form feed and keeps to each page's edges.
    """
    path = Path(path)
    if not path.exists():
        raise VerificationError(f"no PDF at {path}")

    reader = available_reader()
    if reader == "pdftotext":
        binary = shutil.which("pdftotext")
        result = subprocess.run([binary, "-layout", str(path), "-"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise VerificationError(
                f"pdftotext could not read {path}: "
                f"{result.stderr.strip() or 'no message'}")
        pages = result.stdout.split("\f")
        return pages[:-1] if pages and not pages[-1].strip() else pages

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

    pages = []
    for page in PdfReader(str(path)).pages:
        low, high = float(page.mediabox.bottom), float(page.mediabox.top)
        drawn: list[str] = []

        def inside(text, cm, tm, font, size, drawn=drawn, low=low, high=high):
            # pypdf reports the content stream, edges or no edges; held to the box
            # here, so both readers answer about the same page.
            if text.strip() and low <= cm[3] * tm[5] + cm[5] <= high:
                drawn.append(text)

        page.extract_text(visitor_text=inside)
        pages.append("\n".join(drawn))
    return pages


def pdf_text(path: str | Path) -> str:
    """The whole document's text: every page, and only what is drawn on them."""
    return "\n".join(pdf_pages(path))


def numbers_in(text: str) -> list[str]:
    return _NUMBER.findall(_HANDLE.sub(" ", text))


def handles_in(text: str) -> list[str]:
    """Content handles, matched whole. See `_HANDLE`."""
    return _HANDLE.findall(text)


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


def _record(certificate: dict | str | Path) -> dict:
    if isinstance(certificate, (str, Path)):
        return json.loads(Path(certificate).read_text(encoding="utf-8"))
    return certificate


def _flat(text: str) -> str:
    return " ".join(text.split())


def verify_projection(certificate: dict | str | Path,
                      pdf: str | Path | list[str]) -> list[str]:
    """Numbers on the page that are absent from the JSON, or an empty list.

    `pdf` may be the pages already read, so one reading serves every check."""
    certificate = _record(certificate)

    allowed: set[str] = set()
    allowed_handles: set[str] = set()
    for scalar in _scalars(certificate):
        allowed.update(numbers_in(scalar))
        allowed_handles.update(handles_in(scalar))

    pages = pdf if isinstance(pdf, list) else pdf_pages(pdf)
    text = _PAGE_LINE.sub(" ", "\n".join(pages))
    unbacked: list[str] = []
    for number in numbers_in(text):
        if number not in allowed and number not in unbacked:
            unbacked.append(number)
    # Handles are checked the same way and in the same list, because a page
    # printing a capture handle the record does not carry is making the same kind
    # of claim as a page printing a reading the record does not carry -- and it is
    # a worse one, since a handle looks like proof.
    for handle in handles_in(text):
        if handle not in allowed_handles and handle not in unbacked:
            unbacked.append(handle)
    return unbacked


def _subject(row: dict) -> str:
    return str(row.get("point", row.get("sensor", "?")))


def required_on_page(certificate: dict | str | Path) -> list[str]:
    """What the record says that the page must also say, in the record's words."""
    certificate = _record(certificate)
    judgment = certificate["judgment"]
    left_out = certificate["not_part_of_this_judgment"]
    diff = left_out["declaration_diff"]
    source = certificate["source"]

    need = [str(v) for v in certificate["identity"].values()]
    need += [judgment["statement"], "Not part of this judgment"]
    need += [_subject(f) for f in judgment.get("findings", [])]
    need += [_subject(d) for d in judgment.get("declined", [])]
    if diff.get("present"):
        need += [_subject(f) for f in diff.get("findings", [])]
    elif diff.get("reason"):
        need.append(str(diff["reason"]))
    if left_out.get("engine_boundary"):
        need.append(str(left_out["engine_boundary"]))
    if source.get("walk_digest"):
        need.append(str(source["walk_digest"]))
    return list(dict.fromkeys(need))


def missing_from_page(certificate: dict | str | Path,
                      pdf: str | Path | list[str]) -> list[str]:
    """Statements of the record that appear on no page, or an empty list."""
    pages = pdf if isinstance(pdf, list) else pdf_pages(pdf)
    text = _flat("\n".join(pages))
    missing = []
    for statement in required_on_page(certificate):
        wanted = _flat(statement)
        if " " in wanted:
            found = wanted in text
        else:
            found = re.search(_ALONE.format(re.escape(wanted)), text) is not None
        if not found:
            missing.append(statement)
    return missing


def page_line_problems(certificate: dict | str | Path,
                       pdf: str | Path | list[str]) -> list[str]:
    """Pages that do not say which certificate and which page of how many they are."""
    from .render import footer_line

    serial = _record(certificate)["identity"]["serial"]
    pages = pdf if isinstance(pdf, list) else pdf_pages(pdf)
    return [f"page {number} does not say {footer_line(serial, number, len(pages))!r}"
            for number, page in enumerate(pages, start=1)
            if _flat(footer_line(serial, number, len(pages))) not in _flat(page)]


def verify_document(certificate: dict | str | Path, pdf: str | Path) -> dict:
    """Every check, on one reading of the document."""
    certificate = _record(certificate)
    pages = pdf_pages(pdf)
    return {"pages": len(pages),
            "unbacked": verify_projection(certificate, pages),
            "missing": missing_from_page(certificate, pages),
            "page_lines": page_line_problems(certificate, pages)}
