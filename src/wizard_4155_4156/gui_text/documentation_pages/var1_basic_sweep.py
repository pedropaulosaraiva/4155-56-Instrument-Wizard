"""VAR1 — Basic Sweep documentation page (Sweep Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# VAR1 — Basic Sweep

The **VAR1 — Basic Sweep** card configures the *primary* sweep source of a sweep
measurement — the staircase output that is stepped from a start value to a stop
value while each point is measured.

The **Assigned:** line at the top of the card shows which channel is acting as the
VAR1 source. You pick that channel on the **Channels** page; this card then adapts
to it — the value fields switch between **volts (V)** and **amperes (A)**, and the
**Compliance** and **Power Compliance** rows are hidden when the source is a VSU
(which has no compliance).

## Controls

| Control | What it does |
|---------|--------------|
| **Mode** | Chooses a **SINGLE** sweep (start → stop) or a **DOUBLE** sweep (start → stop → start). |
| **Spacing** | Selects the step spacing: **LINEAR**, or one of the logarithmic spacings **L10 / L25 / L50** (10, 25, or 50 points per decade). Choosing any logarithmic spacing **disables the Step field** — the point count then comes from the decade span instead. |
| **Start** | First value of the sweep. |
| **Stop** | Final value of a single sweep, or the turn-back value of a double sweep. |
| **Step** | Increment between points for a **LINEAR** sweep. It cannot be zero, and its sign sets the sweep direction (a negative step sweeps downward, so Stop must be below Start). Disabled for logarithmic spacings. |
| **Compliance** | The limit the source will not exceed (a current limit when sweeping voltage, a voltage limit when sweeping current). Hidden for VSU sources. |
| **Power Compliance** | Optional power limit. The value field is greyed out until you switch on the toggle beside it; while it is off, the setting is left out of the generated configuration. Hidden for VSU sources. |

## Behaviour to know

- **Fields follow the assigned channel.** Each value editor enforces the valid
  range for the current channel (voltage vs. current source, VSU, and whether the
  interlock is open) and flags entries that fall outside it.
- **Live point count.** When the configuration is valid, the status line at the
  top of the page reports the resulting VAR1 point count. For a linear sweep it
  is derived from Start, Stop, and Step; for a logarithmic sweep, from the decade
  span and the chosen points-per-decade. The count must land between **1 and 1001**
  (and, when a VAR2 sweep is also active, the VAR1 × VAR2 total must stay within
  the overall point budget).
- **Timing lives elsewhere.** Hold time, delay, and the sweep-stop behaviour are
  set in the separate **Sweep Timing** card, not here.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sweep Measurements ▸ Measurement Functions.
""".strip()
