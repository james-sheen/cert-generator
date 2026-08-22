"""The README is the one surface that can promise what no index can deliver.

`bmc-sensor-audit` already carries a pair like this -- its README and its CITATION
file each have to agree with the released state -- but both are anchored on a
version sentinel, `__version__ == "0.0.0"`. That does not transplant here. This
package declares a real `0.1.0` and is on no index, so the sentinel reads
*released*, the check passes, and the README goes on sending readers to a name
PyPI answers 404 for. A mechanism copied without its premise is a check that runs
correctly and asks the wrong question.

What the README can be held to is agreeing with itself: a page that says this is
unreleased must not also hand a reader a command that only works once it is.

`DIST` below is the **distribution** name, which is not the command's. PyPI
refuses `cert-generator` as too similar to an existing `certgenerator`, so this
publishes as `odm-cert-generator` and installs a `cert-generator` script. The
install line is the thing under test here, so the name an index is asked for is
the one that belongs in the matcher.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from cert_generator import __version__

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DIST = "odm-cert-generator"

UNRELEASED = "Not yet released"

# The wording `bmc-sensor-audit` announces a release with. Reused verbatim rather
# than invented, so this family has one vocabulary for one fact and a future
# release here needs no new spelling.
RELEASED = re.compile(r"\*\*Released[^*]*?(\d+\.\d+\.\d+)\*\*")

# `pip install odm-cert-generator`, quoted or not, with or without an extra -- the
# form that only works once an index carries the name. The lookahead is what makes
# it usable while unreleased: `pip install "odm-cert-generator @ git+https://..."` is
# a direct reference, not an index lookup, and must not trip this.
#
# Spelled strictly on purpose: a guard with false positives is a guard the next
# person loosens, and a loosened guard stops catching the real thing.
INDEX_INSTALL = re.compile(
    r"pip install\s+(?:-[^\s]+\s+)*['\"]?"
    + re.escape(DIST)
    + r"(?:\[[A-Za-z0-9,_\-]+\])?['\"]?(?!\s*@)")


def _tags():
    """Repository tags, or None when git cannot answer -- borrowed from
    `bmc-sensor-audit`, caveat included. A checkout with no `.git` exits
    non-zero and an image with no git binary raises; answering `[]` for either
    would turn *cannot tell* into *there are no tags*. A shallow clone fetched
    without tags answers successfully and is still not an answer.
    """
    try:
        listed = subprocess.run(["git", "tag"], cwd=str(ROOT),
                                capture_output=True, text=True)
    except OSError:
        return None
    if listed.returncode != 0:
        return None
    return [line for line in listed.stdout.split() if line]


class TestTheReadmeDoesNotPromiseAnIndex:

    def test_the_readme_states_a_release_state_at_all(self):
        """Non-vacuity, and it is the whole reason this file is not one test.

        Every rule below is conditional on one of these two markers being
        present. Without this, deleting the marker is a way to pass -- the
        prohibition would find nothing and report success, which is the failure
        shape this suite refuses everywhere else.
        """
        readme = README.read_text()
        unreleased = UNRELEASED in readme
        released = RELEASED.search(readme)
        assert unreleased or released, (
            "the README states neither that this is unreleased nor which version "
            f"was released; one of `{UNRELEASED}` or `**Released -- X.Y.Z**` has "
            "to be there for the rest of this file to mean anything")
        assert not (unreleased and released), (
            "the README says both that this is unreleased and that a version was "
            "released; that is two answers to one question")

    def test_an_index_install_is_not_offered_while_unreleased(self):
        readme = README.read_text()
        if UNRELEASED not in readme:
            return
        found = INDEX_INSTALL.search(readme)
        assert not found, (
            f"the README says {UNRELEASED.lower()} and still tells a reader "
            f"{found.group(0)!r}; that command resolves against an index which "
            f"does not carry this name. Offer the direct reference "
            f"`odm-qa-pipeline` already pins for gate 4, or release it")

    def test_a_released_readme_names_the_version_the_package_reports(self):
        """The other branch, so this file keeps working after publication rather
        than becoming a check that only ever meant something once."""
        readme = README.read_text()
        released = RELEASED.search(readme)
        if not released:
            return
        assert released.group(1) == __version__, (
            f"the README announces {released.group(1)} and the package reports "
            f"{__version__}; both are published records of one fact")

    def test_an_announced_release_has_a_tag_behind_it(self):
        """Otherwise the cheapest way past this file is to announce a release
        that did not happen: the version matches because both come from the tree.
        A tag is the one part of the claim the tree cannot write about itself.
        """
        released = RELEASED.search(README.read_text())
        if not released:
            return
        tags = _tags()
        if not tags:
            pytest.skip("no tags visible here; *cannot tell* is not *no tags*")
        assert f"v{released.group(1)}" in tags, (
            f"the README announces {released.group(1)} and no tag v"
            f"{released.group(1)} exists; a release nobody tagged is a claim "
            f"with nothing behind it")

    def test_the_matcher_finds_a_bare_install_when_there_is_one(self):
        """The prohibition above is only worth as much as the pattern under it."""
        assert INDEX_INSTALL.search(f"pip install {DIST}")
        assert INDEX_INSTALL.search(f"pip install '{DIST}[verify]'")
        assert INDEX_INSTALL.search(f"pip install --quiet {DIST}")
        assert not INDEX_INSTALL.search(
            f'pip install "{DIST} @ git+https://example.invalid/x@master"')
        assert not INDEX_INSTALL.search("pip install -r requirements.txt")
        assert not INDEX_INSTALL.search("pip install -e .")


class TestNothingNamesTheCommandAsADistribution:
    """`cert-generator` is the command; `odm-cert-generator` is the thing an
    index carries. Any `pip install` or `pip show` naming the first is a line
    that fails when someone runs it.

    **This is filed after it happened twice in one release.** The rename swept
    `pyproject.toml`, `src/` and `tests/` -- the population I grepped -- and
    missed the CI step that ran `pip show cert-generator`, which found nothing
    and ended the job under `pipefail`, and a `VerificationError` that told
    readers to install a distribution that does not exist. Fixing the two
    instances leaves the class open; this closes it.
    """

    # Not preceded by `odm-`: the correct name contains the wrong one as a
    # substring, so a plain search for it flags every correct line too.
    NAMES_THE_COMMAND = re.compile(
        r"pip (?:install|show)\s+(?:-\S+\s+)*['\"]?(?<!odm-)cert-generator")

    def _shipped(self):
        for pattern in ("src/**/*.py", ".github/workflows/*.yml", "*.md",
                        "pyproject.toml"):
            yield from sorted(ROOT.glob(pattern))

    def test_the_matcher_separates_the_two_names(self):
        """Non-vacuity, and the reason this needed a lookbehind at all."""
        assert self.NAMES_THE_COMMAND.search("pip install cert-generator")
        assert self.NAMES_THE_COMMAND.search("pip show cert-generator")
        assert self.NAMES_THE_COMMAND.search("pip install 'cert-generator[verify]'")
        assert not self.NAMES_THE_COMMAND.search("pip install odm-cert-generator")
        assert not self.NAMES_THE_COMMAND.search(
            "pip show odm-cert-generator | sed -n 's/^Version: //p'")

    def test_no_shipped_file_asks_an_index_for_the_command_name(self):
        """Comment lines are skipped, and that is not tidiness.

        Written without the skip, this flagged the comment above the very line
        it was written to protect -- the one explaining why `pip show
        cert-generator` is wrong. A comment describing a rule is not a breach of
        it, and a guard that cannot tell the difference is one nobody can
        document around. `test_pins.py` skips them for the same reason.
        """
        offences = []
        for path in self._shipped():
            for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.lstrip().startswith(("#", "//")):
                    continue
                if self.NAMES_THE_COMMAND.search(line):
                    offences.append(f"{path.relative_to(ROOT)}:{number}: "
                                    f"{line.strip()[:72]}")
        assert not offences, (
            "these ask an index for `cert-generator`, which it does not carry:\n"
            + "\n".join(offences))

    def test_the_scan_covered_something(self):
        """The check above asserts an absence over a glob. A glob that matches
        nothing asserts an absence over nothing."""
        scanned = list(self._shipped())
        assert len(scanned) >= 6, f"only {len(scanned)} file(s) scanned"
