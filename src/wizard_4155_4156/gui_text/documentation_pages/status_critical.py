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

**Timing** — Delay and Hold Time each within range. When a pulse source is
configured the Delay is ignored by the instrument (each step is paced by the
pulse period), so it is hidden and **not checked**.

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
| Compliance within the bounds implied by the source magnitude (for a pulsed unit the **Pulse Base** counts toward that magnitude) | VAR1, VAR2, VARD |
| Power Compliance within range (when its toggle is on; not applicable to a pulsed VAR1/VARD unit — see below) | VAR1, VAR2, VARD |

**PULSE — Pulse Source** (only when one SMU is in VPULSE/IPULSE mode):

| Check | Fails when |
|-------|-----------|
| Pulse Period | outside **5 ms – 1 s** |
| Pulse Width | outside **0.5 ms – 100 ms** |
| Period vs Width | **Pulse Period < Pulse Width + 4 ms** — the instrument needs 4 ms after each pulse to settle and transfer the reading |
| Pulse Base | outside the pulsed channel's source range (volts for VPULSE, amperes for IPULSE, tightened when the interlock is open) |

A pulsed VAR1 or VARD unit has **no power compliance**: the row is hidden, its
value is not validated, and it does not trigger the Sweep Stop rule below.

**Output resolution** (checked once the corresponding card is otherwise sound):

Every output value must be representable in the **output range** the instrument
selects — the lowest standard range covering the unit's largest output magnitude
(including the Pulse Base on a pulsed unit). Each range has a finite setting
resolution (e.g. the 40 V range resolves 2 mV; the tables differ between the
4155's MPSMU and the 4156's HRSMU, and a VSU always resolves 1 mV):

- **Step ⩾ resolution** — a finer step cannot advance the sweep. Checked for the
  VAR1 Step, the VAR2 Step, and the VARD *effective* step (VAR1 Step × Ratio).
- **Values ⩾ resolution (or exactly zero)** — a nonzero value smaller than the
  resolution cannot be output. Checked for VAR1 Start/Stop, VAR2 Start and Last
  Value, and the Pulse Base. Example: sweeping 1 mV → 40 V puts the output in
  the 40 V range, whose 2 mV resolution cannot represent the 1 mV start.

**Point counts** (checked once the VAR1 fields are sound):

- **VAR1 points** must be **1–1001**.
- **Total points** = measured variables × total indexes must not exceed the
  instrument's data buffer.

**Cross-parameter & shared checks**

- **Sweep Stop** must be ABNORMAL or COMPLIANCE whenever any Power Compliance is
  enabled (a pulsed VAR1/VARD unit is exempt — its power compliance is ignored).
- **Display Variables**: at least two selected, at least one of them a measured
  variable, and no more than the maximum.
- **Constant Sources**: each constant source value and its compliance within the
  channel's hardware limits (for a pulsed CONST unit the Pulse Base counts toward
  the source magnitude that bounds the compliance).
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
| **Capacitance Meas Voltage** | 0 < value ≤ 10 V, and ≤ \\|Step\\| |
| **No. of Step** | within range (checked once VAR1 is sound) |
| **Output resolution** (checked once VAR1 is otherwise sound) | The output range is the lowest standard range covering max(\\|Start\\|, \\|Stop\\|), and each range has a finite setting resolution (e.g. the 2 V range resolves 100 µV, the 40 V range 2 mV). **Start** and **Stop** must be ⩾ that resolution (or exactly zero); **Step** and **Capacitance Meas Voltage** must be ⩾ **twice** it, because each point outputs a measurement window around the DC bias |
| **Display Variables** | at least two selected, at least one a measured variable (capacitance or leakage) |
| **Constant Sources** | each value and compliance within the channel's limits |

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — hardware limits per measurement mode.
""".strip()
