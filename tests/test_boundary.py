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

# The entire permitted surface of the tool under certification. Both names come
# from one module, and that module deliberately does not import the engine.
ALLOWED = {"validate_attestation", "ATTESTATION_FORMAT"}
ALLOWED_MODULE = "bmc_sensor_audit.detect.attestation"


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


class TestTheGeneratorReachesOnlyForTheValidator:
    def test_every_import_of_the_tool_is_the_validator(self):
        offences = []
        for path in _sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for module, names, lineno in _imports_of_the_tool(tree):
                if module != ALLOWED_MODULE or not set(names) <= ALLOWED:
                    offences.append(
                        f"{path.name}:{lineno} imports {names} from {module}")
        assert not offences, (
            "the generator may consume only the audit tool's shipped attestation "
            "validator; reaching further is how it would start constructing audit "
            "inputs: " + "; ".join(offences))

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
                if module == ALLOWED_MODULE and "validate_attestation" in names:
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
