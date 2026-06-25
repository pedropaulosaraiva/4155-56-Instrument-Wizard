"""Measurement Ranges documentation page (shared: Sweep + Sampling)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Measurement Ranges

The **measurement range** sets the full-scale value the analyzer uses when it
measures current (on an SMU) or voltage (on a VMU). Choosing the right range is
a trade-off between **resolution**, **measurement speed**, and **safety against
overflow**.

This page is shared by both **Sweep Mode** and **Sampling Mode** — the range
settings behave identically in either measurement mode.

## Range modes

| Mode | Behaviour | Best for |
|------|-----------|----------|
| **Auto** | The instrument picks the lowest range that fits each reading, switching up or down automatically. | General use; unknown or widely varying signal levels. |
| **Fixed** | The reading is locked to the selected range. No auto-ranging occurs. | Fastest, glitch-free sweeps where the signal stays within one range. |
| **Limited** | Auto-ranges, but never goes *below* the selected range. | Avoiding slow low-current ranges while keeping headroom. |

## Choosing a range

- **Resolution** improves on lower ranges: a 10 pA reading resolves far better
  on the 10 nA range than on the 100 mA range.
- **Speed** improves with **Fixed** ranging — auto-ranging costs an extra
  settling step every time the hardware changes range.
- **Overflow** occurs when a reading exceeds the selected full scale on a Fixed
  or Limited range; the value is reported as invalid. Leave headroom above your
  expected maximum.

## Per-unit ranges

The available ranges depend on the unit and the instrument model:

- **HRSMU** (high-resolution SMU) exposes the lowest current ranges
  (down to the 10 pA / 1 pA region) for sensitive measurements.
- **MPSMU** (medium-power SMU) trades the lowest ranges for higher compliance
  current.
- **VMU** voltage ranges follow the differential / grounded measurement mode.

> **Note:** the range value field is only enabled for **Fixed** and **Limited**
> modes. In **Auto** mode the field is disabled because the instrument selects
> the range for you.

## Related topics

- **Measurement Setup** — integration time and averaging.
- **Constant Sources** — compliance limits that bound the measured signal.
""".strip()
