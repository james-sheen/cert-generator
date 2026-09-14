"""The message a stuck reader gets, exercised instead of assumed.

This tool imports its validators from two other packages rather than copying
their rules, so a missing one is a normal way to arrive here -- and the only
thing this program can do about it is say what to install. That sentence was
built from a tuple of both package names and a lookup in
`importlib.metadata`, and it was wrong: metadata describes the wheel INSTALLED
under a name, not the code running, so a checkout ahead of its own release
reads its predecessor's dependencies. A downstream canary running this source
against the published 0.2.1 was told to install `bmc-sensor-audit` while
`presence_audit` was what had not imported. Following that advice to
completion left the reader exactly as stuck.

Nothing could have caught it. The block carried `no cover`, and the advice is
produced only on a failure the suite never provoked. So this file provokes it,
in a subprocess, with the module blocked at the import hook -- once for each
package, because the defect needed TWO of something and only one had ever been
missing at a time.

The specifiers below are absurd on purpose. A version nobody publishes cannot
reach the message by any route except the metadata this test handed it, so a
match is evidence of derivation rather than a coincidence of the environment.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

# Blocks one module at the import hook, optionally lies about this
# distribution's metadata, and prints whatever refusal that provoked -- from the
# import for the attestation half, and from reading a walk for the BMC half.
PROBE = '''
import sys

BLOCK, METADATA, NAMED = sys.argv[1], sys.argv[2], sys.argv[3] == "named"


class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == BLOCK or fullname.startswith(BLOCK + "."):
            if NAMED:
                raise ModuleNotFoundError("blocked by the test", name=fullname)
            # A failure that does not say which module it was. Rare, and the
            # message has a branch for it, so it gets a case.
            raise ImportError("blocked by the test, carrying no module name")
        return None


sys.meta_path.insert(0, Blocker())

import importlib.metadata as metadata

if METADATA == "absent":
    def _raise(name):
        raise metadata.PackageNotFoundError(name)
    metadata.requires = _raise
elif METADATA != "ambient":
    metadata.requires = lambda name: METADATA.split("|")

try:
    import cert_generator.certificate
except ImportError as error:
    print(str(error))
else:
    # THE BMC HALF REFUSES WHERE IT IS USED, not at import. Both validators are
    # called in the one function that reads a walk, so importing this module no
    # longer needs that package -- which is the whole point of the change and
    # would otherwise read here as *the advice stopped being given*.
    try:
        cert_generator.certificate._walk_validators()
    except ImportError as error:
        print(str(error))
    else:
        print("NOTHING WAS RAISED")
'''

# What a current install declares, and what the published 0.2.1 declared: one
# dependency, from before the attestation moved out of the audit tool.
CURRENT = "presence-audit>=9.9.9,<10|bmc-sensor-audit>=8.8.8,<9|fpdf2>=2.7,<3"
STALE = "bmc-sensor-audit>=8.8.8,<9|fpdf2>=2.7,<3"


def advice(block: str, metadata: str = CURRENT, named: bool = True) -> str:
    """Run the probe and return the message, refusing a silent non-failure."""
    result = subprocess.run(
        [sys.executable, "-c", PROBE, block, metadata,
         "named" if named else "anonymous"],
        capture_output=True, text=True, env={"PYTHONPATH": str(SRC)},
        check=True)
    message = result.stdout.strip()
    # Non-vacuity. Every assertion below is about the text of a failure; a run
    # that stopped failing would satisfy most of them by saying nothing.
    assert message and message != "NOTHING WAS RAISED", (
        f"the probe did not provoke an ImportError, so it checked nothing: "
        f"{result.stdout!r} {result.stderr!r}")
    return message


class TestItNamesThePackageThatIsActuallyMissing:
    """The defect: the advice named a package, not THE package."""

    def test_the_missing_one_is_named(self):
        assert "presence-audit" in advice("presence_audit")

    def test_and_so_is_the_other_one(self):
        # N=2. With one of the two always installed the message could be a
        # constant and pass. This is the case that says it is not.
        assert "bmc-sensor-audit" in advice("bmc_sensor_audit")

    def test_the_two_answers_differ(self):
        assert advice("presence_audit") != advice("bmc_sensor_audit")


class TestTheVersionComesFromTheMetadata:
    """Derived, not restated -- and the sentinel proves which."""

    def test_the_declared_specifier_is_offered(self):
        assert "pip install 'presence-audit>=9.9.9,<10'" in advice("presence_audit")

    def test_for_the_other_package_too(self):
        assert "pip install 'bmc-sensor-audit>=8.8.8,<9'" in advice("bmc_sensor_audit")

    def test_no_version_is_invented_when_there_is_no_metadata(self):
        message = advice("presence_audit", metadata="absent")
        assert "pip install presence-audit" in message
        assert "9.9.9" not in message


class TestMetadataOlderThanTheCode:
    """The observed failure, reproduced: the wheel is behind the checkout."""

    def test_it_still_names_the_missing_package(self):
        assert "presence-audit" in advice("presence_audit", metadata=STALE)

    def test_it_does_not_recommend_the_package_that_is_present(self):
        # The regression, pinned by what the reader is told to DO rather than
        # by the sentence that told them. `test_for_the_other_package_too`
        # above is the positive control: this instruction is one the message
        # is perfectly capable of emitting, just not here.
        assert "pip install 'bmc-sensor-audit" not in advice(
            "presence_audit", metadata=STALE)

    def test_it_says_the_version_is_not_knowable(self):
        message = advice("presence_audit", metadata=STALE)
        assert "not knowable" in message
        assert "8.8.8" not in message


class TestAFailureThatDoesNotSayWhichModule:

    def test_it_does_not_guess(self):
        message = advice("presence_audit", named=False)
        assert "does not say which" in message
        assert "presence-audit" not in message
