# Where these came from

Both artifacts are real output from `bmc-sensor-audit 0.1.0`, not hand-written
shapes. A fixture written by hand to match a format is a fixture that agrees with
whatever the author believed the format was — and the whole reason this package
validates its input with the tool's own validator is that believing is not
checking.

## How they were produced

A `MockBMC` from `bmc_sensor_audit.testing.mock_redfish` served four declared
sensors, one of which was never registered on the mock at all:

| sensor | declared | served | why |
|---|---|---|---|
| Inlet Temp | upper critical 80.0 | 92.4 | a finding with a measurement behind it |
| Outlet Temp | upper critical 80.0 | 31.5 | a healthy neighbour, so the run is not uniformly bad |
| P12V | 10.8 – 13.2 | 12.1 | a second healthy entity, in different units |
| Fan 3 Tach | lower critical 500 | *absent* | declared and never reported — the coverage finding |

Then:

```
bmc-sensor-audit detect   --config board.json --target $URL \
                          --attest-out attestation.json \
                          --attest-target-label reference-board
bmc-sensor-audit coverage --config board.json --target $URL --json
```

`tests/test_seam.py` reproduces the first of those end to end against whichever
version of the audit tool is installed, which is how a format change inside the
`>=0.1.0,<0.2` pin gets noticed here rather than at a customer.

## Two fields in `coverage.json` were replaced, and only two

The mock serves on an ephemeral port and writes its configuration to a temporary
directory, so `target` and `declared_in` differ on every run and would make the
file noise in a diff. They now read:

```
target      https://bmc-a17.mfg.internal
declared_in /opt/entity-manager/configurations/reference-board.json
```

Everything else is exactly what the tool emitted. The substitution is deliberate
in a second way: those two fields are the ones `cert_generator.coverage` drops
before rendering, and stable stand-ins that *look* like a real factory's make
`tests/test_privacy.py` a check rather than a coincidence.

`attestation.json` is unmodified.

## The identity block

`identity.json` is invented — there is no unit. Every value in it is a plausible
shape rather than a real serial, work order or person.
