"""Stop Condition documentation page (Sampling Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Stop Condition

The **Stop Condition** card ends a sampling run **early** when a measured value
meets a condition you define, instead of always waiting for the full sample count
or total time. It is what you use to stop the moment a device breaks down, a
current runs away, or a voltage settles — so you neither waste time nor keep
stressing the device once the interesting event has happened.

It is switched **off by default**. Tick **Enable stop condition** to turn it on;
the fields below stay greyed out until you do. The whole card also needs an
**Initial Interval of at least 2 ms** — at faster intervals the instrument has no
time to evaluate the condition, so the card is disabled and a hint explains why.

## Controls

| Control | What it does |
|---------|--------------|
| **Enable stop condition** | The master on/off switch for the whole card. |
| **Variable Name (Val)** | The measured variable to watch, chosen from the variables currently available for display. |
| **Event** | The comparison that counts as a hit (see below). |
| **Threshold (Th)** | The value the variable is compared against. |
| **Maximum Number of Events** | How many hits to accumulate before stopping (**1 to 200**). |
| **Enable Delay** | A grace period after the run starts before the condition begins to be checked. Its range is **0 to Initial Interval × 32767**, in steps of the Initial Interval. |

## The event types

The **Event** drop-down sets which comparison between the watched value (**Val**)
and the **Threshold** (**Th**) counts as a hit:

| Event | Counts as a hit when… |
|-------|-----------------------|
| **Val > Th** | the value rises above the threshold. |
| **Val < Th** | the value falls below the threshold. |
| **\\|Val\\| > \\|Th\\|** | the *magnitude* of the value exceeds the magnitude of the threshold (either sign). |
| **\\|Val\\| < \\|Th\\|** | the *magnitude* of the value drops below the magnitude of the threshold. |

The absolute-value events are convenient when you care about size regardless of
polarity — for example, stopping when a current magnitude exceeds a limit whether
it flows in or out.

## How it works

On every sample, the watched value (**Val**) is compared with the **Threshold**
(**Th**) using the chosen **Event**. Each time the comparison is true it counts as
one event; when the running count reaches the **Maximum Number of Events**, the run
stops immediately.

Two settings make this robust in practice:

- **Maximum Number of Events** guards against noise. A noisy signal may cross the
  threshold for a single stray sample; requiring several hits before stopping means
  the run ends only on a *sustained* condition, not on one glitch.
- **Enable Delay** ignores the start of the run. Inrush, settling, and other
  start-up transients can momentarily trip the threshold; the delay holds off
  checking until the measurement has settled, so the condition only acts on the
  behaviour you actually care about.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sampling Measurements ▸ Measurement Functions.
""".strip()
