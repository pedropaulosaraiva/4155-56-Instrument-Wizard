"""Warnings documentation page (Setup Status)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Warnings

The **Warnings** column lists **non-blocking** advisories. Unlike a critical, a
warning never stops you from saving or exporting a setup — it is shown in amber to
flag something that is *allowed* but may not behave the way you expect. A setup
with warnings but no criticals still reads *Ready to Save*.

Warnings are raised in **Sampling Mode** (timing feasibility) and in **Sweep
Mode** when a **pulse source** is configured (pulse-width feasibility). Both
concern the same underlying question: can the measurement actually fit inside the
time window you have allotted for it?

## Sweep — pulse width feasibility

A pulse sweep measures **while the pulse peak is output**, so the measurement must
fit inside the programmed **Pulse Width**. The instrument only guarantees that
width when the measurement is as fast as it can be. If the setup does not meet
**all** of the following conditions, the pulse width may be **extended
automatically** to make the measurement possible:

| Condition | Required value |
|-----------|----------------|
| Number of measured channels | exactly **1** (one unit whose measured variable is selected for display) |
| Integration Time | **SHORT** |
| Ranging Mode of the measured channel | **FIXED** |

The warning names each condition that is not met. The setup remains valid and can
be saved and run — but the actual pulse width (and therefore the run time) may be
longer than configured.

**How to clear it:** display the measured variable of only one unit, switch the
integration mode to SHORT, and set the measured channel's range to Fixed in the
**Measurement Ranges** card.

## Sampling — timing feasibility

Sampling asks the instrument to start a new sample once every **Initial
Interval**. But a single measurement takes a finite amount of time — its
*estimated time per sample* (see the **Information** page) — and the instrument
cannot begin the next sample until the current one finishes. When the estimated
time approaches or exceeds the Initial Interval, the instrument cannot keep the
cadence you requested and will silently space the samples further apart.

| Warning | Raised when |
|---------|-------------|
| **Est. time/measurement index  is close to the Initial Interval** | the estimated worst-case measurement time reaches about **75 %** of the Initial Interval — the schedule is tight and small changes may push it over |
| **Est. time/measurement index  exceeds the Initial Interval** | the estimated worst-case measurement time is **at least twice** the Initial Interval — the requested sampling rate cannot be met, and actual samples will be slower than configured |

Because current measurements under AUTO / limited-auto ranging span a range of
possible integration times, the check uses the **worst case** (the slowest
possible measurement), so the warning errs on the side of caution.

**How to clear it:** raise the Initial Interval, shorten the integration time
(e.g. switch to SHORT, or fewer LONG cycles), fix the measurement range instead
of auto-ranging, or reduce the number of measured display variables.

> **Non-pulsed Sweep and QSCV** currently raise no warnings: their timing is
> governed by a per-step Delay and Hold Time rather than a fixed cadence, so
> there is no equivalent feasibility check to fail.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sweep Measurements ▸ Pulse Sweep Measurement; Sampling Measurements ▸ Measurement Functions.
""".strip()
