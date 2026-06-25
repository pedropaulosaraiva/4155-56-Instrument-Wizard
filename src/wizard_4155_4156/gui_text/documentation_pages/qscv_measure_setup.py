"""QSCV Measure Setup documentation page (QSCV Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# QSCV Measure Setup

The **QSCV Measure Setup** card chooses which unit measures the capacitance, how
sensitive and how long each measurement is, and the two accuracy options. QSCV
keeps its own measurement settings here rather than using the shared Measurement
Setup and Measurement Ranges cards — and the front-panel Short / Medium / Long
integration choice has no effect on a QSCV measurement.

## Controls

| Control | What it does |
|---------|--------------|
| **Measurement Unit** | Which SMU takes the capacitance measurement. **DEFAULT** lets the instrument choose; otherwise pick a specific enabled SMU. |
| **Measurement Range** | The current range used for the capacitance measurement. The choices depend on the instrument model — the HRSMU (4156C) offers the lower **10 pA / 100 pA** ranges, while the MPSMU/HPSMU (4155C) offers **1 nA / 10 nA**. The resolution of the selected range is shown on the line just below the card. |
| **QSCV Integration Time** | How long each capacitance measurement integrates — longer means less noise but a slower sweep. |
| **Leak Integration Time** | How long each leakage-current measurement integrates; it works together with **Leak Compensation**. |
| **Leak Compensation** | **ON** subtracts the device's leakage current from the capacitance result. |
| **Zero Cancel** | **ON** removes a fixed capacitance offset from the result. |

## Behaviour to know

- **Range drives the resolution readout.** Changing the **Measurement Range**
  updates the *Resolution:* line beneath the controls, so you can see the smallest
  change that range can resolve.
- **Integration time is entered in seconds but bounded in line cycles.** You type
  the two integration times in seconds, but their allowed ranges are defined as a
  number of power-line cycles — so the limits shift with the instrument's 50 / 60 Hz
  line-frequency setting.
- **Leak Compensation needs a name.** With Leak Compensation **ON**, the
  configuration will not validate until a valid **Leakage Current Name** is entered
  on the **User Functions** card.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Quasi-static C-V Measurements ▸ Measurement Functions.
""".strip()
