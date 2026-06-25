"""QSCV Mode overview documentation page (QSCV Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# QSCV Mode

**QSCV** (quasi-static capacitance–voltage) mode sweeps a DC voltage across a
device and measures its **capacitance** at each step, producing a
capacitance-versus-voltage curve.

## How the measurement works

At each DC voltage step, the instrument finds the capacitance by nudging the
output across a **small voltage window** centred on that step and watching how
much charge moves. Capacitance is simply the **charge that flows during the
measurement, divided by the size of that voltage nudge**.

That picture explains most of the settings on the page:

- The **width of the window** is the **QSCV Meas Voltage**, set on the **VAR1 —
  Voltage Sweep** card. It has to fit inside one sweep step.
- How long each measurement integrates — and so how quiet it is — is the **QSCV
  Integration Time**, set on the **QSCV Measure Setup** card.
- The sweep's **Start** and **Stop** voltages are **not** measured; only the steps
  in between are.

Two optional refinements improve accuracy, both on the **QSCV Measure Setup** card:

- **Leak Compensation** subtracts the device's steady leakage current so it does
  not get mistaken for capacitance.
- **Zero Cancel** removes a fixed capacitance offset.

## The QSCV Configuration page

The page is built from a channel configuration — most often by clicking
**⚙️ Generate Setup Page** on the **Channels** page, but it can also be opened by
copying a previously saved setup. It is laid out in two columns:

- **Left** — **Channel Summary**, **User Functions** (the capacitance and leakage
  variable names), and **Display Variables**.
- **Right** — **QSCV Measure Setup**, **VAR1 — Voltage Sweep**, **Constant
  Sources**, and **QSCV Timing**.

QSCV brings its own measurement settings, so it does **not** use the shared
Measurement Setup or Measurement Ranges cards that sweep and sampling rely on.

A status line in the header reports whether the configuration is valid and, when
it is, how many **sweep steps** it will run; the **Generate JSON**, **Save JSON**,
and **Save Setup** buttons stay disabled until it is valid.

## Where to go next

- **VAR1 — Voltage Sweep** — the DC voltage staircase and the measurement window.
- **QSCV Measure Setup** — which unit measures, the current range, the integration
  times, and the two accuracy options.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Quasi-static C-V Measurements ▸ Measurement Functions.
""".strip()
