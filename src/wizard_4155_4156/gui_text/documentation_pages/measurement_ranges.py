"""Measurement Ranges documentation page (shared: Sweep + Sampling)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Measurement Ranges

The **Measurement Ranges** card sets, for each measuring channel, the **range** it
uses when it reads back current or voltage — the full-scale window the reading is
taken in. It is shared by the **Sweep** and **Sampling** configuration pages.

The card is a table with **one row per measurement unit** — the SMUs and VMUs that
actually measure. Source-only VSUs do not appear, and if no measuring unit is
active the card shows a short placeholder instead.

Each row has three columns:

- **Unit** — which channel the row belongs to.
- **Range Mode** — how the range is chosen.
- **Range Value** — the specific range, used only by the modes that need one.

## Range Mode

| Mode | What it does |
|------|--------------|
| **Automatic** | The unit chooses the range itself, stepping up or down so each reading sits well inside full scale and resolution stays high. The **Range Value** is not used. |
| **Automatic with limitation** | Like Automatic, but it never ranges *below* the **Range Value** you pick — so it won't drop into the slowest, most sensitive ranges. |
| **Fixed** | The reading is locked to the **Range Value** you pick; no auto-ranging happens. A reading larger than that range overflows. |

The **Range Value** combo is enabled only for **Automatic with limitation** and
**Fixed**. In **Automatic** it is disabled, because the instrument picks the range
for you. (The instrument also has a *Compliance* ranging mode, but it applies only
to knob-sweep measurements, which this application does not use, so the table
offers just the three modes above.)

## What the Range Value offers

The range choices match **what the unit measures**, which follows its Mode (set on
the **Channels** page):

- An SMU forcing **current** (I / IPULSE) measures voltage → **voltage** ranges.
- An SMU forcing **voltage** (or acting as **COMMON**) measures current →
  **current** ranges. A **4156** (high-resolution SMU) reaches the lowest current
  ranges; a **4155** offers fewer.
- A **VMU** offers its voltage or differential-voltage ranges.

## Behaviour to know

- **The trade-off.** Lower ranges resolve small signals more finely; **Fixed**
  ranging is the fastest because the unit never pauses to change range; **Automatic**
  is the safest when the signal size is unknown.
- **Range vs. compliance.** For **Automatic with limitation** and **Fixed**, the
  **Range Value** cannot be larger than the smallest standard range that already
  covers the unit's compliance — the page flags a range that exceeds it.
- **Fast sampling forces Fixed.** In sampling mode with an Initial Interval under
  **2 ms**, every measurement unit must be set to **Fixed**; the page flags any unit
  that is not.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Measurement Units and Functions ▸ Measurement Ranging Mode.
""".strip()
