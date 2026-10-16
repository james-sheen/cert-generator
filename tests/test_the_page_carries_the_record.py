"""A record too long for one page is printed whole, and a page that drops it is refused.

The fixture is the bletchley board as `bmc-sensor-audit` 0.3.18 judged it from its own recording: 26
findings, 28 declines, 86 declared and 58 absent (`tests/fixtures/bletchley/README.md`). On 0.2.5 that
certificate was one page with page breaks off, and the library drew everything after the second measurement
below the page's edge -- *Not part of this judgment*, every absent sensor, the capture handle. On paper it
listed 26 findings and never said *absent*, and `verify` passed it, because it asked only whether the page
had added to the record and never whether the record had reached the page.

**Both halves are pinned, and the second is the one that matters.** A layout can regress in ways nobody
predicts; a check that refuses the page whatever the layout did is what keeps the document honest after the
next change to it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cert_generator.certificate import Capture, build_certificate
from cert_generator.identity import load_identity
from cert_generator.render import footer_line, render_pdf
from cert_generator.verify import available_reader, pdf_pages, verify_document

HERE = Path(__file__).resolve().parent / "fixtures" / "bletchley"
HANDLE = "sha256:9a59dad65f8ed74a9b0549ae469404db065e19907d98adc55bd5259d81140271"
REQUIRED = os.environ.get("CERT_GENERATOR_REQUIRE_PDF_ORACLE") == "1"


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture(autouse=True)
def a_reader():
    if available_reader() is None:
        message = ("no PDF reader is installed, so no page was read and nothing here was checked -- a "
                   "different answer from the page being right")
        if REQUIRED:
            pytest.fail(message + "; this run requires one")
        pytest.skip(message)


@pytest.fixture
def bletchley(identity_block) -> dict:
    return build_certificate(json.loads((HERE / "attestation.json").read_text(encoding="utf-8")),
                             load_identity(identity_block),
                             coverage=json.loads((HERE / "coverage.json").read_text(encoding="utf-8")),
                             capture=Capture(digest=HANDLE, verified=False))


@pytest.fixture
def absent(bletchley) -> list[str]:
    diff = bletchley["not_part_of_this_judgment"]["declaration_diff"]
    return sorted({str(f.get("point", f.get("sensor"))) for f in diff["findings"]
                   if f.get("kind") == "declared_absent"})


@pytest.fixture
def one_page_as_it_was(monkeypatch):
    """0.2.5's renderer: the same layout with page breaks off."""
    import fpdf
    original = fpdf.FPDF.set_auto_page_break
    monkeypatch.setattr(fpdf.FPDF, "set_auto_page_break",
                        lambda self, auto, margin=0: original(self, False, margin))


class TestTheFixtureIsTheBoardItSaysItIs:
    """Guards the rest: a record that fits one page would make every test below vacuous."""

    def test_the_counts(self, bletchley, absent):
        judgment = bletchley["judgment"]
        diff = bletchley["not_part_of_this_judgment"]["declaration_diff"]
        assert (judgment["finding_count"], judgment["declined_count"]) == (26, 28)
        assert (diff["declared"], diff["declared_absent"]) == (86, 58)
        assert len(absent) > 40, "the absent names are what the page lost"


class TestThePagesCarryTheRecord:
    def test_it_runs_to_more_than_one_page(self, bletchley, tmp_path):
        assert len(pdf_pages(render_pdf(bletchley, tmp_path / "c.pdf"))) > 1

    def test_page_one_states_declared_against_absent(self, bletchley, tmp_path):
        first = _flat(pdf_pages(render_pdf(bletchley, tmp_path / "c.pdf"))[0])
        assert "86 declared" in first and "58 declared and absent" in first, (
            "page one must say how many declared sensors were absent; it is the line that cannot fall off")

    def test_every_page_says_which_certificate_and_page_it_is(self, bletchley, tmp_path):
        pages = pdf_pages(render_pdf(bletchley, tmp_path / "c.pdf"))
        serial = bletchley["identity"]["serial"]
        for number, page in enumerate(pages, start=1):
            assert _flat(footer_line(serial, number, len(pages))) in _flat(page)

    def test_what_was_not_judged_and_every_absent_sensor_are_printed(self, bletchley, absent, tmp_path):
        text = _flat("\n".join(pdf_pages(render_pdf(bletchley, tmp_path / "c.pdf"))))
        assert "Not part of this judgment" in text
        assert [name for name in absent if name not in text] == []
        assert HANDLE in text

    def test_verify_passes_the_whole_document(self, bletchley, tmp_path):
        found = verify_document(bletchley, render_pdf(bletchley, tmp_path / "c.pdf"))
        assert (found["unbacked"], found["missing"], found["page_lines"]) == ([], [], [])


class TestAPageThatDropsTheRecordIsRefused:
    def test_the_one_page_render_loses_the_section(self, bletchley, tmp_path, one_page_as_it_was):
        pages = pdf_pages(render_pdf(bletchley, tmp_path / "c.pdf"))
        assert len(pages) == 1 and "Not part of this judgment" not in _flat(pages[0]), (
            "the replay of 0.2.5 no longer overflows; it reproduces nothing")

    def test_verify_names_what_the_page_dropped(self, bletchley, absent, tmp_path, one_page_as_it_was):
        found = verify_document(bletchley, render_pdf(bletchley, tmp_path / "c.pdf"))
        assert "Not part of this judgment" in found["missing"]
        assert HANDLE in found["missing"]
        assert set(absent) <= set(found["missing"]), "every absent sensor the page lost is named"
        assert found["unbacked"] == [], (
            "the numbers it did print are all in the record -- which is exactly why the old check passed it")

    def test_pypdf_is_held_to_the_page_too(self, bletchley, tmp_path, one_page_as_it_was, monkeypatch):
        """pypdf reads the content stream, where the lost section still is. Held to the page's box, it
        answers about the page a person sees -- and without that, this check would pass the old page."""
        pypdf = pytest.importorskip("pypdf")
        pdf = render_pdf(bletchley, tmp_path / "c.pdf")
        stream = pypdf.PdfReader(str(pdf)).pages[0].extract_text()
        assert "Not part of this judgment" in stream, "the stream must hold it, or this test proves nothing"
        import cert_generator.verify as verify
        monkeypatch.setattr(verify, "available_reader", lambda: "pypdf")
        assert "Not part of this judgment" in verify_document(bletchley, pdf)["missing"]
