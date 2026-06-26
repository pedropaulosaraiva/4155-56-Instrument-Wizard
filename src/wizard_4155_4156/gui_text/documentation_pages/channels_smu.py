"""Source Monitor Units (SMU) documentation page (Channels)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Source Monitor Units (SMU)

A **Source Monitor Unit (SMU)** is a channel that can **source** (force a voltage
or current) and **measure** (read back the other quantity) at the same time. The
instrument has four of them, configured as the **SMU1–SMU4** cards in the
**Source Monitor Units (SMU)** group on the **Channels** page.

## Enabling a unit

Each card has a checkbox in its header. Tick it — or click anywhere on the card —
to include that unit; clearing it marks the card **"(disabled)"** and leaves the
unit out of the measurement.

## The card's settings

| Setting | What it does |
|---------|--------------|
| **Mode** | What the unit does electrically: **V** forces a voltage and measures current; **I** forces a current and measures voltage; **VPULSE** / **IPULSE** do the same with a pulsed output; **COMM** makes the unit the circuit **common** (a 0 V reference) that neither sources nor measures. |
| **Function** | The role the unit plays in the measurement: **CONST** (a constant source) or one of the sweep roles **VAR1 / VAR2 / VAR1'**. The choices offered depend on the current measurement mode, and in **COMM** mode the function is fixed to **CONST**. |
| **V-Name** | The name for this unit's **voltage** variable (up to 6 characters). |
| **I-Name** | The name for this unit's **current** variable (up to 6 characters). |

## What an SMU measures

An SMU always measures the quantity it is **not** forcing — and that measured
variable is the one that flows through to the rest of the app:

- In **V**, **VPULSE**, or **COMM** mode it measures **current** → its **I-Name**.
- In **I** or **IPULSE** mode it measures **voltage** → its **V-Name**.

That measured variable is what you tick in **Display Variables** to record and
plot, what a sampling **Stop Condition** can watch, and what makes the unit count
as an active measurement unit in sampling mode.

## What is set elsewhere

The SMU card defines only the unit's **role and names**. Its other properties are
set on the measurement-configuration page, with the function the SMU performs:

- **Compliance** — the safety limit that caps the output to protect your device
  (a current limit when forcing voltage, a voltage limit when forcing current) — is
  set on the VAR1 / VAR2 / VAR1' cards, or with the constant source.
- **Measurement range** is set in that page's ranges section.

How fine those ranges can go depends on the **instrument model** chosen at the top
of the Channels page: a **4156** provides high-resolution SMUs (reaching the lowest
current ranges, down into the picoamp region), while a **4155** provides
medium-power SMUs (ranges starting higher). This is why the available ranges
change when you switch model.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Measurement Units and Functions ▸ Measurement Units.
""".strip()
