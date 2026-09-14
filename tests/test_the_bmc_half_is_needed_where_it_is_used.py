"""`render --walk-digest` reads no walk, and needed a BMC package anyway.

Reported from outside, by somebody looking at what a second vertical would have
to install. Both symbols this module takes from the audit tool are called in one
function -- the one that reads a BMC walk -- and both were imported at module
scope, so every path through the tool required the package.

The seam is unchanged and deliberate: a walk is a BMC's and the attestation
format is a presence audit's. What moved is WHEN the BMC half is required.
"""
from __future__ import annotations

import importlib
import importlib.abc
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cert_generator import certificate

ROOT = Path(__file__).resolve().parents[1]


def _without_bmc(body: str) -> subprocess.CompletedProcess:
    """Run `body` in a fresh interpreter where the BMC package cannot import.

    A SUBPROCESS, because the package is installed in this environment and
    unimporting one inside a live interpreter leaves other modules holding
    references to it -- a probe that proves something about a state no run is
    ever in.
    """
    script = textwrap.dedent('''
        import sys, importlib.abc
        class Blocked(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] == "bmc_sensor_audit":
                    raise ImportError("blocked", name="bmc_sensor_audit")
                return None
        sys.meta_path.insert(0, Blocked())
        sys.path.insert(0, %r)
    ''' % str(ROOT / "src")) + textwrap.dedent(body)
    return subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True)


class TestTheModuleImportsWithoutIt:
    def test_importing_the_module_does_not_need_the_bmc_package(self):
        done = _without_bmc('''
            import cert_generator.certificate
            print("imported")
        ''')
        assert done.returncode == 0, done.stderr[-600:]
        assert "imported" in done.stdout

    def test_a_handle_produced_elsewhere_still_renders(self):
        done = _without_bmc('''
            from cert_generator.certificate import capture_from_digest
            print(capture_from_digest("sha256:abc").digest)
        ''')
        assert done.returncode == 0, done.stderr[-600:]
        assert "sha256:abc" in done.stdout

    def test_reading_a_walk_says_what_to_install(self):
        done = _without_bmc('''
            from cert_generator.certificate import _walk_validators
            try:
                _walk_validators()
            except ImportError as refused:
                print("REFUSED", refused)
        ''')
        assert "REFUSED" in done.stdout, done.stderr[-600:]
        assert "bmc" in done.stdout and "pip install" in done.stdout


class TestNothingMovedForAnybodyWhoHasIt:
    """The control. Every test above would also pass if the walk path had been
    deleted rather than made lazy."""

    def test_the_walk_path_still_validates_and_digests(self, tmp_path):
        walk = tmp_path / "walk.json"
        walk.write_text('{"not": "a walk"}')
        with pytest.raises(Exception) as refused:
            certificate.capture_from_walk(walk)
        assert "walk" in str(refused.value).lower()

    def test_both_symbols_are_reachable_when_the_package_is_there(self):
        validate_walk, walk_digest = certificate._walk_validators()
        assert callable(validate_walk) and callable(walk_digest)
        assert walk_digest(b"abc").startswith("sha256:")

    def test_the_advice_is_derived_and_not_written_down(self):
        """It reads the installed metadata; a restated range went stale once."""
        assert "pip install" in certificate._advice("bmc_sensor_audit")
