"""The identity block: refused loudly, or accepted whole."""

from __future__ import annotations

import json

import pytest

from cert_generator.identity import (OPTIONAL, REQUIRED, Identity, IdentityError,
                                     load_identity)


class TestRequiredFields:
    @pytest.mark.parametrize("missing", REQUIRED)
    def test_each_one_is_required(self, identity_block, missing):
        del identity_block[missing]
        with pytest.raises(IdentityError) as raised:
            load_identity(identity_block)
        assert missing in str(raised.value)

    def test_every_problem_is_reported_at_once(self, identity_block):
        """One fault per run means one edit per run. Report them together."""
        for field in REQUIRED:
            del identity_block[field]
        message = str(pytest.raises(IdentityError,
                                    load_identity, identity_block).value)
        for field in REQUIRED:
            assert field in message

    def test_a_blank_field_is_worse_than_a_missing_one(self, identity_block):
        identity_block["station"] = "   "
        with pytest.raises(IdentityError) as raised:
            load_identity(identity_block)
        assert "blank" in str(raised.value)

    def test_a_non_string_is_refused(self, identity_block):
        identity_block["serial"] = 482
        with pytest.raises(IdentityError) as raised:
            load_identity(identity_block)
        assert "not a string" in str(raised.value)


class TestUnknownFields:
    def test_a_typo_is_refused_rather_than_silently_dropped(self, identity_block):
        """`statoin` would otherwise vanish, and nobody reads a certificate
        looking for the field that is not on it."""
        identity_block["statoin"] = "FCT-3"
        with pytest.raises(IdentityError) as raised:
            load_identity(identity_block)
        assert "statoin" in str(raised.value)

    @pytest.mark.parametrize("field", OPTIONAL)
    def test_every_documented_optional_field_is_accepted(self, identity_block,
                                                          field):
        identity_block[field] = "value"
        assert load_identity(identity_block).extra[field] == "value"


class TestLoading:
    def test_from_a_path(self, tmp_path, identity_block):
        path = tmp_path / "identity.json"
        path.write_text(json.dumps(identity_block))
        assert load_identity(path).serial == identity_block["serial"]

    def test_a_missing_file_says_so(self, tmp_path):
        with pytest.raises(IdentityError) as raised:
            load_identity(tmp_path / "absent.json")
        assert "no identity file" in str(raised.value)

    def test_broken_json_says_so(self, tmp_path):
        path = tmp_path / "identity.json"
        path.write_text("{not json")
        with pytest.raises(IdentityError) as raised:
            load_identity(path)
        assert "not valid JSON" in str(raised.value)

    def test_whitespace_is_trimmed(self, identity_block):
        identity_block["serial"] = "  SN-1  "
        assert load_identity(identity_block).serial == "SN-1"

    def test_the_block_round_trips(self, identity_block):
        loaded = load_identity(identity_block)
        assert loaded.to_dict()["customer"] == identity_block["customer"]
        assert set(REQUIRED) <= set(loaded.to_dict())

    def test_it_is_immutable(self, identity):
        with pytest.raises(Exception):
            identity.serial = "SN-2"
