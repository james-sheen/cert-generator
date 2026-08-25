"""The PDF is a projection of the JSON: no number on the page is absent from it.

**The oracle is poppler, not us.** `pdftotext` was written by people with no stake
in this repository, which is the only kind of reader worth checking your own
output with. A test that read the PDF back with the same code that wrote it would
prove the two halves agree and nothing about whether either is right.

**Not finding the oracle is not a pass.** Where poppler is absent these tests skip
with the reason said out loud -- but CI sets `CERT_GENERATOR_REQUIRE_PDF_ORACLE=1`
and then a missing reader is a failure, because a check that silently stopped
running in the one place it matters is worse than no check at all.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

from cert_generator.render import RenderError, render_pdf
from cert_generator.verify import available_reader, verify_projection

NUMBER = re.compile(r"\d+(?:\.\d+)?")
REQUIRED = os.environ.get("CERT_GENERATOR_REQUIRE_PDF_ORACLE") == "1"


def poppler_text(path) -> str:
    binary = shutil.which("pdftotext")
    if binary is None:
        message = ("poppler's pdftotext is not installed, so the PDF was written "
                   "and never read back; nothing here was checked")
        if REQUIRED:
            pytest.fail(message + " -- and this run requires the oracle")
        pytest.skip(message)
    result = subprocess.run([binary, "-layout", str(path), "-"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def rendered(certificate, tmp_path):
    path = tmp_path / "certificate.pdf"
    render_pdf(certificate, path)
    return path


class TestThePageWasActuallyRead:
    """Guards every test below. An empty extraction satisfies 'no extra numbers'."""

    def test_the_oracle_returns_the_document(self, rendered):
        text = poppler_text(rendered)
        assert "Quality Control Certificate" in text
        assert len(NUMBER.findall(text)) >= 8, (
            "almost no numbers came back from the reader; the projection tests "
            "would pass on an empty page")


NEEDS_READER = pytest.mark.skipif(
    available_reader() is None,
    reason="no PDF reader is installed (poppler's pdftotext or pypdf), so the "
           "rendered page was never opened and the projection was not checked "
           "-- which is a different answer from the projection being wrong")


@NEEDS_READER
class TestNoNumberOnThePageIsAbsentFromTheRecord:
    def test_every_number_is_backed(self, certificate, rendered):
        unbacked = verify_projection(certificate, rendered)
        assert unbacked == [], (
            "these numbers are printed on the certificate and appear nowhere in "
            f"the record behind it: {unbacked}")

    def test_the_check_can_fail(self, certificate, rendered):
        """The falsification. Take a measurement out of the record and the page
        is now claiming something the record does not support."""
        tampered = {**certificate}
        tampered["judgment"] = {**certificate["judgment"], "measurements": []}
        unbacked = verify_projection(tampered, rendered)
        assert "92.4" in unbacked, (
            "removing the measurement from the record did not make the printed "
            "reading unbacked; the check cannot distinguish the two")


class TestTheDocumentSaysWhatTheRecordSays:
    def test_the_unit_is_named(self, rendered, identity_block):
        text = poppler_text(rendered)
        for field in ("serial", "work_order", "station", "signer"):
            assert identity_block[field] in text

    def test_the_finding_and_its_measurement_are_printed(self, rendered):
        text = poppler_text(rendered)
        assert "Inlet Temp" in text
        assert "92.4" in text, "the reading behind the finding is the point"
        assert "80.0" in text, "so is the bound it exceeded"

    def test_the_declines_are_printed_with_their_count(self, rendered):
        text = poppler_text(rendered)
        assert "Declined" in text
        assert "insufficient_samples" in text

    def test_what_was_left_out_is_printed(self, rendered):
        text = poppler_text(rendered)
        assert "Not part of this judgment" in text
        assert "engine-side evidence only" in text, (
            "the engine's own boundary statement must reach the page; it is the "
            "engine declining to be called an attestation service")

    def test_the_declaration_diff_denominator_is_printed(self, rendered):
        text = poppler_text(rendered)
        assert "Declared sensors" in text
        assert "Fan 3 Tach" in text, (
            "the absent sensor is the most important QC fact about this unit")

    def test_the_missing_diff_is_printed_when_there_is_no_coverage(
            self, attestation, identity, tmp_path):
        from cert_generator.certificate import build_certificate
        certificate = build_certificate(attestation, identity)
        path = render_pdf(certificate, tmp_path / "no-coverage.pdf")
        text = poppler_text(path)
        assert "cannot state how many" in text


class TestOneUnreadableFieldStopsTheRender:
    def test_characters_outside_latin1_are_refused(self, certificate, tmp_path):
        certificate["identity"]["serial"] = "SN-高雄-01"
        with pytest.raises(RenderError) as raised:
            render_pdf(certificate, tmp_path / "unrenderable.pdf")
        assert "Latin-1" in str(raised.value)

    def test_nothing_is_written_when_refused(self, certificate, tmp_path):
        target = tmp_path / "unrenderable.pdf"
        certificate["identity"]["signer"] = "張三"
        with pytest.raises(RenderError):
            render_pdf(certificate, target)
        assert not target.exists(), (
            "a partial PDF was left on disk; a half-written certificate is the "
            "one document nobody should find lying around")
