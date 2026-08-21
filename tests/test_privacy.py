"""Two trust domains, and the traffic between them goes one way.

The audit tool keeps serials out of its outputs. This package holds serials -- and
therefore has to be the one that keeps the tool's operational detail out of a
document that leaves the building. `coverage --json` is written for a CI log: it
names the BMC by URL and the configuration by filesystem path. Neither belongs on
a customer's certificate.
"""

from __future__ import annotations

import json

from cert_generator.certificate import build_certificate
from cert_generator.coverage import DROPPED_FIELDS, summarise


class TestTheCoverageArtifactIsScrubbed:
    def test_the_input_really_does_carry_what_we_are_dropping(self, coverage):
        """Otherwise every test below passes because there was nothing to remove.

        This is the fixture asserting its own premise: if a future release of the
        audit tool stops emitting these, the scrubbing tests become vacuous and
        this is the one that goes red to say so.
        """
        assert coverage["target"].startswith("http")
        assert coverage["findings"][0]["declared_in"].startswith("/")

    def test_the_bmc_url_does_not_reach_the_summary(self, coverage):
        rendered = json.dumps(summarise(coverage))
        assert coverage["target"] not in rendered
        assert "http" not in rendered

    def test_no_filesystem_path_reaches_the_summary(self, coverage):
        rendered = json.dumps(summarise(coverage))
        assert coverage["findings"][0]["declared_in"] not in rendered

    def test_none_of_the_dropped_field_names_survive(self, coverage):
        rendered = json.dumps(summarise(coverage))
        for field in DROPPED_FIELDS:
            assert f'"{field}"' not in rendered

    def test_the_certificate_carries_none_of_it_either(self, certificate,
                                                       coverage):
        """The seam that matters: scrubbed at the module and still scrubbed after
        the certificate is assembled around it."""
        rendered = json.dumps(certificate)
        assert coverage["target"] not in rendered
        assert coverage["findings"][0]["declared_in"] not in rendered

    def test_the_finding_itself_survives_the_scrub(self, coverage):
        """Scrubbing must not become dropping. The absent sensor is the point."""
        summary = summarise(coverage)
        assert summary["findings"][0]["sensor"] == "Fan 3 Tach"
        assert summary["findings"][0]["regression"] is True
        assert "not reported at all" in summary["findings"][0]["statement"]

    def test_an_unknown_finding_kind_is_carried_not_dropped(self, coverage):
        """A kind this build has not seen is still a fact about the unit."""
        coverage["findings"].append({"kind": "some_future_kind",
                                     "sensor": "P5V", "detail": "a new shape",
                                     "regression": False})
        summary = summarise(coverage)
        assert summary["findings"][-1]["sensor"] == "P5V"
        assert summary["findings"][-1]["statement"] == "a new shape"


class TestIdentityNeverTravelsBackwards:
    def test_the_attestation_is_not_mutated_by_rendering(self, attestation,
                                                          identity, coverage):
        before = json.dumps(attestation, sort_keys=True)
        build_certificate(attestation, identity, coverage=coverage)
        assert json.dumps(attestation, sort_keys=True) == before, (
            "building a certificate changed the attestation; audit evidence must "
            "be identical before and after a serial number is attached to it")

    def test_the_coverage_artifact_is_not_mutated_either(self, attestation,
                                                          identity, coverage):
        before = json.dumps(coverage, sort_keys=True)
        build_certificate(attestation, identity, coverage=coverage)
        assert json.dumps(coverage, sort_keys=True) == before

    def test_no_identity_field_appears_inside_the_judgment(self, certificate,
                                                            identity_block):
        """Identity belongs in one block. Smeared through the evidence it would
        be impossible to strip a certificate back to the artifact it came from."""
        judgment = json.dumps(certificate["judgment"])
        left_out = json.dumps(certificate["not_part_of_this_judgment"])
        for value in identity_block.values():
            assert value not in judgment
            assert value not in left_out
