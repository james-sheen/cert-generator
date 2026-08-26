# cert-generator

Render a QC certificate from a [`bmc-sensor-audit`](https://github.com/james-sheen/bmc-sensor-audit)
attestation.

**Released — 0.2.0**, tagged `v0.2.0`, Apache-2.0, on PyPI as
`odm-cert-generator`.

**0.2.0 raises the referee floor to 0.2.0.** From there the referee refuses a
command that asks to verify and not to verify at once, instead of running
unverified — and a certificate rendered from a walk taken over an unverified
connection is a document nobody should rely on. What this package does is
unchanged; the break is in the floor.

0.1.3 carried the repository's publication-hygiene tooling: the rules run over
commit messages as well as files, and a pre-commit hook refuses a commit whose
staged content it has not read.

0.1.2 lets a certificate name the capture it was judged from. The audit tool
refuses to hold unit identity and this package holds nothing else, so the
binding between them has to happen on content — and a content handle is what
`bmc-sensor-audit` 0.1.1 supplies. Needs that version.

**The distribution and the command differ, and the reason is worth one line.**
PyPI ultranormalises a name by stripping its separators, so `cert-generator`
becomes `certgenerator` — which an unrelated project holds — and the upload is
refused as *too similar to an existing project*. So this publishes as
`odm-cert-generator` and installs a command still called `cert-generator`. A
certificate records the **distribution** name, because that is the one that
resolves on an index.

```
pip install odm-cert-generator

cert-generator render \
    --attestation attestation.json \
    --identity identity.json \
    --coverage coverage.json \
    --out-json certificate.json \
    --out-pdf certificate.pdf
```

## What it is for

The audit tool judges a machine and deliberately keeps the machine's identity out
of everything it writes. A certificate has the opposite job: it has to name the
unit. This renders one from the other, and holds the serial number on its own side
of the line.

Two trust domains, split on purpose. The referee cannot leak what it never sees.
The certificate can say what a certificate must.

## The certificate never claims a flat pass

It will not print "100 % match". It prints the denominator:

```
6 invariant(s) checked over 3 entit(ies); 1 finding(s) recorded;
3 check(s) declined and therefore not judged
```

...and then a section headed **Not part of this judgment**, which is emitted even
when every list in it is empty — because an absent section reads as *nothing was
left out*, and that is a claim.

That section carries:

| | |
|---|---|
| the declines | each with the engine's machine-readable reason |
| `unattested` | problem types the engine would not attest |
| `unread_feeds` | data that was read and not used |
| the declaration diff | declared vs. present, when supplied — see below |
| the engine's boundary | quoted verbatim, not paraphrased |

A certificate showing what was *not* checked is one an incoming-inspection team
can act on. The denominator is the point, not a concession.

## The declaration diff is a second, optional input

`attestation/1` records what the engine judged. It does not record what was
*declared and never showed up*. Run the audit tool against a board declaring four
sensors where one is absent and the artifact reads `checked: {entities: 3}` — three,
with nothing on it saying three of four.

So `--coverage` takes the JSON from `bmc-sensor-audit coverage --json`, which does
carry the diff. Supply it and the certificate states declared-vs-present and names
the absent sensor. Leave it out and the certificate says, on the page:

> no declaration diff was supplied, so this certificate cannot state how many
> declared sensors were present; the attestation counts only entities that reached
> the engine

It is optional because requiring it would make a certificate impossible for anyone
holding only an attestation. It is *stated* because the smaller denominator must
not pass for the whole picture.

**That coverage artifact is written for a CI log, not a customer.** It names the
BMC by URL and the configuration by filesystem path. Both are dropped here before
anything is rendered; see `tests/test_privacy.py`.

## The PDF is a projection of the JSON

No number appears in the PDF that is absent from the certificate JSON. The JSON is
the record; the PDF is how it looks. Anyone holding both can check one against the
other without trusting this code:

```
cert-generator verify --certificate certificate.json --pdf certificate.pdf
```

Shipped rather than kept in a CI script, for the same reason the audit tool ships
its attestation validator: the person who *receives* the document is the one who
needs to check it.

The suite checks the same property with poppler's `pdftotext` — a reader nobody
here wrote.

## Which capture the judgment came from

The audit tool refuses to hold unit identity; this package holds nothing else. The
binding between the two has to happen on **content**, and since the tool shipped a
content handle there is finally something to bind to:

```
cert-generator render --attestation attestation.json --identity identity.json \
                      --walk walk.json          # computes and verifies the handle
cert-generator render ... --walk-digest sha256:81422480...   # records one produced elsewhere
```

Both are legitimate and they are **not the same claim**, so the record carries
which one it is. `--walk` means this program read the file and computed the
handle; `--walk-digest` means it was handed the value and checked nothing. A clean
orchestrator run deletes its walks long before a certificate is rendered, so often
the handle is all that survives — that case is supported and labelled rather than
quietly presented as a measurement.

The handle is a SHA-256 over the walk file's bytes, computed with the audit tool's
own function so there is one definition of it rather than two. A recipient
matches it with `sha256sum` and no tooling at all; a walk that does not match is
not the walk that was judged. A malformed handle is refused rather than printed —
one that looks like proof and matches nothing is worse than none.

Reading a walk is not a boundary crossing. A walk carries no identity by
construction: the audit tool serialises the parsed sensor set and never the raw
payloads, which is the same rule described below.

## Identity goes one way

Identity flows *into* the certificate and never back toward the audit inputs. This
package does not construct walks, configurations or supplemental declarations, and
has no HTTP client. `tests/test_boundary.py` enforces it by parsing this package's
own imports, because a rule kept by review lasts exactly as long as the reviewer's
attention.

The only thing it may reach for in the audit tool is `validate_attestation` — the
tool's *shipped* validator, not a second copy of its rules. A shapeless artifact is
refused, not decorated.

## Exit codes

The family's contract, not this tool's invention:

| | |
|---|---|
| `0` | certificate written; nothing recorded against the unit |
| `1` | certificate written; findings, or a declared sensor absent |
| `2` | could not complete — nothing was judged |

Precedence is `max`, copied from the audit tool. A run that both found something
and failed to finish reports `2`, because `2` is the statement about the
denominator and `1` would let a reader conclude the rest was checked.

A certificate is still written when the verdict is `1`. A QC record for a unit that
failed is a valid document.

## A certificate is not the pipeline's verdict

Two records run in parallel and neither contains the other. This one certifies what
the referee established about a unit: the attestation, the identity, and the
declaration diff when one is supplied. Conformance and fault injection are not in
it. Those meet in `odm-qa-pipeline aggregate`, which answers a different question —
did all four gates run, and what is the worst thing any of them found.

Worth stating because reading either as the other goes wrong in both directions: a
clean certificate says nothing about whether the injection gate ran, and a clean
pipeline verdict is not a document anyone can hand to a customer.

## The identity block

```json
{
  "serial": "SN-A17-000482",
  "work_order": "WO-2026-08-1174",
  "station": "FCT-3",
  "signer": "L. Okonkwo",
  "part_number": "PN-88213-B",
  "customer": "Example Hyperscale Inc.",
  "line": "Kaohsiung 2"
}
```

The first four are required. The rest are optional and rendered when present.
Nothing is inferred, and an unrecognised key is **refused** rather than dropped —
a typo would otherwise vanish silently, and nobody reads a certificate looking for
the field that is not on it.

## Known limits, written down rather than implied

- **Latin-1 only.** The built-in PDF fonts cannot draw characters outside it. An
  identity field containing them is refused, not transliterated: a serial number
  silently rewritten is worse than a failed render. Shipping a Unicode font would
  lift this; it has not been done.
- **`verify` needs a PDF reader.** poppler's `pdftotext` if it is on `PATH`,
  otherwise `pip install 'odm-cert-generator[verify]'` for pypdf. If neither is
  present the command exits `2` — not finding a reader is not a pass.
- **Nothing here re-audits the machine.** `verify` proves the page matches the
  record. The record's authority comes from the attestation, and the
  attestation's from the engine.
- **One page.** Automatic page breaks are off on purpose, so a certificate that
  overflows is visible as overflow rather than quietly paginated. A unit with very
  many findings will need the JSON.

## Where it sits

```
arbiter-engine        the invariant envelope
bmc-sensor-audit      the referee: declaration diff, liveness, attestation
cert-generator        this: identity, and the honest certificate
```

**No version ranges in that diagram, on purpose.** It carried two and both had
gone false — an `arbiter-engine` floor this package does not declare at all, and
a `bmc-sensor-audit` floor one patch below the real one. The pin that binds is
in `pyproject.toml`; `pip show odm-cert-generator` prints what your install
actually resolved. A number whose only job is to be current belongs where it is
enforced, not in a picture.

`qa-orchestrator` sits beside this one, injecting faults and checking the referee
caught them. `odm-qa-pipeline` composes all of them.

## Licence

Apache-2.0.
