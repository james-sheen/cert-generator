"""A workflow must not spell out a range this package already declares.

`checks.yml` used to carry `pip install 'bmc-sensor-audit[detect]>=0.1.0,<0.2'`
after the package had already been installed, and it went on installing a 0.1.x
referee after `pyproject.toml` declared `>=0.2.0`. That was found and fixed:
both jobs there now read the range out of the installed metadata.

`seam-canary.yml` carried the identical line and was not fixed. It ran every
morning, downgraded the referee below this package's own floor, and went red at
the combination it had assembled itself -- so the one instrument watching the
seam this repository does not control had spent its signal on its own pin and
could not have reported an upstream break if one had happened.

The fix in one file and not its sibling is why this test scans BOTH and is
parametrised per file rather than asserting over a concatenation: a per-file
failure names the file, and a new workflow is picked up without anyone
remembering to add it here.

**What is a defect and what is not.** An executed constraint is the defect. The
comments in `checks.yml` quote `>=0.1.0,<0.2` while explaining what went wrong,
and they must keep doing that -- a rule that forces prose about a removal to be
deleted buys a clean grep with the history that explains it. So the matcher
requires a `pip install` on the same line, which no comment here has.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

#: A literal version specifier: an operator against a number, with the end of a
#: distribution name or an extras bracket in front of it. Anchored on the left
#: so shell redirection (`2>&1`, `>> "$GITHUB_OUTPUT"`) is not a version.
SPECIFIER = re.compile(r"[\w\].\-]\s*(==|>=|<=|~=|!=|<|>)\s*v?\d")

PIP_INSTALL = re.compile(r"\bpip\s+install\b")


def workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


class TestTheMatcherWorksBeforeItIsTrusted:
    """The guard below asserts an ABSENCE, and an absence passes when the
    matcher is broken. Both directions are proved first."""

    @pytest.mark.parametrize("bad", [
        "python3 -m pip install --quiet --upgrade 'bmc-sensor-audit[detect]>=0.1.0,<0.2'",
        "pip install bmc-sensor-audit>=0.2.0",
        "python3 -m pip install 'fpdf2>=2.7,<3'",
        "pip install pytest==7.4.0",
    ])
    def test_it_catches_a_spelled_out_range(self, bad):
        assert PIP_INSTALL.search(bad) and SPECIFIER.search(bad), bad

    @pytest.mark.parametrize("benign", [
        "python3 -m pip install --quiet --upgrade pip",
        "python3 -m pip install --quiet -e '.[dev]'",
        "python3 -m pip install --quiet -e '.[dev,verify]'",
        'python3 -m pip install --quiet "bmc-sensor-audit[detect]${REQ#bmc-sensor-audit}"',
        '          python-version: "3.12"',
        "      - uses: actions/checkout@v4",
        "          echo \"exit-code=$code\" >> \"$GITHUB_OUTPUT\"",
        "          curl -sS -o /dev/null 2>&1",
        "          # This line used to carry `>=0.1.0,<0.2` -- a range that never matched",
    ])
    def test_it_leaves_a_legitimate_line_alone(self, benign):
        assert not (PIP_INSTALL.search(benign) and SPECIFIER.search(benign)), benign


class TestNoWorkflowRestatesARange:
    def test_there_is_something_to_scan(self):
        """The per-file test below is parametrised over a glob, and a glob that
        matches nothing produces no tests and no failure."""
        found = workflows()
        assert len(found) >= 2, f"{len(found)} workflow(s) found under {WORKFLOWS}"

    @pytest.mark.parametrize("path", workflows(), ids=lambda p: p.name)
    def test_no_install_line_spells_out_a_version(self, path):
        offences = [
            f"line {n}: {line.strip()}"
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if PIP_INSTALL.search(line) and SPECIFIER.search(line)
        ]
        assert not offences, (
            f"{path.relative_to(ROOT)} installs a version range it spells out "
            f"itself. Read it from this package's own metadata instead, the way "
            f"checks.yml does, so the range has one home: "
            + "; ".join(offences))
