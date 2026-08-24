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


# **The ANCHOR for every version record in this repository.** `pyproject.toml`
# reads the literal for packaging, so it is the one record that cannot disagree
# with the artifact -- and the only one that answers in an sdist and in a shallow
# checkout with no tags. Everything else is compared against it, never against
# another derivation of it.
NO_RELEASE = "0.0.0"

#: The tag the README's Status line names, so the two can be compared without
#: asking git anything.
TAGGED = re.compile(r"tagged `([^`]+)`")

#: The tag namespace this project releases in: `v` and a dotted version.
_TOOL_TAG = re.compile(r"^v(\d+(?:\.\d+)*)$")


def _released_versions(tags):
    """Every tag naming a version of THIS package, as comparable tuples."""
    return [tuple(int(part) for part in match.group(1).split("."))
            for match in (_TOOL_TAG.match(tag) for tag in tags) if match]


def _named_tag():
    """The tag string the README's Status line names, or None."""
    found = TAGGED.search(README.read_text())
    return found.group(1) if found else None


def _version():
    from cert_generator import __version__
    return __version__


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

    def test_the_readme_names_the_tag_this_version_will_carry(self):
        """The tag string and the version literal, compared without asking git.

        **The anchor is the version LITERAL.** It is what the package reports
        about itself, what `pyproject.toml` reads for packaging, and the only one
        of these records that answers in an sdist and in a shallow checkout with
        no tags. Every other record is derived from it, so every other record is
        compared against it rather than against another derivation.

        The Status line carries a tag string that nothing used to check, so a
        `v0.1.1` left behind by a bump to 0.1.2 sent a reader to a tag describing
        different code -- and both strings look right in isolation.

        Tree-local, so it holds at every instant of a release. The check below
        cannot say that of itself.
        """
        version = _version()
        named = _named_tag()
        if version == NO_RELEASE:
            assert named is None, (
                f"the README names the tag {named!r} while the package reports "
                f"{NO_RELEASE}; an unreleased tree must not hand a reader a tag "
                f"to check out")
            return
        assert named, (
            f"the package reports {version} and the README names no tag. The "
            f"Status line should read: tagged `v{version}`")
        assert named == f"v{version}", (
            f"the README names the tag {named!r} and the package reports "
            f"{version}; they must be `v{version}`. A leading v dropped from one, "
            f"or a tag string left behind by a bump, is how these two part company")

    def test_a_tag_and_the_tree_do_not_disagree(self):
        """A tag is the one part of the claim the tree cannot write about itself.

        **What was wrong with this before.** It tolerated only a repository with
        NO TAGS AT ALL -- true when written, false forever after the first
        release. The tag is made OF the commit that bumps the version, so from
        then on it went red between the bump and the tag, every release, at the
        moment somebody is most likely to reach for `--no-verify`.

        Worse than red, it RACED. CI fetches whatever tags the remote holds at
        checkout and a release pushes master before the tag, so a release
        commit's own CI run passed or failed on which push won.

        **The window is carved to the rule rather than widened.** Only this
        version may be untagged, and only while no LATER version is tagged: a
        release in flight is always the newest one. A reverted bump that left its
        tag, or a tag made from the wrong commit, both leave a later tag behind
        and still fail here.

        Whether the tag was ever PUSHED is a fact about the remote, and no
        assertion from a working tree can reach it. Saying so is the honest
        version; asserting it would be a check that is right by luck.
        """
        tags = _tags()
        if not tags:
            pytest.skip("no tags visible here; *cannot tell* is not *no tags*")
        version = _version()
        assert version != NO_RELEASE, (
            f"the repository has tags {tags} and the package still reports "
            f"{NO_RELEASE}")
        if f"v{version}" in tags:
            return
        current = tuple(int(part) for part in version.split("."))
        ahead = sorted(t for t in _released_versions(tags) if t > current)
        assert not ahead, (
            f"v{version} has no tag, and "
            f"{['v' + '.'.join(map(str, t)) for t in ahead]} name later versions. "
            f"A release in flight is the only reason this version should be "
            f"untagged, and a release in flight is always the newest one -- so "
            f"either a bump was reverted with its tag left behind, or a tag was "
            f"made from the wrong commit")
        pytest.skip(
            f"v{version} is not tagged in this tree. The tag is made OF the "
            f"commit that sets the version literal, so this is the one legitimate "
            f"window and `git tag -a v{version}` closes it. Whether the tag was "
            f"ever pushed is a fact about the remote rather than this tree.")

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
