"""The cert-gen -> tool seam, checked against the tool that is actually installed.

Two repositories in this family have now watched a workflow sit red-or-silent for
want of a canary on exactly this kind of join. The pin here is a range
(`>=0.1.0,<0.2`), which means any 0.1.x release of the audit tool lands in a
consumer's environment without this repository changing -- and the seam is
precisely where that would show up first.

So: the checked-in example is re-validated by whichever validator is installed,
and where the engine is available a fresh artifact is produced end-to-end and
rendered. `CERT_GENERATOR_REQUIRE_SEAM=1` in CI turns the second one's skip into a
failure, because a canary nobody notices has stopped running is not a canary.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from cert_generator.certificate import (ATTESTATION_FORMAT, build_certificate)
from cert_generator.render import render_pdf

REQUIRED = os.environ.get("CERT_GENERATOR_REQUIRE_SEAM") == "1"

CONFIG = {
    "Name": "Reference Board",
    "Exposes": [
        {"Name": "Inlet Temp", "Type": "TMP75", "Thresholds": [
            {"Name": "upper critical", "Severity": 1,
             "Direction": "greater than", "Value": 80},
            {"Name": "upper warning", "Severity": 0,
             "Direction": "greater than", "Value": 70}]},
        {"Name": "Fan 3 Tach", "Type": "AspeedFan", "Thresholds": [
            {"Name": "lower critical", "Severity": 1,
             "Direction": "less than", "Value": 500}]},
    ],
}


class TestTheCheckedInExampleStillMatchesTheInstalledTool:
    def test_the_example_is_a_format_the_installed_core_reads(self, attestation):
        """The range admits a core that writes format 2 by default, so the
        example, written as format 1, is held to what the installed core READS
        rather than to the one id it writes. Taken from the core's own set, so
        the pin cannot outlive a change to it."""
        from presence_audit.attestation import ACCEPTED_ATTESTATION_FORMATS

        assert attestation["format"] in ACCEPTED_ATTESTATION_FORMATS, (
            "the installed core no longer reads the format examples/attestation.json "
            "was produced under; the pin range let a reader in that refuses it")
        assert ATTESTATION_FORMAT in ACCEPTED_ATTESTATION_FORMATS

    def test_the_installed_validator_still_accepts_it(self, attestation):
        from cert_generator.certificate import validate_attestation
        assert validate_attestation(attestation) == []

    def test_it_still_renders(self, attestation, identity, coverage, tmp_path):
        certificate = build_certificate(attestation, identity, coverage=coverage)
        render_pdf(certificate, tmp_path / "seam.pdf")


class TestAFreshlyProducedArtifactStillRenders:
    """End to end: run the real tool against a real mock BMC, render the result.

    This is the only test here that would notice the tool changing what it *emits*
    rather than what it *accepts* -- a new required key, a renamed count, a
    measurement that stopped carrying its bound.
    """

    def _skip_or_fail(self, reason: str):
        if REQUIRED:
            pytest.fail(reason + " -- and this run requires the seam canary")
        pytest.skip(reason)

    def test_end_to_end(self, identity, tmp_path):
        try:
            from bmc_sensor_audit.testing.mock_redfish import (MockBMC, MockSensor,
                                                               serve)
        except ImportError:
            self._skip_or_fail("the audit tool's mock BMC is not importable")
        try:
            import arbiter_engine  # noqa: F401
        except ImportError:
            self._skip_or_fail(
                "arbiter-engine is not installed, so `detect` cannot reach Stage 2 "
                "and no attestation can be produced; install "
                "'bmc-sensor-audit[detect]'")

        bmc = MockBMC(shape="sensors")
        bmc.sensors.append(MockSensor(name="Inlet Temp", reading=92.4,
                                      upper_critical=80.0, upper_warning=70.0))

        config = tmp_path / "board.json"
        config.write_text(json.dumps(CONFIG))
        artifact = tmp_path / "fresh-attestation.json"

        with serve(bmc) as url:
            result = subprocess.run(
                [sys.executable, "-m", "bmc_sensor_audit.cli", "detect",
                 "--config", str(config), "--target", url,
                 "--attest-out", str(artifact),
                 "--attest-target-label", "seam-canary"],
                capture_output=True, text=True)

        assert artifact.exists(), (
            "the audit tool produced no attestation; "
            f"exit {result.returncode}\n{result.stdout}\n{result.stderr}")

        fresh = json.loads(artifact.read_text())
        certificate = build_certificate(fresh, identity)
        render_pdf(certificate, tmp_path / "fresh.pdf")

        assert certificate["source"]["target_label"] == "seam-canary"
        assert certificate["judgment"]["finding_count"] >= 1, (
            "a sensor reading 92.4 against an upper critical of 80.0 produced no "
            "finding; either the engine changed its mind or this canary stopped "
            "driving it")

    def test_the_tool_is_the_one_we_pin(self):
        """The installed referee satisfies the range THIS package declares.

        Derived, not restated. This assertion used to hardcode `(0, 1)` and name
        the range `>=0.1.0,<0.2` in its own message -- while `pyproject.toml`
        declared `>=0.1.1`. Two copies of one range, already disagreeing, and the
        test could only ever check the copy it carried. Now there is one copy,
        it lives where pip enforces it, and this reads it.
        """
        from importlib.metadata import requires, version
        from packaging.requirements import Requirement

        declared = [Requirement(r.split(";")[0].strip())
                    for r in (requires("odm-cert-generator") or ())
                    if r.split(";")[0].strip().startswith("bmc-sensor-audit")]
        assert declared, (
            "this package declares no bmc-sensor-audit requirement, so nothing "
            "pins the referee it validates with")
        installed = version("bmc-sensor-audit")
        for req in declared:
            assert req.specifier.contains(installed, prereleases=True), (
                f"bmc-sensor-audit {installed} is installed and this package "
                f"declares {req}; the environment and the metadata disagree")


class TestAnArtifactWrittenBeforeTheSplitStillRenders:
    """The compatibility promise this tool inherits, and nobody else asserts.

    `bmc-sensor-audit` 0.3.0 moved the attestation to `presence-audit` and the
    format name moved with it. The old name is still READ, deliberately: the
    shape did not change when the package did, so an artifact already on disk
    is still exactly the same document and refusing it would be inventing an
    incompatibility to match a rename.

    That promise is made upstream and CONSUMED here -- this is the tool that
    holds somebody's older attestation and has to render it. A test upstream
    can show the validator accepts the name; only this one shows a certificate
    still comes out.
    """

    def test_the_old_format_name_is_still_accepted(self, attestation, identity):
        from cert_generator.certificate import build_certificate, validate_attestation

        old = dict(attestation)
        old["format"] = "bmc-sensor-audit/attestation/1"
        assert validate_attestation(old) == [], (
            "an attestation written before the split was refused")

        certificate = build_certificate(old, identity)
        assert certificate["source"]["attestation_format"] == \
            "bmc-sensor-audit/attestation/1", (
            "the certificate must record the format it was GIVEN, not the one "
            "this build happens to emit -- that field is provenance")

    def test_an_unknown_format_is_still_refused(self, attestation, identity):
        """Non-vacuity: the acceptance widened by exactly one name, not into a
        wildcard. A tool that rendered a certificate from a document it did not
        understand is the failure the format id exists to prevent."""
        from cert_generator.certificate import validate_attestation

        stranger = dict(attestation)
        stranger["format"] = "something-else/attestation/1"
        assert validate_attestation(stranger) != [], (
            "an unrecognised attestation format was accepted")
