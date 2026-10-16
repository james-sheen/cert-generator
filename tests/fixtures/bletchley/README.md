# Where these came from

A board whose record does not fit one page: the bletchley board as `bmc-sensor-audit` 0.3.18 judged it from
its own vendored recording. Real output of the released tool, not shapes written by hand -- see
`examples/README.md` for why that matters here.

## How they were produced

From a clone of `bmc-sensor-audit` at `v0.3.18`, in `tests/fixtures/`, with that version installed from
PyPI with its `detect` extra:

```
bmc-sensor-audit detect   --config upstream/meta/bletchley --walk walk_qemu_bletchley.json \
                          --attest-out attestation.json
bmc-sensor-audit coverage --config upstream/meta/bletchley --walk walk_qemu_bletchley.json --json
```

The walk is upstream OpenBMC firmware booted under QEMU and walked over Redfish, recorded by that project;
the three configurations are the board's own, from upstream `entity-manager`. What the two files say:

| | |
|---|---|
| attestation | 56 checks over the 28 sensors that reported; 26 findings, each a reading past a declared limit; 28 stability checks declined for too few observations |
| coverage | 86 declared, 28 matched, 58 declared and absent -- each one a device the emulated board does not have |

The readings are an emulator's, so the findings are not a board's health. They are here for their number:
26 findings and 58 absences are more than one page holds.

The walk's content handle, which the tests pass as supplied rather than computed because the walk is not
vendored here, is
`sha256:9a59dad65f8ed74a9b0549ae469404db065e19907d98adc55bd5259d81140271`.

## What they pin

On 0.2.5 this certificate was one page with page breaks off, and the library drew everything after the
second measurement below the page's edge: *Not part of this judgment*, the 58 absent sensors, the capture
handle. `verify` passed it. `tests/test_the_page_carries_the_record.py` pins both halves of the fix.
