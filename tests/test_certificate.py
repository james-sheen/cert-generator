"""The honest template, and the refusal that precedes it."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cert_generator import CERTIFICATE_FORMAT
from cert_generator.certificate import (FORBIDDEN_CLAIMS, CertificateError,
                                        build_certificate, has_coverage_regression)
from cert_generator.coverage import ABSENT_REASON


class TestAShapelessArtifactIsRefusedNotDecorated:
    def test_a_non_object_is_refused(self, identity):
        with pytest.raises(CertificateError) as raised:
            build_certificate(["not", "an", "object"], identity)
        assert "validator" in str(raised.value)

    def test_a_wrong_format_is_refused(self, attestation, identity):
        attestation["format"] = "some-other-tool/attestation/1"
        with pytest.raises(CertificateError):
            build_certificate(attestation, identity)

    def test_a_missing_left_out_list_is_refused(self, attestation, identity):
        """`unattested` absent reads as 'nothing was left out'. The tool's own
        validator rejects it, and this is the check that we let it."""
        del attestation["unattested"]
        with pytest.raises(CertificateError) as raised:
            build_certificate(attestation, identity)
        assert "unattested" in str(raised.value)

    def test_evidence_without_a_measurement_is_refused(self, attestation, identity):
        attestation["evidence"][0]["measurement"] = {}
        with pytest.raises(CertificateError):
            build_certificate(attestation, identity)

    def test_nothing_is_returned_when_refused(self, identity):
        """The refusal is total. There is no partial certificate."""
        with pytest.raises(CertificateError):
            build_certificate({"format": "wrong"}, identity)


class TestTheDenominatorIsOnTheDocument:
    def test_the_statement_carries_all_four_numbers(self, certificate):
        statement = certificate["judgment"]["statement"]
        assert "6 invariant(s) checked over 3 entit(ies)" in statement
        assert "1 finding(s) recorded" in statement
        assert "3 check(s) declined" in statement

    def test_declines_are_carried_with_their_reasons(self, certificate):
        declined = certificate["judgment"]["declined"]
        assert len(declined) == 3
        for entry in declined:
            assert entry["reason"], "a decline without a reason is not auditable"
            assert entry["axiom"]

    def test_an_unknown_count_is_not_written_as_zero(self, attestation, identity):
        attestation["checked"] = {}
        certificate = build_certificate(attestation, identity)
        statement = certificate["judgment"]["statement"]
        assert "does not record how many" in statement
        assert "0 invariant" not in statement


class TestTheLeftOutBlockIsMandatory:
    def test_it_is_present_even_when_every_list_is_empty(self, attestation,
                                                         identity):
        attestation["unattested"] = []
        attestation["unread_feeds"] = []
        certificate = build_certificate(attestation, identity)
        left_out = certificate["not_part_of_this_judgment"]
        assert set(left_out) == {"engine_boundary", "unattested", "unread_feeds",
                                 "declaration_diff"}

    def test_the_engines_own_boundary_is_carried_verbatim(self, attestation,
                                                          certificate):
        assert (certificate["not_part_of_this_judgment"]["engine_boundary"]
                == attestation["engine"]["boundary"])

    def test_without_a_coverage_artifact_the_gap_is_stated(self, attestation,
                                                           identity):
        certificate = build_certificate(attestation, identity)
        diff = certificate["not_part_of_this_judgment"]["declaration_diff"]
        assert diff == {"present": False, "reason": ABSENT_REASON}
        assert "cannot state" in diff["reason"]

    def test_with_a_coverage_artifact_the_real_denominator_appears(self,
                                                                   certificate):
        diff = certificate["not_part_of_this_judgment"]["declaration_diff"]
        assert diff["declared"] == 4
        assert diff["matched"] == 3
        assert diff["declared_absent"] == 1


class TestItNeverClaimsAFlatPass:
    @pytest.mark.parametrize("clean", [False, True],
                             ids=["unit-with-findings", "unit-with-none"])
    def test_no_forbidden_claim_appears_anywhere(self, attestation, identity,
                                                 coverage, clean):
        """Both verdicts, because only one of them can contain a flat pass.

        Scanning a certificate that HAS findings can never see the wording a clean
        unit gets -- the test would pass for the whole life of the bug. The clean
        case is the one this check exists for.
        """
        if clean:
            attestation["findings"] = []
            attestation["evidence"] = []
        certificate = build_certificate(attestation, identity, coverage=coverage)
        rendered = json.dumps(certificate).lower()
        for claim in FORBIDDEN_CLAIMS:
            assert claim.lower() not in rendered, (
                f"the certificate claims {claim!r}; the denominator is the "
                f"product and a flat pass hides it")

    def test_a_clean_unit_says_no_findings_recorded_not_pass(self, attestation,
                                                             identity):
        attestation["findings"] = []
        attestation["evidence"] = []
        certificate = build_certificate(attestation, identity)
        assert certificate["judgment"]["verdict"] == "no findings recorded"

    def test_a_clean_unit_still_carries_its_declines(self, attestation, identity):
        attestation["findings"] = []
        attestation["evidence"] = []
        certificate = build_certificate(attestation, identity)
        assert certificate["judgment"]["declined_count"] == 3
        assert "3 check(s) declined" in certificate["judgment"]["statement"]


class TestTheRecordIdentifiesItself:
    def test_the_format_is_declared(self, certificate):
        assert certificate["format"] == CERTIFICATE_FORMAT

    def test_the_generator_and_source_are_recorded(self, certificate):
        assert certificate["generator"]["name"] == "odm-cert-generator"
        assert certificate["source"]["attestation_format"].startswith(
            "bmc-sensor-audit/attestation/")
        assert certificate["source"]["engine_schema_version"] == 1

    def test_the_timestamp_can_be_pinned(self, attestation, identity):
        moment = datetime(2026, 8, 21, 9, 30, tzinfo=timezone.utc)
        certificate = build_certificate(attestation, identity, now=moment)
        assert certificate["generator"]["rendered_at"] == "2026-08-21T09:30:00+00:00"


class TestACoverageRegressionIsAVerdict:
    def test_an_absent_declared_sensor_counts(self, certificate):
        assert has_coverage_regression(certificate) is True

    def test_without_the_artifact_it_cannot_be_claimed_either_way(self,
                                                                  attestation,
                                                                  identity):
        certificate = build_certificate(attestation, identity)
        assert has_coverage_regression(certificate) is False
