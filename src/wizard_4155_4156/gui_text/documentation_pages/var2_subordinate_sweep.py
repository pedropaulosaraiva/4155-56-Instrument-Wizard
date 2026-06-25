"""VAR2 — Subordinate Sweep documentation page (Sweep Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# VAR2 — Subordinate Sweep

The **VAR2 — Subordinate Sweep** card configures a *secondary* sweep source that
runs alongside VAR1. For every VAR2 step, the whole VAR1 sweep is repeated: VAR1
runs a full staircase, VAR2 advances one step, VAR1 runs again, and so on. The
result is a family of VAR1 sweeps — one per VAR2 value.

The card only appears when a channel has been given the **VAR2** function on the
**Channels** page. The **Assigned:** line shows which channel that is, and the
card adapts to it — the value fields switch between **volts (V)** and **amperes
(A)**, and the **Compliance** and **Power Compliance** rows are hidden when the
source is a VSU (which has no compliance).

Unlike VAR1, this card has **no Mode or Spacing controls**: the secondary sweep is
always a single, linear staircase, so it only needs a start, a step, and a count.

## Controls

| Control | What it does |
|---------|--------------|
| **Start** | First value of the secondary sweep. |
| **Step** | Increment applied after each complete VAR1 sweep. It cannot be zero, and its sign sets the direction (a negative step decrements VAR2). |
| **Number of steps** | How many secondary steps to run, chosen with the spinner. Allowed range: **1 to 128**. |
| **Compliance** | The limit the source will not exceed (a current limit when sweeping voltage, a voltage limit when sweeping current). Hidden for VSU sources. |
| **Power Compliance** | Optional power limit. The value field is greyed out until you switch on the toggle beside it; while it is off, the setting is left out of the generated configuration. Hidden for VSU sources. |

## Behaviour to know

- **No Stop field.** There is no stop value to enter — the final VAR2 value is
  computed from **Start + Step × Number of steps**. The card checks that this
  derived endpoint still falls within the assigned channel's valid range and flags
  it if it does not.
- **Fields follow the assigned channel.** Each value editor enforces the valid
  range for the current channel (voltage vs. current source, VSU, and whether the
  interlock is open) and flags entries that fall outside it.
- **Counts toward the total.** The number of VAR2 steps multiplies the VAR1 point
  count. When the configuration is valid, the status line at the top of the page
  reports the combined **VAR1 × VAR2** total, which must stay within the overall
  point budget.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sweep Measurements ▸ Measurement Functions.
""".strip()
