"""Exit codes, which are the family's contract and not this tool's invention.

`0` clean, `1` something is recorded against the unit, `2` this run could not
complete. The rule that matters is the third one never reading as the first.
"""

from __future__ import annotations

import json

import pytest

from cert_generator.verify import available_reader

from cert_generator.cli import EXIT_CLEAN, EXIT_INCOMPLETE, EXIT_RECORDED, main


@pytest.fixture
def paths(tmp_path, attestation, coverage, identity_block):
    files = {}
    for name, payload in (("attestation", attestation), ("coverage", coverage),
                          ("identity", identity_block)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload))
        files[name] = str(path)
    files["out_json"] = str(tmp_path / "certificate.json")
    files["out_pdf"] = str(tmp_path / "certificate.pdf")
    return files


def render_argv(paths, *extra):
    return ["render", "--attestation", paths["attestation"],
            "--identity", paths["identity"],
            "--out-json", paths["out_json"], *extra]


class TestRender:
    def test_a_unit_with_findings_exits_one(self, paths):
        assert main(render_argv(paths)) == EXIT_RECORDED

    def test_a_clean_unit_exits_zero(self, paths, tmp_path, attestation):
        attestation["findings"] = []
        attestation["evidence"] = []
        clean = tmp_path / "clean.json"
        clean.write_text(json.dumps(attestation))
        paths["attestation"] = str(clean)
        assert main(render_argv(paths)) == EXIT_CLEAN

    def test_a_clean_engine_run_with_an_absent_sensor_still_exits_one(
            self, paths, tmp_path, attestation):
        """The engine found nothing because the sensor never reached it. The
        declaration diff is the only artifact that knows, and it is a verdict."""
        attestation["findings"] = []
        attestation["evidence"] = []
        clean = tmp_path / "clean.json"
        clean.write_text(json.dumps(attestation))
        paths["attestation"] = str(clean)
        assert main(render_argv(paths, "--coverage", paths["coverage"])) \
            == EXIT_RECORDED

    def test_the_certificate_is_written_even_when_the_verdict_is_one(self, paths):
        main(render_argv(paths))
        record = json.loads(open(paths["out_json"]).read())
        assert record["judgment"]["verdict"] == "findings recorded"

    def test_the_pdf_is_written_when_asked_for(self, paths):
        main(render_argv(paths, "--out-pdf", paths["out_pdf"]))
        assert open(paths["out_pdf"], "rb").read(5) == b"%PDF-"


class TestCouldNotComplete:
    def test_a_missing_attestation_exits_two(self, paths):
        paths["attestation"] = "/nonexistent/attestation.json"
        assert main(render_argv(paths)) == EXIT_INCOMPLETE

    def test_a_shapeless_attestation_exits_two(self, paths, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text(json.dumps({"format": "wrong"}))
        paths["attestation"] = str(broken)
        assert main(render_argv(paths)) == EXIT_INCOMPLETE

    def test_a_bad_identity_exits_two(self, paths, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"serial": "SN-1"}))
        paths["identity"] = str(bad)
        assert main(render_argv(paths)) == EXIT_INCOMPLETE

    def test_asking_for_no_output_at_all_exits_two(self, paths):
        argv = ["render", "--attestation", paths["attestation"],
                "--identity", paths["identity"]]
        assert main(argv) == EXIT_INCOMPLETE

    def test_could_not_complete_beats_a_finding(self, paths, tmp_path):
        """The precedence that matters. This unit HAS a finding; the run also
        could not finish. Reporting 1 would tell a reader the rest was checked."""
        bad = tmp_path / "bad-coverage.json"
        bad.write_text(json.dumps({"counts": "not an object"}))
        assert main(render_argv(paths, "--coverage", str(bad))) == EXIT_INCOMPLETE


NEEDS_READER = pytest.mark.skipif(
    available_reader() is None,
    reason="no PDF reader is installed (poppler's pdftotext or pypdf), so the "
           "rendered page was never opened and the projection was not checked "
           "-- which is a different answer from the projection being wrong")


class TestVerify:
    # Per-test, NOT on the class. `test_an_unreadable_pdf_exits_two_not_zero`
    # below is the one whose subject IS the absence of a reader, so it has to
    # keep running when there is none -- a class-level guard skipped it and
    # turned the test for this exact situation off in this exact situation.
    @NEEDS_READER
    def test_a_faithful_pair_exits_zero(self, paths):
        main(render_argv(paths, "--out-pdf", paths["out_pdf"]))
        assert main(["verify", "--certificate", paths["out_json"],
                     "--pdf", paths["out_pdf"]]) == EXIT_CLEAN

    @NEEDS_READER
    def test_a_mismatched_pair_is_caught(self, paths, tmp_path):
        main(render_argv(paths, "--out-pdf", paths["out_pdf"]))
        record = json.loads(open(paths["out_json"]).read())
        record["judgment"]["measurements"] = []
        stripped = tmp_path / "stripped.json"
        stripped.write_text(json.dumps(record))
        assert main(["verify", "--certificate", str(stripped),
                     "--pdf", paths["out_pdf"]]) == EXIT_RECORDED

    def test_an_unreadable_pdf_exits_two_not_zero(self, tmp_path, paths):
        assert main(["verify", "--certificate", paths["attestation"],
                     "--pdf", str(tmp_path / "absent.pdf")]) == EXIT_INCOMPLETE


class TestCheck:
    def test_a_good_artifact_exits_zero(self, paths):
        assert main(["check", paths["attestation"]]) == EXIT_CLEAN

    def test_a_bad_artifact_exits_two(self, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text(json.dumps({"format": "wrong"}))
        assert main(["check", str(broken)]) == EXIT_INCOMPLETE
