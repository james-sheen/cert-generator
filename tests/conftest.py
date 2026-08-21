from __future__ import annotations

import json
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load(name: str):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def attestation() -> dict:
    """A real artifact, produced by the shipped audit tool. See examples/README.md."""
    return _load("attestation.json")


@pytest.fixture
def coverage() -> dict:
    return _load("coverage.json")


@pytest.fixture
def identity_block() -> dict:
    return _load("identity.json")


@pytest.fixture
def identity(identity_block):
    from cert_generator.identity import load_identity
    return load_identity(identity_block)


@pytest.fixture
def certificate(attestation, identity, coverage) -> dict:
    from cert_generator.certificate import build_certificate
    return build_certificate(attestation, identity, coverage=coverage)
