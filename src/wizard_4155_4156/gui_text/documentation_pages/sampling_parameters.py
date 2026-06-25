"""Sampling Parameters documentation page (Sampling Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Sampling Parameters

The **Sampling Parameters** card decides *how often* the instrument takes a
reading, *how many* readings it keeps, and *when* the run ends. It is the heart of
a sampling measurement and the part that most often trips people up. Three ideas
below make everything else fall into place — read them first.

## Idea 1 — the interval is a request, not a promise

The **Initial Interval** is how often the instrument *tries* to take a reading.
But each reading also takes real time to complete: roughly the integration time
plus some measurement overhead, and that cost is paid **once per active
measurement unit**.

- If a reading finishes **well within** the interval, you get exactly one reading
  per interval — the spacing you asked for.
- If a reading takes **longer** than the interval, the instrument cannot keep up.
  It skips triggers, so the readings actually land at the next whole multiple of
  the interval — a coarser spacing than you requested.

So adding measurement units, raising the integration time, or shrinking the
interval can all quietly push you into the second case. (A **measurement unit**
here is an enabled SMU or VMU whose measured variable is ticked in **Display
Variables**.) When the app senses this, it shows an amber timing warning in the
header — see *Behaviour to know* below.

## Idea 2 — the run ends on a completion condition

A sampling run stops the instant **any one completion condition is satisfied**.
This is the thread that connects several controls on this page — and the **Stop
Condition** card beside it — because each of them is really just a different
completion condition. That is why they interact:

- **Total Sampling Time** — a time limit. **Value** ends the run after a set
  duration; **NO LIMIT** removes the time limit; **AUTO** hands the job to the
  sample count instead (see below).
- **Number of Samples** — when **Total Sampling Time = AUTO**, reaching the sample
  budget ends the run. (The logarithmic modes have no Total Sampling Time at all,
  so they always end on the sample count.)
- **Stop Condition** — a separate, value-based completion condition on its own
  card. When it is enabled, whichever completion condition is satisfied first ends
  the run.

If you set **NO LIMIT** with no **Stop Condition**, none of these will ever end
the run on their own — it continues until you stop it by hand.

## Idea 3 — Number of Samples is a budget, and the modes spend it differently

**Number of Samples** is a budget: the instrument never keeps more readings than
that. Whether it ever has to *thin* the budget follows directly from Idea 2:

- With **Total Sampling Time = AUTO**, the run ends the moment the budget is full,
  so nothing is ever thinned.
- With **Value**, **NO LIMIT**, or a pending **Stop Condition**, the run is meant
  to outlast a full budget — so the instrument **throws away some readings it
  already stored** (keeping every other one — "thinning") to make room for new
  ones.

When thinning is needed, the **Mode** decides what happens to the sampling
interval:

| Mode | Sampling interval over the run | What the kept readings look like |
|------|--------------------------------|----------------------------------|
| **LINEAR** | Starts at the Initial Interval and **doubles** each time the budget fills | *Number of Samples* readings spread across the whole run |
| **THIN** (thinned-out) | **Stays** at the Initial Interval for the entire run | *Number of Samples* readings thinned from a constant-rate stream |
| **LOG10 / LOG25 / LOG50** | Constant trigger interval, but only readings on a **logarithmic time grid** are kept (10 / 25 / 50 per decade) | readings evenly spaced on a logarithmic time axis |

### A worked example (LINEAR)

Say **Number of Samples = 10**, the **Initial Interval** is *T*, and a completion
condition keeps the run going (for example, **Total Sampling Time = Value**):

1. The instrument stores 10 readings, one every *T*. The budget is now full.
2. The completion condition has not fired, so it **doubles the interval to 2T**
   and thins the 10 stored readings down to 5 (keeping every other), freeing 5
   slots.
3. It collects 5 more readings at *2T*, refilling the budget to 10.
4. Still running — it doubles again to *4T*, thins back to 5, and continues.

This repeats until the completion condition is met. You always end with 10
readings, now spread across the entire run. **Thinned-out** behaves the same way
*except* it never changes the interval — it keeps sampling at *T* throughout and
only thins what it stores.

## The controls

| Control | What it does |
|---------|--------------|
| **Mode** | Chooses **LINEAR**, **LOG10 / LOG25 / LOG50**, or **THIN** — the behaviour described in the table above. |
| **Initial Interval** | The requested time between readings. Its smallest allowed value depends on the mode (linear reaches the shortest intervals; logarithmic and thinned-out start higher). The field's tooltip shows the exact range for the current mode. |
| **Number of Samples** | The budget of readings to keep. Its maximum depends on the mode: for **linear** and **thinned-out** the cap is divided among the active measurement units, while **LOG10 / LOG25 / LOG50** cap at **111 / 276 / 551** readings. |
| **Total Sampling Time** | The time-limit completion condition (see Idea 2): **AUTO**, **NO LIMIT**, or **Value**. Choose **Value** to type an explicit duration in the field beside it. The row is hidden for the logarithmic modes. |
| **Hold Time** | The wait between the sources starting their output and the first reading. |
| **Filter** | Turns the measurement filter **ON** or **OFF**. |

## Behaviour to know

- **The form adapts to the Mode.** Changing **Mode** recomputes the **Initial
  Interval** minimum, the **Number of Samples** maximum, and which **Total Sampling
  Time** options the drop-down offers.
- **Total Sampling Time = Value** must be at least **Initial Interval × (Number of
  Samples − 1)** — the minimum time needed to collect that many readings.
- **Hold Time can be negative at fast intervals.** When the Initial Interval is
  under 2 ms you may set a negative Hold Time, which starts the readings before the
  source output begins.
- **Fast intervals restrict the rest of the setup.** Below 2 ms the instrument can
  manage only **one** measurement unit, a **fixed** measurement range, and **short**
  integration time, and the **Stop Condition** becomes unavailable. The page flags
  any of these if they are violated.
- **Timing feasibility warning.** If the estimated per-reading time approaches or
  exceeds the Initial Interval (Idea 1), the header shows an **amber warning** that
  the requested interval may not be kept. The measurement still runs, and the
  warning never blocks generating or saving the configuration.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sampling Measurements ▸ Measurement Functions.
""".strip()
