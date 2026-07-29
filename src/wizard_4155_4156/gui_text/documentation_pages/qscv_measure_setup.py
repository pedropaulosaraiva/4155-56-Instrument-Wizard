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
| **Measurement Unit** | Which SMU takes the capacitance measurement. **DEFAULT** uses the one selected as VAR1, otherwise pick a specific enabled SMU. |
| **Measurement Range** | The current range used for the capacitance measurement. The choices depend on the instrument model — the HRSMU (4156C) offers the lower **10 pA / 100 pA** ranges, while the MPSMU/HPSMU (4155C) offers **1 nA / 10 nA**. The resolution of the selected range is shown on the line just below the card. |
| **Referenced Mode** | **ON** (the default) restricts the integration times to the manufacturer's reference values and shows the maximum measurable capacitance — see below. |
| **Capacitance Integration Time** | How long each capacitance measurement integrates — longer means less noise but a slower sweep. In Referenced Mode this becomes a dropdown of the supported values. |
| **Leak Integration Time** | How long each leakage-current measurement integrates; it works together with **Leak Compensation**. In Referenced Mode it is locked equal to the Capacitance Integration Time. |
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

## Referenced Mode — maximum measurable capacitance

A quasi-static C-V measurement starts to **oscillate** above a capacitance ceiling that
depends on the current range, the integration time and the capacitance measurement
voltage. The manufacturer publishes reference curves for that ceiling. On a log-log plot
each (range, integration time) pair is a straight line with a slope of −1, so the ceiling
follows a simple inverse law:

```
C_max(V) = A / V
```

where **V** is the **Capacitance Meas Voltage** from the VAR1 card and **A** is the coefficient
for the selected range and integration time.

A new QSCV page opens **in Referenced Mode at 500 ms** — a middle-of-the-grid reference
time that is available on every measurement range and at both 50 and 60 Hz — so the
capacitance ceiling is on screen from the start.

Referenced Mode does three things while it is **ON**:

- The **Capacitance Integration Time** becomes a dropdown limited to the values the reference
  curves were measured at — 2 s, 1 s, 500 ms, 300 ms, and additionally 100 ms, 50 ms and
  30 ms on the 1 nA / 10 nA ranges. Values outside the instrument's own line-cycle limits
  are not offered, so the list also depends on the 50 / 60 Hz line-frequency setting.
- The **Leak Integration Time** is locked equal to it, because that is how the reference
  data was taken.
- The estimated **maximum measurable capacitance** appears under the card and updates
  immediately whenever the range, the integration time or the Capacitance Meas Voltage changes.

### Read the number with care

- **It is a reference value, not a guaranteed limit.** Treat it as guidance, not as a
  specification the instrument will honour.
- **Leave a safety margin.** Keep the device under test roughly **10× to 100× below** the
  displayed value; the card shows that band explicitly. Measuring close to the ceiling
  invites oscillation.
- **Raising the Capacitance Meas Voltage lowers the ceiling.** The maximum measurable
  capacitance and the measurement voltage pull in opposite directions.

Turning Referenced Mode **OFF** restores free entry of both integration times and removes
the capacitance readout. The setting is a configuration aid only: it is not saved with the
setup and it changes none of the commands sent to the instrument. When you **reload a
saved setup**, Referenced Mode switches itself back on only if the stored integration
times already sit on the reference grid and are equal — otherwise the setup reopens in
free entry with its stored values untouched.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Quasi-static C-V Measurements ▸ Measurement Functions.
""".strip()
