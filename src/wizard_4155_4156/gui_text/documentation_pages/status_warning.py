"""Warnings documentation page (Setup Status)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Warnings

The **Warnings** column lists **non-blocking** advisories. Unlike a critical, a
warning never stops you from saving or exporting a setup — it is shown in amber to
flag something that is *allowed* but may not behave the way you expect. A setup
with warnings but no criticals still reads *Ready to Save*.

Today, warnings are raised **only in Sampling Mode**, and they all concern one
thing: whether each sample can actually be measured within the time you have
allotted for it.

## Sampling — timing feasibility

Sampling asks the instrument to start a new sample once every **Initial
Interval**. But a single measurement takes a finite amount of time — its
*estimated time per sample* (see the **Information** page) — and the instrument
cannot begin the next sample until the current one finishes. When the estimated
time approaches or exceeds the Initial Interval, the instrument cannot keep the
cadence you requested and will silently space the samples further apart.

| Warning | Raised when |
|---------|-------------|
| **Est. time/sample is close to the Initial Interval** | the estimated worst-case measurement time reaches about **75 %** of the Initial Interval — the schedule is tight and small changes may push it over |
| **Est. time/sample exceeds the Initial Interval** | the estimated worst-case measurement time is **at least twice** the Initial Interval — the requested sampling rate cannot be met, and actual samples will be slower than configured |

Because current measurements under AUTO / limited-auto ranging span a range of
possible integration times, the check uses the **worst case** (the slowest
possible measurement), so the warning errs on the side of caution.

**How to clear it:** raise the Initial Interval, shorten the integration time
(e.g. switch to SHORT, or fewer LONG cycles), fix the measurement range instead
of auto-ranging, or reduce the number of measured display variables.

> **Sweep and QSCV** currently raise no warnings: their timing is governed by a
> per-step Delay and Hold Time rather than a fixed cadence, so there is no
> equivalent feasibility check to fail.

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sampling Measurements ▸ Measurement Functions.
""".strip()
