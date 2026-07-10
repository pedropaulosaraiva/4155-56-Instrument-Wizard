"""PULSE — Pulse Source documentation page (Sweep Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# PULSE — Pulse Source

The **PULSE — Pulse Source** card configures the SMU pulse output of a **pulse
sweep measurement**. Instead of holding its programmed level continuously, the
pulsed SMU rests at a **base value** and rises to its programmed level (its sweep
step or constant value) for a short **pulse width**, once every **pulse period**.
Measurements are made **while the peak value is output**, and each step of the
primary sweep is synchronized with one pulse.

The card appears only when one SMU is set to a pulse mode (**VPULSE** or
**IPULSE**) on the **Channels** page; the **Assigned:** line shows which channel
that is. **Only one SMU can be a pulse source** — once a card takes VPULSE/IPULSE,
the pulse options disappear from the other SMU cards (and they are only offered in
Sweep mode to begin with). The pulsed SMU may carry any function: **VAR1**,
**VAR2**, **VAR1'** or **CONST**.

## Controls

| Control | What it does |
|---------|--------------|
| **Pulse Period** | Time between the start of one pulse and the start of the next. Allowed range: **5 ms – 1 s** (resolution 100 µs). |
| **Pulse Width** | Time from when the output starts to leave the base value until it starts to return to it. The measurement happens inside this window. Allowed range: **0.5 ms – 100 ms** (resolution 100 µs). |
| **Base Value** | The output level between pulses. Volts for a VPULSE source, amperes for an IPULSE source; the valid range follows the channel type and the interlock setting, exactly like a sweep Start/Stop value. |

## Behaviour to know

- **Period ⩾ Width + 4 ms.** The instrument needs at least 4 ms after each pulse
  to settle and transfer the reading, so the pulse period must be at least the
  pulse width plus 4 ms. Violations are flagged as a critical.
- **The base value counts as an output value.** It participates in the same checks
  as the sweep values of its channel: it widens the output range used for the
  compliance limits (e.g. a 50 V base caps current compliance at 20 mA even for a
  0–1 V sweep), and it must be representable in that range's output resolution.
- **Delay is ignored.** During a pulse sweep the per-step delay has no effect —
  each step is paced by the pulse period instead. The **Delay** field is hidden
  from the Sweep Timing card and the setting is left out of the generated
  configuration.
- **No power compliance on the pulsed unit.** A pulsed VAR1 or VARD unit cannot
  use power compliance; the row is hidden on its card and the setting is left out
  of the generated configuration.
- **The programmed width is not always honoured.** Unless the setup measures
  exactly **one channel**, with **SHORT** integration and a **FIXED** measurement
  range, the instrument may automatically extend the pulse width to fit the
  measurement. This is allowed, but flagged as an amber warning (see the
  **Warnings** page).
- **Runtime becomes deterministic.** The estimated execution time of a pulse sweep
  is `Hold Time + Pulse Period × total indexes` — a single value rather than a
  range (and a lower bound when the instrument extends the width).

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sweep Measurements ▸ Pulse Sweep Measurement.
""".strip()
