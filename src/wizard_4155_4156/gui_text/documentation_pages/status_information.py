"""Information documentation page (Setup Status)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Information

The **Information** column reports what the current setup will *do* when it runs —
how many measurement points it produces and roughly how long it will take. These
figures update live as you edit; unlike the Critical and Warnings columns, they
never block saving.

## What each figure means

| Row | Meaning |
|-----|---------|
| **Total measurement indexes** | The number of measurement *steps* the instrument performs — one index per source step (Sweep/QSCV) or per sample (Sampling). |
| **Total measurement points** | The number of stored data values: **indexes × number of measured display variables**. |
| **Minimum runtime** | An estimate of the total run time, scaled to a readable unit (ms / s / min / h) and shown as `> value` or a `> min - max` range (or `> indeterminate`, see below). |
| **Current setup status** | *Ready to Save* when no critical errors remain, otherwise *Not Ready*. |

### Indexes

An *index* is one point in the measurement series.

- **Sweep / QSCV** — `indexes = VAR1 points × (2 if DOUBLE sweep else 1) × VAR2 steps`
  (QSCV always uses a single VAR2 step). For a linear VAR1 sweep the point count
  comes from Start, Stop and Step; for a logarithmic sweep, from the decade span
  and the points-per-decade.
- **Sampling** — `indexes = number of samples`.

### Points

`points = indexes × (units that will actually measure)`. A unit is counted only
when it is **enabled and its measured variable is selected for display**. A VMU in
DVOLT mode contributes a single stored value.

### Estimated runtime

The estimate follows the instrument's measurement model:

- **Sweep / QSCV** — `Execution ≈ Hold + (Delay + Measurement interval) × indexes`.
- **Pulse sweep** (one SMU in VPULSE/IPULSE mode) — `Execution = Hold + Pulse
  Period × indexes`. The Delay is ignored (each step is paced by one pulse
  period), so the estimate is a **single deterministic value** rather than a
  range — though it becomes a lower bound if the instrument extends the pulse
  width automatically (see the **Warnings** page).
- **Sampling, fixed total time** — `Execution ≈ Hold + Total Sampling Time`.
- **Sampling, automatic (linear)** — `Execution ≈ Hold + adjusted interval × samples`,
  where the *adjusted interval* is the smallest multiple of the Initial Interval
  that is at least as long as one measurement (the instrument cannot start a new
  sample before the previous measurement finishes).
- **Logarithmic sampling** and a **No-Limit** total sampling time have no bounded,
  predictable duration, so the estimate is shown as **indeterminate**.

## Why it is only an estimate

The figure that drives the runtime — the **measurement interval** — is itself
estimated, and two real-world contributions are deliberately left out.

First, the underlying identity:

> **Measurement time = Integration time + Overhead time**

*Integration time* is the time the A/D actually spends acquiring and averaging
samples. *Overhead time* covers range changing, data compensation and similar
bookkeeping — none of which this estimate tries to predict.

- **Auto-ranging overhead is not counted.** Under AUTO / limited-auto ranging the
  instrument may switch measurement ranges between points, and each switch costs
  time that cannot be known in advance. Because the run-time current range is
  unknown, the effective integration time is reported as a `min–max` interval
  spanning the fastest and slowest possible ranges — which is why the runtime
  is often shown as a range rather than a single value.
- **Stabilization / wait time is not counted (Sweep and QSCV).** After each source
  step the instrument waits for the measurement to settle before it integrates.
  This wait is set by the instrument and strongly influenced by the DUT (its
  capacitance, settling behaviour, and so on), so it cannot be predicted here and
  is excluded from the estimate.

### About integration time

To reduce errors from line-frequency and other environmental noise, the
4155C/4156C takes several samples per measurement and averages them; a **longer
integration time means more samples and more accurate data**. The setting applies
to every measurement unit.

- For **Sweep** and **Sampling**, integration time is chosen with the
  **Short / Medium / Long** setting.
- For **QSCV**, integration time is the value in the QSCV Measure Setup; the
  Short/Medium/Long keys have **no effect** in this mode.

The *effective* integration time depends on the measurement type (voltage vs
current), the current and output-voltage ranges, the integration mode and the SMU
model (HRSMU on the 4156C, MPSMU on the 4155C) — which is why the same setting can
yield different times on different channels.

> **ADC Zero (Medium / Long).** An automatic ADC-zero step cancels the A/D offset
> and effectively **doubles** the integration time. It applies to voltage
> measurements and to current measurements on the 10 nA range or greater.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Measurement Time / Integration Time, plus the setup's runtime model.
""".strip()
