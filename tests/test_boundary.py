"""The one prohibition, enforced by reading the source rather than by review.

Identity flows *into* the certificate and never back toward the audit inputs. The
generator may not construct walks, configurations or supplemental files -- the day
it does, the two-trust-domain split is gone and the referee's privacy hygiene
becomes decorative, because the thing holding serial numbers would also be
producing the evidence.

A rule kept only by review survives as long as the reviewer's attention. This one
is a test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "cert_generator"

# The entire permitted surface of the tool under certification, by module and by
# NAME, each with the reason it is allowed.
#
# **Keyed on names rather than modules, and that is load-bearing.** Two of these
# live in `inventory.redfish`, which also holds `RedfishClient` and `walk_chassis`
# -- the things that go and TALK to a machine. Permitting the module would permit
# those, and the prohibition this file exists for is precisely that the generator
# must not produce evidence.
#
# **The rule is read-only, not one particular function.** This started as a single
# name because a single name was all there was, and the first genuine addition --
# citing the capture a judgment came from -- read as a violation when it is the
# same category: a validator and a digest both CONSUME an artifact and construct
# nothing. A guard written from the spelling of its first instance refuses the
# second one for being new rather than for being wrong.
ALLOWED = {
    "bmc_sensor_audit.detect.attestation": {
        "validate_attestation": "the shipped validator for the input format",
        "ATTESTATION_FORMAT": "the format string, so it is not restated here",
    },
    "bmc_sensor_audit.inventory.redfish": {
        "validate_walk": "the shipped validator for a capture the certificate cites",
        "walk_digest": "the content handle, so there is one definition of it",
    },
}

# Names from the tool that must never appear here, whatever the rule above grows
# into. Every one of them reaches a machine or builds an audit input.
FORBIDDEN = ("RedfishClient", "walk_chassis", "read_sensor_object", "MockBMC",
             "load_declaration", "parse_config_text", "load_supplemental",
             "build_attestation", "generate")


def _sources():
    return sorted(PACKAGE.rglob("*.py"))


def _imports_of_the_tool(tree: ast.AST):
    """Every reference to `bmc_sensor_audit`, as (module, names, lineno)."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "bmc_sensor_audit":
                found.append((node.module,
                              [a.name for a in node.names], node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "bmc_sensor_audit":
                    found.append((alias.name, ["<module>"], node.lineno))
    return found


def _offences() -> list[str]:
    found = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module, names, lineno in _imports_of_the_tool(tree):
            permitted = ALLOWED.get(module, {})
            extra = sorted(set(names) - set(permitted))
            if extra:
                found.append(f"{path.name}:{lineno} imports {extra} from {module}")
    return found


class TestTheGeneratorReachesOnlyForReadOnlySurfaces:
    def test_every_import_of_the_tool_is_permitted_by_name(self):
        assert not _offences(), (
            "the generator may consume only the audit tool's shipped read-only "
            "surfaces; reaching further is how it would start constructing audit "
            "inputs: " + "; ".join(_offences()))

    def test_the_permitted_surface_is_small_and_each_entry_says_why(self):
        """A list that grows without a reason per entry is a list that grows."""
        for module, names in ALLOWED.items():
            for name, why in names.items():
                assert why and len(why) > 15, f"{module}.{name} has no reason"
        assert sum(len(n) for n in ALLOWED.values()) <= 6, (
            "the permitted surface has grown past a handful of names. That is the "
            "shape of a boundary being negotiated one import at a time")

    @pytest.mark.parametrize("name", FORBIDDEN)
    def test_a_constructor_would_still_be_refused(self, name, tmp_path):
        """**Non-vacuity, in the direction that matters.** The check above passes
        on a package that imports nothing at all, and it passed for months on an
        allowlist of one name. This proves it still says no -- by running it over
        a file that reaches for the machine.

        Written against `inventory.redfish` deliberately: two names from that
        module ARE permitted, so this also proves the allowlist is per-name and
        did not quietly become per-module."""
        offender = tmp_path / "cert_generator" / "leak.py"
        offender.parent.mkdir(parents=True, exist_ok=True)
        offender.write_text(f"from bmc_sensor_audit.inventory.redfish import {name}\n")

        tree = ast.parse(offender.read_text())
        imports = _imports_of_the_tool(tree)
        assert imports, "the import scanner stopped seeing the tool"
        module, names, _ = imports[0]
        assert set(names) - set(ALLOWED.get(module, {})) == {name}

    def test_the_validator_is_actually_imported(self):
        """Otherwise the test above passes by finding nothing.

        A prohibition that holds because the package stopped talking to the tool
        entirely is not the prohibition being tested -- and it would mean the
        certificate was no longer validating its input at all.
        """
        seen = False
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for module, names, _ in _imports_of_the_tool(tree):
                if (module == "bmc_sensor_audit.detect.attestation"
                        and "validate_attestation" in names):
                    seen = True
        assert seen, ("no module imports validate_attestation; the certificate "
                      "would be rendering unvalidated artifacts")


class TestNothingConstructsAuditInputs:
    # Names that would mean this package had started producing the evidence it
    # exists to present. Matched as whole identifiers against the parsed source.
    FORBIDDEN_CALLS = {"walk", "capture_walk", "build_walk", "read_config",
                       "load_declaration", "build_supplemental", "MockBMC",
                       "urlopen", "Request", "HTTPSConnection", "HTTPConnection"}

    def test_no_audit_input_is_constructed(self):
        offences = []
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", None) or getattr(
                        node.func, "attr", None)
                    if name in self.FORBIDDEN_CALLS:
                        offences.append(f"{path.name}:{node.lineno} calls {name}()")
        assert not offences, (
            "the generator constructs an audit input: " + "; ".join(offences))

    def test_no_network_client_is_imported(self):
        """It has no business talking to a BMC. Nothing it renders comes from one."""
        offences = []
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                for module in modules:
                    root = module.split(".")[0]
                    if root in {"urllib", "http", "requests", "socket", "ssl"}:
                        offences.append(f"{path.name}:{node.lineno} imports {module}")
        assert not offences, (
            "a certificate generator that can reach a machine can be asked to "
            "re-run the audit it is presenting: " + "; ".join(offences))


class TestIdentityIsOneDirectional:
    def test_identity_module_is_not_imported_by_the_coverage_reader(self):
        """Identity must not reach the modules that parse audit artifacts.

        `coverage.py` reads a tool artifact. If it could see the identity block it
        could annotate, filter or re-key that artifact by unit -- which is the
        prohibition running backwards.
        """
        tree = ast.parse((PACKAGE / "coverage.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "identity" not in node.module, (
                    "coverage.py imports identity; audit artifacts must be parsed "
                    "without knowing which unit they belong to")
