"""VAR1 — Voltage Sweep documentation page (QSCV Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# VAR1 — Voltage Sweep

The **VAR1 — Voltage Sweep** card sets the DC voltage staircase that QSCV walks
through, and the small window used to measure capacitance at each step. The sweep
source is always an SMU forcing voltage; the **Assigned:** line shows which
channel that is, and the value fields adapt to it.

## Controls

| Control | What it does |
|---------|--------------|
| **Mode** | A **SINGLE** sweep (start → stop) or a **DOUBLE** sweep (start → stop → start). |
| **Start** | The first voltage of the sweep. |
| **Stop** | The last voltage of the sweep. |
| **Step** | The voltage increment between steps. It cannot be zero, and its sign sets the direction (a negative step sweeps downward). |
| **QSCV Meas Voltage** | The width of the small voltage window used to measure capacitance at each step. It must be greater than **0**, at most **10 V**, and no larger than **\\|Step\\|** — the window has to fit within one step. |
| **Compliance** | The current limit the voltage source will not exceed. |

## Behaviour to know

- **No Spacing or Power Compliance.** Unlike a sweep-mode VAR1, the QSCV sweep is
  always linear and the source is always an SMU forcing voltage, so there is no
  spacing choice and no power-compliance row.
- **Start and Stop are not measured.** Capacitance is recorded only at the steps
  *between* Start and Stop.
- **Live step count.** The number of steps is worked out from Start, Stop, and
  Step (with the two end points excluded) and shown in the header status line when
  the configuration is valid; it must land between **1 and 1001**.
- **Fields follow the assigned channel.** Each value editor enforces the valid
  range for the channel and whether the interlock is open, and flags entries that
  fall outside it.
- **Timing lives elsewhere.** Delay, hold time, and the sweep-stop behaviour are
  set in the separate **QSCV Timing** card, not here.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Quasi-static C-V Measurements ▸ Measurement Functions.
""".strip()
