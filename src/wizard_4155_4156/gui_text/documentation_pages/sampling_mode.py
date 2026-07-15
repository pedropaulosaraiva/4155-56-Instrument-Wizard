"""Sampling Mode overview documentation page (Sampling Mode)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Sampling Mode

**Sampling mode** records how a measured value changes **over time** while the
source channels hold a constant bias — unlike sweep mode, which steps a source
through a staircase and measures at each step. Use it to watch a current or
voltage drift, settle, or respond after the bias is applied.

It is the most involved of the measurement modes to set up, mainly because the
timing does not always behave the way it first appears. The sections below explain
the model; the **Sampling Parameters** and **Stop Condition** pages cover the
individual cards in depth.

## How a sampling run works

A run proceeds like this:

1. The source channels start forcing their constant output.
2. The instrument waits the **Hold Time**.
3. It takes the first reading and stores it.
4. It keeps triggering further readings, one every **sampling interval**, storing
   each one as it is taken.
5. It continues until a **completion condition** is reached (see below).

## The catch: requested interval vs. real measurement time

The single biggest source of confusion is that the **interval you ask for is not
always the interval you get**. The interval you set is how often the instrument
*tries* to take a reading, but each reading itself takes real time to complete —
roughly the integration time plus some overhead (such as auto-ranging).

- If the interval is **comfortably longer** than the time a reading takes, you get
  exactly one reading per interval, as configured.
- If the interval is **shorter** than the time a reading takes, the unit cannot
  keep up: it misses triggers, and the readings actually land at a *multiple* of
  the interval — coarser than you asked for.

This is why a configuration can look correct yet still warn you (in amber) that
the requested interval may not be honoured. It is also why the number of active
**measurement units** matters: every extra unit adds to the per-reading time, so
more units make a short interval harder to keep.

## The three sampling modes

Sampling offers three ways of spacing the stored readings — **linear**,
**thinned-out**, and **logarithmic**. They differ in what happens once you have
collected the requested number of readings but the run is not over yet. The
**Sampling Parameters** page explains each one and when to use it.

## How a run ends

A run stops as soon as any one of these happens:

- the **Total Sampling Time** elapses,
- the requested **Number of Samples** is reached,
- a **Stop Condition** you defined becomes true,
- or it is stopped by hand, by an instrument error, or by the safety interlock.

## The Sampling Configuration page

The page is built from a channel configuration — most often by clicking
**Generate Setup Page** on the **Channels** page, but it can also be opened by
copying a previously saved setup. It brings together:

- Sections **common to every measurement mode** — **Channel Summary**,
  **Measurement Setup**, **Measurement Ranges**, **Display Variables**, and
  **Constant Sources**.
- The two sections **specific to sampling** — **Sampling Parameters** and **Stop
  Condition**.

In the **Display Variables** list, sampling mode always offers two extra readings:
**@TIME** (the moment a reading was taken) and **@INDEX** (its sequence number).

## Header and status

*Explanation coming soon.*

> Source: *Agilent 4155C/4156C User's Guide Vol.2* — Sampling Measurements ▸ Measurement Functions.
""".strip()
