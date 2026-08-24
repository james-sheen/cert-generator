"""Render a QC certificate from an attestation the audit tool produced.

This package holds unit identity -- serial number, work order, station, signer --
which the audit tool deliberately refuses to hold. Two trust domains, split on
purpose: the referee cannot leak what it never sees, and a certificate can say
what a certificate must.

The version lives here and nowhere else. `pyproject.toml` reads it through
hatchling rather than repeating it, because a version written in two places is a
version that will disagree with itself and no check will notice.
"""

__version__ = "0.1.2"

CERTIFICATE_FORMAT = "cert-generator/certificate/1"

__all__ = ["__version__", "CERTIFICATE_FORMAT"]
