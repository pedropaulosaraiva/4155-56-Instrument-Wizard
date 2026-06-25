"""VARD — Synchronous Sweep documentation page (Sweep Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# VARD — Synchronous Sweep

The **VARD — Synchronous Sweep** card configures a source that sweeps *in step
with* VAR1 instead of running a staircase of its own. At every VAR1 point its
output is derived from the VAR1 value by a fixed scale and shift, as the on-card
note shows:

> **Output = VAR1 × ratio + offset**

Because it simply tracks VAR1, this card has **no Mode, Spacing, Start, Stop, or
Step controls** — it inherits VAR1's sweep shape and output type, and you only set
the ratio and offset that relate the two outputs.

The card only appears when a channel has been given the synchronous-sweep function
on the **Channels** page. The **Assigned:** line shows which channel that is, and
the card adapts to it — the value fields switch between **volts (V)** and
**amperes (A)**, and the **Compliance** and **Power Compliance** rows are hidden
when the source is a VSU (which has no compliance).

## Controls

| Control | What it does |
|---------|--------------|
| **Offset** | The constant added to the scaled VAR1 value. Its units follow the assigned channel. |
| **Ratio** | The factor VAR1 is multiplied by — a dimensionless multiplier (shown with a **×** unit). |
| **Compliance** | The limit the source will not exceed (a current limit for a voltage source, a voltage limit for a current source). Hidden for VSU sources. |
| **Power Compliance** | Optional power limit. The value field is greyed out until you switch on the toggle beside it; while it is off, the setting is left out of the generated configuration. Hidden for VSU sources. |

## Behaviour to know

- **Output is checked across the whole sweep.** The card evaluates
  `VAR1 × ratio + offset` at both ends of VAR1's range and verifies the resulting
  output stays within the assigned channel's valid range — it flags the offset or
  ratio if the synchronous output would run past the channel limits.
- **Fields follow the assigned channel.** Each value editor enforces the valid
  range for the current channel (voltage vs. current source, VSU, and whether the
  interlock is open) and flags entries that fall outside it.
- **Timing lives elsewhere.** Hold time, delay, and the sweep-stop behaviour are
  set in the separate **Sweep Timing** card, not here.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sweep Measurements ▸ Measurement Functions.
""".strip()
