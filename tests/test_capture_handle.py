"""Which capture a certificate was judged from, and how firmly it knows.

The audit tool refuses to hold unit identity; this package holds nothing else. The
binding between the two has always had to happen on CONTENT, and until the tool
shipped a content handle at 0.1.1 there was nothing to bind to — a certificate
named a target label and a format, and nothing that could be matched against a
file somebody kept.

**`verified` is the whole reason `Capture` is a pair rather than a string.** A
handle computed here from a file this program read is a measurement. A handle
typed in from a run log is a transcription. Both are legitimate — a clean
orchestrator run deletes its walks long before a certificate is rendered, so often
the handle is all that survives — and they support different claims, so the record
carries which one it is instead of flattening them into a number on a page.

**The projection check needed a category correction to accept it.** A digest is an
identifier that happens to contain digits. Counted as numbers, its hex would
contribute dozens of short digit runs to the set the page is allowed to print, so
a stray `83` anywhere on the certificate would come out "backed" by a fragment of
a hash. That is a silent weakening of the one check standing between the document
and an unsupported number, so handles are taken out of the number count on both
sides and matched whole — which verifies them more strictly than any number.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cert_generator.certificate import (Capture, CertificateError,
                                        build_certificate, capture_from_digest,
                                        capture_from_walk)
from cert_generator.verify import handles_in, numbers_in, verify_projection

HANDLE = "sha256:" + "3" * 64
WALK = {"format": "bmc-sensor-audit/walk/1", "fields_observed": True,
        "sensors": [{"name": "Inlet", "reading": 21.0,
                     "thresholds": {"upper/critical": 80.0}}]}


@pytest.fixture
def walk_file(tmp_path) -> Path:
    path = tmp_path / "walk.json"
    path.write_text(json.dumps(WALK, indent=2))
    return path


class TestTheRecordSaysWhichCaptureAndHowFirmly:
    def test_without_one_both_keys_are_present_and_null(self, attestation, identity):
        """Present rather than absent. A certificate that omitted the key would
        read like one whose capture is beyond doubt, which is the opposite of what
        not knowing means."""
        source = build_certificate(attestation, identity)["source"]
        assert source["walk_digest"] is None
        assert source["walk_digest_verified"] is None

    def test_a_walk_this_program_read_is_recorded_as_verified(self, attestation,
                                                              identity, walk_file):
        source = build_certificate(attestation, identity,
                                   capture=capture_from_walk(walk_file))["source"]
        assert source["walk_digest_verified"] is True

    def test_a_supplied_handle_is_recorded_as_unverified(self, attestation,
                                                         identity):
        """Nothing here checked it, and the record says so rather than presenting
        a transcription as a measurement."""
        source = build_certificate(attestation, identity,
                                   capture=capture_from_digest(HANDLE))["source"]
        assert source["walk_digest"] == HANDLE
        assert source["walk_digest_verified"] is False

    def test_the_computed_handle_is_the_one_sha256sum_gives(self, walk_file):
        """The property that makes it useful to a recipient: no tooling needed,
        and nothing to trust. It is the audit tool's own function, so there is one
        definition of this number rather than two that can disagree."""
        expected = hashlib.sha256(walk_file.read_bytes()).hexdigest()
        assert capture_from_walk(walk_file).digest == f"sha256:{expected}"

    def test_a_rewritten_walk_gets_a_different_handle(self, walk_file, tmp_path):
        """Non-vacuity: the handle is of the FILE, so it moves when the file does."""
        other = tmp_path / "other.json"
        other.write_text(json.dumps({**WALK, "sensors": [
            {**WALK["sensors"][0], "reading": 99.0}]}, indent=2))
        assert capture_from_walk(walk_file).digest != capture_from_walk(other).digest


class TestAHandleThatCannotBeMatchedIsRefused:
    @pytest.mark.parametrize("bad", ["", "sha256:", "deadbeef", "sha256:XYZ",
                                     "sha256:" + "3" * 63, "md5:" + "3" * 64])
    def test_a_malformed_handle_stops_the_render(self, attestation, identity, bad):
        """A certificate printing an unusable handle would look like proof and
        match nothing, which is worse than printing none."""
        with pytest.raises(CertificateError, match="hex characters"):
            build_certificate(attestation, identity,
                              capture=Capture(digest=bad, verified=False))

    def test_a_walk_the_tool_refuses_is_not_cited(self, attestation, identity,
                                                  tmp_path):
        """Validated with the audit tool's own validator rather than a copy of its
        rules. A certificate citing a file the tool would not read is citing
        nothing."""
        path = tmp_path / "broken.json"
        path.write_text(json.dumps({"format": "bmc-sensor-audit/walk/1",
                                    "sensors": [{"reading": 1.0}]}))
        with pytest.raises(CertificateError, match="refused by the audit tool"):
            capture_from_walk(path)

    def test_a_file_that_is_not_json_is_refused(self, tmp_path):
        path = tmp_path / "notjson.json"
        path.write_text("{")
        with pytest.raises(CertificateError, match="not parseable"):
            capture_from_walk(path)

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(CertificateError, match="cannot read"):
            capture_from_walk(tmp_path / "nothing.json")


class TestAHandleIsAnIdentifierAndNotABagOfDigits:
    def test_its_digits_do_not_count_as_numbers(self):
        """The dilution this correction prevents. Left in the number count, a
        handle contributes dozens of short digit runs to what the page may print."""
        assert numbers_in(f"reading 21.0 and {HANDLE}") == ["21.0"]

    def test_it_is_matched_whole(self):
        assert handles_in(f"Capture {HANDLE} end") == [HANDLE]

    def test_a_near_miss_is_not_a_handle(self):
        """Sixty-three characters, or the wrong algorithm, is not this format."""
        assert handles_in("sha256:" + "3" * 63) == []
        assert handles_in("md5:" + "3" * 64) == []


@pytest.mark.skipif(shutil.which("pdftotext") is None,
                    reason="the projection is checked with poppler, which is not "
                           "ours; a reader we wrote could agree with our own bug")
class TestThePageAndTheRecordAgreeAboutTheCapture:
    @staticmethod
    def _render(certificate, path):
        from cert_generator.render import render_pdf

        render_pdf(certificate, path)
        return path

    @staticmethod
    def _text(path) -> str:
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def test_the_handle_is_printed_where_a_recipient_will_look(
            self, attestation, identity, walk_file, tmp_path):
        """A certificate that knows which capture it came from and keeps that to
        itself has left the recipient the one job they cannot otherwise do."""
        certificate = build_certificate(attestation, identity,
                                        capture=capture_from_walk(walk_file))
        text = self._text(self._render(certificate, tmp_path / "c.pdf"))
        assert certificate["source"]["walk_digest"] in text.replace("\n", "")

    def test_the_page_says_whether_the_handle_was_verified(
            self, attestation, identity, walk_file, tmp_path):
        certificate = build_certificate(attestation, identity,
                                        capture=capture_from_walk(walk_file))
        assert "computed here from the walk" in self._text(
            self._render(certificate, tmp_path / "c.pdf"))

        supplied = build_certificate(attestation, identity,
                                     capture=capture_from_digest(HANDLE))
        assert "not verified by this program" in self._text(
            self._render(supplied, tmp_path / "s.pdf"))

    def test_the_projection_check_backs_the_printed_handle(
            self, attestation, identity, walk_file, tmp_path):
        certificate = build_certificate(attestation, identity,
                                        capture=capture_from_walk(walk_file))
        pdf = self._render(certificate, tmp_path / "c.pdf")
        assert verify_projection(certificate, pdf) == []

    def test_a_handle_the_record_does_not_carry_is_caught(
            self, attestation, identity, walk_file, tmp_path):
        """**The falsification, and the reason handles are checked at all.** A
        page printing a capture handle the record does not support is making the
        same kind of claim as a page printing a reading nothing measured -- and a
        worse one, because a hash looks like proof."""
        certificate = build_certificate(attestation, identity,
                                        capture=capture_from_walk(walk_file))
        pdf = self._render(certificate, tmp_path / "c.pdf")
        tampered = {**certificate,
                    "source": {**certificate["source"], "walk_digest": HANDLE}}
        unbacked = verify_projection(tampered, pdf)
        assert certificate["source"]["walk_digest"] in unbacked

    def test_a_certificate_with_no_capture_prints_no_handle(
            self, attestation, identity, tmp_path):
        """Non-vacuity for the row: it appears because there is something to say,
        not on every certificate."""
        certificate = build_certificate(attestation, identity)
        text = self._text(self._render(certificate, tmp_path / "c.pdf"))
        assert "Capture" not in text
        assert handles_in(text) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
