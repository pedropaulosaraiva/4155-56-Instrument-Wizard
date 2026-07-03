"""Setup Status overview documentation page (status card + detail modal)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Setup Status

The **status card** sits at the top of every measurement-config page — **Sweep**,
**Sampling** and **QSCV** — and is a live summary of whether the current setup is
valid and what it will do when it runs. It updates continuously as you edit, so
you never have to guess whether a setup is ready.

Clicking the card opens a detail modal split into three columns. Each column has
an **ⓘ** icon linking to its own documentation page:

| Column | Accent | What it tells you |
|--------|--------|-------------------|
| **Critical** | red | Blocking errors. While any are present the setup **cannot be saved or exported**, and the card reads *Not Ready*. |
| **Warnings** | amber | Non-blocking advisories — things that are allowed but worth checking. They never block saving. |
| **Information** | blue | Live statistics: how many indexes and points the setup produces, and an estimate of its execution time. |

## Card behaviour

- The compact card shows, at a glance, the count of critical and warning items
  plus the current readiness state.
- The **Save Setup** button and the JSON actions (Save / Generate JSON) are
  **disabled while any critical error remains** — clear the Critical column and
  they become available.
- Warnings alone never disable saving: a setup with warnings but no criticals is
  still *Ready to Save*.

> Source: *Agilent 4155C/4156C User's Guide Vol.2*.
""".strip()
