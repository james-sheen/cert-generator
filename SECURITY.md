# Security

## Report privately

**Use GitHub's private vulnerability reporting** — the *Security* tab on this
repository, *Report a vulnerability*. That opens a channel visible only to the
maintainer.

**Do not open a public issue for anything in the list below.** The failure modes
here are ones where *the report itself is the disclosure*: an issue saying *my
certificate came out with this serial printed on it* has, by being filed,
published the serial.

If private reporting is unavailable to you, open a public issue saying only
**that** you have something to report and nothing about what it is.

## What counts as a security issue here

This package is the one place in its family that **holds unit identity** — serial
number, work order, station, signer. The referee it reads from refuses to hold
any of that on purpose, so identity enters here and must never travel back the
other way. Two consequences:

**1. Identity must not escape into an audit input.** A certificate is an output;
the attestation and coverage files behind it are inputs and carry no identity.

- **Any path by which an identity field reaches an audit artifact**, a log line,
  an error message or a traceback is a security issue.
- **Any real serial, work order or signer appearing in this repository** is a
  security issue, including in an example or a test fixture.
- **A gap in `tools/hygiene_check.py`** — a rule that does not fire on a hazard
  it claims to cover — is a security issue even with nothing currently leaking.

**2. A certificate is a document someone will rely on.** It states what was
checked and what was not.

- **Anything that makes the rendered page claim more than the record supports**
  is a security issue, not a cosmetic one. The projection check
  (`cert-generator verify`) exists to make that falsifiable; a way to pass it
  while the page and the record disagree is the defect it is there to prevent.
- **A declined check rendered as a passed one**, or a *Not part of this judgment*
  section that omits something genuinely omitted, is the same class.

## What does not need private handling

Ordinary defects, layout problems, font and encoding failures, crashes on
malformed input, and refusals working as designed — a field outside Latin-1 is
**refused rather than transliterated**, deliberately, because a silently
rewritten serial is worse than a failed render.

## What to expect

A single maintainer, no service-level commitment, and no bounty. You will get an
acknowledgement and an honest answer about whether and when it will be fixed —
including *not soon*, when that is true.

**The supported version is the latest release on PyPI**, published as
`odm-cert-generator`, and nothing older. A fix lands on the default branch and
ships in the next release; the reply will say which. No version literal appears
in this file on purpose — a number here is a number that goes stale.

## Scope

This repository only. A vulnerability in a BMC, in OpenBMC, in DMTF's validators
or in a vendor's firmware belongs to that project or vendor. If this tool
*surfaces* such a flaw, the flaw is still theirs — report it to them, and by all
means tell us the tool helped.
