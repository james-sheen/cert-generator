"""The PDF, which is a projection of the JSON and nothing more.

**One rule, and it is testable:** no number appears in the PDF that is absent from
the certificate JSON. That is what makes the pair trustworthy -- the JSON is the
record, the PDF is how it looks, and a reader who has both can check one against
the other without trusting this code. `tests/test_projection.py` checks it with
poppler's `pdftotext`, a reader nobody in this project wrote.

The rule is kept by construction rather than by care: every number reaches the
page through `_number`, which formats it from the JSON value's own string form. A
threshold stored as `80.0` prints as `80.0` and not as `80`, because `80` is a
different string and a checker comparing text has no way to know it was the same
measurement.

## A limit, stated rather than worked around

The built-in fonts cover Latin-1. An identity field containing characters outside
it -- a customer name in Chinese, say -- is **refused, not transliterated**: a
serial number silently rewritten to something a machine cannot be found by is a
worse outcome than a failed render. Shipping a Unicode font would lift this; it
has not been done, so it is written down.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["RenderError", "render_pdf"]

_MARGIN = 15
_LINE = 5.0


class RenderError(ValueError):
    """The certificate could not be drawn."""


def _number(value: Any) -> str:
    """A scalar as it appears in the JSON, so text comparison is meaningful."""
    if value is None:
        return "not recorded"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _renderable(certificate: dict) -> None:
    """Refuse characters the built-in fonts cannot draw. See the module docstring."""
    offenders: dict[str, str] = {}
    for name, value in certificate["identity"].items():
        bad = sorted({c for c in value if ord(c) > 0xFF})
        if bad:
            offenders[name] = "".join(bad)
    if offenders:
        detail = "; ".join(f"{k} contains {v!r}" for k, v in offenders.items())
        raise RenderError(
            "the identity block carries characters outside Latin-1, which the "
            f"built-in fonts cannot draw: {detail}. Nothing was written -- a "
            "serial number rendered wrong is worse than one not rendered at all")


def render_pdf(certificate: dict, path: str | Path) -> Path:
    try:
        from fpdf import FPDF
    except ImportError as error:                             # pragma: no cover
        raise RenderError("the PDF projection needs fpdf2: pip install fpdf2"
                          ) from error

    _renderable(certificate)

    pdf = FPDF(format="A4", unit="mm")
    # Deliberately off. Auto page breaks would silently push content onto a second
    # page, and the projection test reads page one; a certificate that overflows
    # should be visible as overflow, not quietly paginated.
    pdf.set_auto_page_break(auto=False, margin=_MARGIN)
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.add_page()
    width = pdf.w - 2 * _MARGIN

    def heading(text: str, size: int = 11, gap: float = 1.5) -> None:
        pdf.ln(gap)
        pdf.set_font("Helvetica", "B", size)
        pdf.cell(width, _LINE + 1, text, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

    def row(label: str, value: str) -> None:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(45, _LINE, label, new_x="RIGHT", new_y="TOP")
        pdf.multi_cell(width - 45, _LINE, value, new_x="LMARGIN", new_y="NEXT")

    def bullet(text: str) -> None:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(5, _LINE, "-", new_x="RIGHT", new_y="TOP")
        pdf.multi_cell(width - 5, _LINE, text, new_x="LMARGIN", new_y="NEXT")

    judgment = certificate["judgment"]
    left_out = certificate["not_part_of_this_judgment"]

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(width, 9, "Quality Control Certificate", new_x="LMARGIN",
             new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(width, _LINE,
             "Sensor declaration and liveness audit. Read the scope statement "
             "below before relying on this document.",
             new_x="LMARGIN", new_y="NEXT")

    heading("Unit")
    for key, value in certificate["identity"].items():
        row(key.replace("_", " ").title(), value)

    heading("Judgment")
    row("Verdict", judgment["verdict"])
    row("Scope", judgment["statement"])

    if judgment["findings"]:
        heading("Findings", size=10)
        for finding in judgment["findings"]:
            bullet(f"{finding.get('sensor', '?')} "
                   f"[{finding.get('axiom', '?')}, "
                   f"{finding.get('severity', 'unrated')}] "
                   f"{finding.get('statement', '')}")

    if judgment["measurements"]:
        heading("Measurements behind those findings", size=10)
        for entry in judgment["measurements"]:
            measurement = entry.get("measurement") or {}
            parts = [f"{key} {_number(value)}"
                     for key, value in measurement.items()]
            bullet(f"{entry.get('sensor', '?')}: " + ", ".join(parts))

    if judgment["declined"]:
        heading(f"Declined -- asked, not answered, and why "
                f"({_number(judgment['declined_count'])})", size=10)
        for decline in judgment["declined"]:
            bullet(f"{decline.get('sensor', '?')} [{decline.get('axiom', '?')}] "
                   f"{decline.get('reason', 'no reason given')}"
                   + (f" -- {decline['detail']}" if decline.get("detail") else ""))

    heading("Not part of this judgment")
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(width, _LINE,
                   "A certificate that shows only what was checked reads as a "
                   "clean bill of health for every question nobody asked. These "
                   "are the questions this run did not answer.",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    diff = left_out["declaration_diff"]
    if diff.get("present"):
        row("Declared sensors", _number(diff.get("declared")))
        row("Matched on the machine", _number(diff.get("matched")))
        row("Declared, absent", _number(diff.get("declared_absent")))
        row("Walk complete", _number(diff.get("walk_complete")))
        for finding in diff.get("findings", []):
            bullet(f"{finding.get('sensor', '?')}: {finding.get('statement', '')}")
    else:
        bullet(str(diff.get("reason", "")))

    pdf.ln(1)
    bullet("Engine boundary: " + str(left_out["engine_boundary"]
                                     or "none stated"))
    if left_out["unattested"]:
        for item in left_out["unattested"]:
            bullet("Not attested: " + str(item))
    else:
        bullet("Not attested: none")
    if left_out["unread_feeds"]:
        for item in left_out["unread_feeds"]:
            bullet("Read but not used: " + str(item))
    else:
        bullet("Read but not used: none")

    generator = certificate["generator"]
    source = certificate["source"]
    heading("Provenance")
    row("Rendered", generator["rendered_at"])
    row("Generator", f"{generator['name']} {generator['version']}")
    row("Attestation format", str(source["attestation_format"]))
    row("Engine schema", _number(source["engine_schema_version"]))
    row("Target", str(source["target_label"]))

    path = Path(path)
    pdf.output(str(path))
    return path
