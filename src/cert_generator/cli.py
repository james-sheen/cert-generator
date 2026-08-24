"""The command line.

Exit codes are the family's, not new ones: `0` clean, `1` the unit has something
recorded against it, `2` this run could not complete. Precedence is `max`, copied
from the audit tool deliberately -- when a run both found a finding and failed to
finish, the answer is 2, because 2 is the statement about the denominator and 1
would let a reader conclude the rest was checked.

A certificate is still written when the verdict is 1. A QC record for a unit that
failed is a valid document and refusing to produce one would just move the problem
to whoever has to explain the gap in the file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .certificate import (CertificateError, build_certificate,
                          capture_from_digest, capture_from_walk,
                          has_coverage_regression)
from .coverage import CoverageError, load_coverage
from .identity import IdentityError, load_identity
from .render import RenderError, render_pdf
from .verify import VerificationError, verify_projection

EXIT_CLEAN, EXIT_RECORDED, EXIT_INCOMPLETE = 0, 1, 2


def _read_json(path: str, what: str) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CertificateError(f"no {what} at {path}")
    except json.JSONDecodeError as error:
        raise CertificateError(f"{path} is not valid JSON: {error}")


def _render(args: argparse.Namespace) -> int:
    if not args.out_json and not args.out_pdf:
        print("nothing to write: pass --out-json, --out-pdf, or both",
              file=sys.stderr)
        return EXIT_INCOMPLETE

    try:
        attestation = _read_json(args.attestation, "attestation")
        identity = load_identity(args.identity)
        coverage = load_coverage(args.coverage) if args.coverage else None
        capture = None
        if args.walk:
            capture = capture_from_walk(args.walk)
        elif args.walk_digest:
            capture = capture_from_digest(args.walk_digest)
        certificate = build_certificate(attestation, identity, coverage=coverage,
                                        capture=capture)
    except (CertificateError, IdentityError, CoverageError) as error:
        print(f"could not build the certificate: {error}", file=sys.stderr)
        return EXIT_INCOMPLETE

    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(certificate, indent=2, sort_keys=False) + "\n",
            encoding="utf-8")

    if args.out_pdf:
        try:
            render_pdf(certificate, args.out_pdf)
        except RenderError as error:
            # The JSON above may already be on disk, and that is the right order:
            # the record is the artifact, the page is its projection. Say so, so
            # nobody reports a half-run as a clean one.
            print(f"the record was written and the PDF was not: {error}",
                  file=sys.stderr)
            return EXIT_INCOMPLETE

    judgment = certificate["judgment"]
    print(f"Certificate for {certificate['identity']['serial']}")
    print(f"  {judgment['statement']}")
    diff = certificate["not_part_of_this_judgment"]["declaration_diff"]
    if not diff.get("present"):
        print(f"  {diff['reason']}")
    for path in (args.out_json, args.out_pdf):
        if path:
            print(f"  wrote {path}")

    recorded = EXIT_RECORDED if (judgment["findings"]
                                 or has_coverage_regression(certificate)
                                 ) else EXIT_CLEAN
    return max(recorded, EXIT_CLEAN)


def _verify(args: argparse.Namespace) -> int:
    try:
        unbacked = verify_projection(args.certificate, args.pdf)
    except VerificationError as error:
        print(f"could not check the projection: {error}", file=sys.stderr)
        return EXIT_INCOMPLETE

    if unbacked:
        print("numbers on the page that are not in the record: "
              + ", ".join(unbacked), file=sys.stderr)
        return EXIT_RECORDED
    print("every number on the page appears in the record")
    return EXIT_CLEAN


def _check(args: argparse.Namespace) -> int:
    """Delegates to the audit tool's own validator; adds nothing to its rules."""
    from .certificate import validate_attestation
    try:
        artifact = _read_json(args.path, "attestation")
    except CertificateError as error:
        print(str(error), file=sys.stderr)
        return EXIT_INCOMPLETE

    problems = validate_attestation(artifact)
    if problems:
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return EXIT_INCOMPLETE
    print("the attestation is well-formed; a certificate can be built from it")
    return EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cert-generator",
        description="Render a QC certificate from an audit attestation.")
    parser.add_argument("--version", action="version",
                        version=f"cert-generator {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser(
        "render", help="build the certificate as JSON and PDF")
    render.add_argument("--attestation", required=True,
                        help="an attestation/1 artifact from bmc-sensor-audit")
    render.add_argument("--identity", required=True,
                        help="JSON with serial, work_order, station, signer")
    render.add_argument("--coverage",
                        help="JSON from 'bmc-sensor-audit coverage --json'; "
                             "without it the certificate cannot state how many "
                             "declared sensors were present, and says so")
    # Two ways to name the capture, because the walk is often gone by the time a
    # certificate is rendered -- a clean orchestrator run deletes its workdir.
    # Mutually exclusive: supplying both would leave a reader unable to tell which
    # one the printed handle came from.
    which_walk = render.add_mutually_exclusive_group()
    which_walk.add_argument("--walk",
                            help="the recorded walk this judgment was made from; "
                                 "its handle is computed here and the certificate "
                                 "records that it was verified")
    which_walk.add_argument("--walk-digest", metavar="sha256:...",
                            help="a handle produced elsewhere, from "
                                 "'bmc-sensor-audit capture --print-digest'. "
                                 "Recorded as unverified, because nothing here "
                                 "checked it")
    render.add_argument("--out-json", help="write the certificate record here")
    render.add_argument("--out-pdf", help="write the printable projection here")
    render.set_defaults(handler=_render)

    verify = subparsers.add_parser(
        "verify", help="check a PDF against the record it projects")
    verify.add_argument("--certificate", required=True)
    verify.add_argument("--pdf", required=True)
    verify.set_defaults(handler=_verify)

    check = subparsers.add_parser(
        "check", help="validate an attestation without rendering anything")
    check.add_argument("path")
    check.set_defaults(handler=_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":                                   # pragma: no cover
    sys.exit(main())
