"""Critical Notifications documentation page (Setup Status)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Critical Notifications

The **Critical** column lists **blocking errors** — problems that make the setup
invalid for the hardware. While any critical remains, the setup **cannot be saved
to the project or exported to JSON**, and the status reads *Not Ready*. Clear them
all and the column shows a green "no critical issues".

Criticals come from two layers working together:

1. **Field-level checks.** Any required field left **blank or holding an
   unparseable value** is flagged immediately (e.g. *"VAR1 Start: value is empty
   or invalid"*).
2. **Constraint checks.** Once a field holds a real number, it is validated
   against the 4155C/4156C hardware limits and the cross-parameter rules below.

The exact set of checks depends on the measurement mode.

## Sweep Mode

**Measurement Setup**

| Check | Fails when |
|-------|-----------|
| Wait Multiplier | outside its valid range |
| Measurement range value | a range is set to FIXED / LIMITED but no value is given |
| Short Aperture | (SHORT integration) outside range |
| Integration Cycles | (LONG integration) outside range |

**Timing** — Delay and Hold Time each within range.

**VAR1 / VAR2 / VARD source cards** — only the cards actually in use are checked:

| Check | Applies to |
|-------|-----------|
| Start / Stop within the channel's source range | VAR1, VAR2 |
| Linear Step non-zero and within range, with a direction matching Start→Stop (a positive step needs Stop > Start; a negative step needs Stop < Start) | VAR1 |
| Logarithmic sweep: Start and Stop non-zero, of the same polarity, and different from each other | VAR1 |
| Step non-zero and within range; Number of Steps within range | VAR2 |
| Last swept value — Start + Step × (Steps − 1) — within the source range | VAR2 |
| Offset and Ratio within range | VARD |
| Output = VAR1 × Ratio + Offset stays within the source range | VARD |
| Compliance within the bounds implied by the source magnitude | VAR1, VAR2, VARD |
| Power Compliance within range (when its toggle is on) | VAR1, VAR2, VARD |

**Point counts** (checked once the VAR1 fields are sound):

- **VAR1 points** must be **1–1001**.
- **Total points** = measured variables × total indexes must not exceed the
  instrument's data buffer.

**Cross-parameter & shared checks**

- **Sweep Stop** must be ABNORMAL or COMPLIANCE whenever any Power Compliance is
  enabled.
- **Display Variables**: at least two selected, at least one of them a measured
  variable, and no more than the maximum.
- **Constant Sources**: each constant source value and its compliance within the
  channel's hardware limits.
- **Range vs Compliance**: a FIXED / LIMITED measurement range may not exceed the
  lowest standard range that covers the unit's compliance.

## Sampling Mode

**Measurement Setup** — the same four checks as Sweep (Wait Multiplier, range
value present, Short Aperture, Integration Cycles).

**Sampling Parameters**

| Check | Fails when |
|-------|-----------|
| Initial Interval | outside the range allowed for the sampling mode (linear vs logarithmic) |
| No. of Samples | outside 1 … the per-mode maximum (the maximum shrinks as more units measure) |
| Total Sampling Time | the chosen mode (No-Limit / fixed) is not allowed for this Initial Interval, or a fixed value is out of range |
| Hold Time | outside its range (its minimum depends on the Initial Interval) |

**Stop Condition** (only when enabled)

- Requires an **Initial Interval ≥ 2 ms**.
- Enable Delay within 0 … Initial Interval × 32767.
- Maximum Number of Events within 1–200.
- The watched **Variable Name** must be a variable that is actually measured.

**Fast-sampling rules** (only when Initial Interval < 2 ms)

- Only **one** measurement unit may be selected.
- Every measuring unit's range must be **FIXED**.
- Integration Time must be **SHORT**.

**Shared checks** — Constant Sources, Display Variables, and Range vs Compliance,
exactly as in Sweep.

## QSCV Mode

| Group | Checks |
|-------|--------|
| **Integration times** | Capacitance integration time and Leakage integration time each within their line-frequency-dependent range |
| **Timing** | Delay and Hold Time within range |
| **Names** | Capacitance Name valid (1–6 chars, first a letter). If leak compensation is ON, a valid Leakage Current Name is required; if it is off but a name is typed, that name must still be valid |
| **Measurement Range** | valid for the connected instrument model |
| **Measurement Unit** | DEFAULT, or one of the enabled SMUs |
| **VAR1** | Start / Stop within the source range; Step non-zero and within range, with a direction matching Start→Stop; Compliance within bounds |
| **QSCV Meas Voltage** | 0 < value ≤ 10 V, and ≤ \\|Step\\| |
| **No. of Step** | within range (checked once VAR1 is sound) |
| **Display Variables** | at least two selected, at least one a measured variable (capacitance or leakage) |
| **Constant Sources** | each value and compliance within the channel's limits |

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — hardware limits per measurement mode.
""".strip()
