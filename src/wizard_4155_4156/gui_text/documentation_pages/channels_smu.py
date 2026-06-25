"""Source Monitor Units (SMU) documentation page (Channels)."""
# ruff: noqa: E501  — Markdown content lines are intentionally long.

BODY = """
# Source Monitor Units (SMU)

An **SMU (Source Monitor Unit)** can force a constant voltage, constant current,
pulse voltage, or pulse current, and can measure a DC current or DC voltage. Only
**one** SMU can be set as the pulsed source.

An SMU has three operating modes:

- **V source / I monitor** — sources voltage, measures current.
- **I source / V monitor** — sources current, measures voltage.
- **Source common** — the unit acts as the circuit common.

> *Figure 7-2 (Simplified SMU Circuit Diagram):* an output switch selects between
> the **V Source Mode** branch (a voltage source in series with an ammeter) and
> the **I Source Mode** branch (a current source with a voltmeter) toward the
> **SMU FORCE** terminal, referenced to **COMMON**.

## Compliance

Each SMU has a **compliance** feature that limits the output voltage or current
to protect your device:

- When the SMU **forces voltage**, you specify a **current compliance**.
- When the SMU **forces current**, you specify a **voltage compliance**.

For the compliance setting range and resolution, see *"Compliance"* in Chapter 7
of the User's Guide.

## Types of SMU

| Type | Where | Force / measure | Max. output power | Notes | Kelvin |
|------|-------|-----------------|:-----------------:|-------|:------:|
| **HRSMU** (high resolution) | 4156C only — four units | ±100 V or ±100 mA | 2 W | Minimum current measurement range **10 pA** with **1 fA** resolution | Yes |
| **MPSMU** (medium power) | 4155C — four units; 41501A/B option 420/422 — two units | ±100 V or ±100 mA | 2 W | — | — |
| **HPSMU** (high power) | 41501A/B option 410/412 — one unit | ±200 V or ±1 A | 20 W | — | Yes |

---

## HRSMU — High Resolution SMU

### Output voltage ranges (Table 7-1)

| Range | Output value | Output resolution | Current compliance range |
|-------|--------------|:-----------------:|:------------------------:|
| 2 V | 0 ≤ \\|V\\| ≤ 2 V | 100 μV | ±100 mA |
| 20 V | 0 ≤ \\|V\\| ≤ 20 V | 1 mV | ±100 mA |
| 40 V | 0 ≤ \\|V\\| ≤ 40 V | 2 mV | ±50 mA |
| 100 V | 0 ≤ \\|V\\| ≤ 100 V | 5 mV | ±20 mA |

### Measurement voltage values and resolutions (Table 7-2)

| Range | Measurement value | 1 PLC or longer | 640 μs – 1.92 ms | 80 – 560 μs | High-speed sampling |
|-------|-------------------|:---------------:|:----------------:|:-----------:|:-------------------:|
| 2 V | 0 ≤ \\|V\\| ≤ 2.2 V | 2 μV | 20 μV | 200 μV | 2 mV |
| 20 V | 0 ≤ \\|V\\| ≤ 22 V | 20 μV | 200 μV | 2 mV | 20 mV |
| 40 V | 0 ≤ \\|V\\| ≤ 44 V | 40 μV | 400 μV | 4 mV | 40 mV |
| 100 V | 0 ≤ \\|V\\| ≤ 100 V | 100 μV | 1 mV | 10 mV | 100 mV |

### Output current ranges (Table 7-3)

| Range | Output value | Output resolution | Voltage compliance range |
|-------|--------------|:-----------------:|:------------------------:|
| 10 pA | 0 ≤ \\|I\\| ≤ 10 pA | 10 fA | ±100 V |
| 100 pA | 0 ≤ \\|I\\| ≤ 100 pA | 10 fA | ±100 V |
| 1 nA | 0 ≤ \\|I\\| ≤ 1 nA | 100 fA | ±100 V |
| 10 nA | 0 ≤ \\|I\\| ≤ 10 nA | 1 pA | ±100 V |
| 100 nA | 0 ≤ \\|I\\| ≤ 100 nA | 10 pA | ±100 V |
| 1 μA | 0 ≤ \\|I\\| ≤ 1 μA | 100 pA | ±100 V |
| 10 μA | 0 ≤ \\|I\\| ≤ 10 μA | 1 nA | ±100 V |
| 100 μA | 0 ≤ \\|I\\| ≤ 100 μA | 10 nA | ±100 V |
| 1 mA | 0 ≤ \\|I\\| ≤ 1 mA | 100 nA | ±100 V |
| 10 mA | 0 ≤ \\|I\\| ≤ 10 mA | 1 μA | ±100 V |
| 100 mA | 0 ≤ \\|I\\| ≤ 20 mA | 10 μA | ±100 V |
| 100 mA | 20 mA < \\|I\\| ≤ 50 mA | 10 μA | ±40 V |
| 100 mA | 50 mA < \\|I\\| ≤ 100 mA | 10 μA | ±20 V |

### Measurement current values and resolutions (Table 7-4)

| Range | Measurement value | 1 PLC or longer | 640 μs – 1.92 ms | 80 – 560 μs | High-speed sampling |
|-------|-------------------|:---------------:|:----------------:|:-----------:|:-------------------:|
| 10 pA | 0 ≤ \\|I\\| ≤ 10.5 pA | 1 fA | 1 fA | 1 fA | 10 fA |
| 100 pA | 0 ≤ \\|I\\| ≤ 115 pA | 1 fA | 1 fA | 10 fA | 100 fA |
| 1 nA | 0 ≤ \\|I\\| ≤ 1.15 nA | 10 fA | 10 fA | 100 fA | 1 pA |
| 10 nA | 0 ≤ \\|I\\| ≤ 11.5 nA | 10 fA | 100 fA | 1 pA | 10 pA |
| 100 nA | 0 ≤ \\|I\\| ≤ 115 nA | 100 fA | 1 pA | 10 pA | 100 pA |
| 1 μA | 0 ≤ \\|I\\| ≤ 1.15 μA | 1 pA | 10 pA | 100 pA | 1 nA |
| 10 μA | 0 ≤ \\|I\\| ≤ 11.5 μA | 10 pA | 100 pA | 1 nA | 10 nA |
| 100 μA | 0 ≤ \\|I\\| ≤ 115 μA | 100 pA | 1 nA | 10 nA | 100 nA |
| 1 mA | 0 ≤ \\|I\\| ≤ 1.15 mA | 1 nA | 10 nA | 100 nA | 1 μA |
| 10 mA | 0 ≤ \\|I\\| ≤ 11.5 mA | 10 nA | 100 nA | 1 μA | 10 μA |
| 100 mA | 0 ≤ \\|I\\| ≤ 100 mA | 100 nA | 1 μA | 10 μA | 100 μA |

---

## MPSMU — Medium Power SMU

### Output voltage ranges (Table 7-5)

| Range | Output value | Output resolution | Current compliance range |
|-------|--------------|:-----------------:|:------------------------:|
| 2 V | 0 ≤ \\|V\\| ≤ 2 V | 100 μV | ±100 mA |
| 20 V | 0 ≤ \\|V\\| ≤ 20 V | 1 mV | ±100 mA |
| 40 V | 0 ≤ \\|V\\| ≤ 40 V | 2 mV | ±50 mA |
| 100 V | 0 ≤ \\|V\\| ≤ 100 V | 5 mV | ±20 mA |

### Measurement voltage values and resolutions (Table 7-6)

| Range | Measurement value | 1 PLC or longer | 640 μs – 1.92 ms | 80 – 560 μs | High-speed sampling |
|-------|-------------------|:---------------:|:----------------:|:-----------:|:-------------------:|
| 2 V | 0 ≤ \\|V\\| ≤ 2.2 V | 2 μV | 20 μV | 200 μV | 2 mV |
| 20 V | 0 ≤ \\|V\\| ≤ 22 V | 20 μV | 200 μV | 2 mV | 20 mV |
| 40 V | 0 ≤ \\|V\\| ≤ 44 V | 40 μV | 400 μV | 4 mV | 40 mV |
| 100 V | 0 ≤ \\|V\\| ≤ 100 V | 100 μV | 1 mV | 10 mV | 100 mV |

### Output current ranges (Table 7-7)

| Range | Output value | Output resolution | Voltage compliance range |
|-------|--------------|:-----------------:|:------------------------:|
| 1 nA | 0 ≤ \\|I\\| ≤ 1 nA | 100 fA | ±100 V |
| 10 nA | 0 ≤ \\|I\\| ≤ 10 nA | 1 pA | ±100 V |
| 100 nA | 0 ≤ \\|I\\| ≤ 100 nA | 10 pA | ±100 V |
| 1 μA | 0 ≤ \\|I\\| ≤ 1 μA | 100 pA | ±100 V |
| 10 μA | 0 ≤ \\|I\\| ≤ 10 μA | 1 nA | ±100 V |
| 100 μA | 0 ≤ \\|I\\| ≤ 100 μA | 10 nA | ±100 V |
| 1 mA | 0 ≤ \\|I\\| ≤ 1 mA | 100 nA | ±100 V |
| 10 mA | 0 ≤ \\|I\\| ≤ 10 mA | 1 μA | ±100 V |
| 100 mA | 0 ≤ \\|I\\| ≤ 20 mA | 10 μA | ±100 V |
| 100 mA | 20 mA < \\|I\\| ≤ 50 mA | 10 μA | ±40 V |
| 100 mA | 50 mA < \\|I\\| ≤ 100 mA | 10 μA | ±20 V |

### Measurement current values and resolutions (Table 7-8)

| Range | Measurement value | 1 PLC or longer | 640 μs – 1.92 ms | 80 – 560 μs | High-speed sampling |
|-------|-------------------|:---------------:|:----------------:|:-----------:|:-------------------:|
| 1 nA | 0 ≤ \\|I\\| ≤ 1.15 nA | 10 fA | 10 fA | 100 fA | 1 pA |
| 10 nA | 0 ≤ \\|I\\| ≤ 11.5 nA | 10 fA | 100 fA | 1 pA | 10 pA |
| 100 nA | 0 ≤ \\|I\\| ≤ 115 nA | 100 fA | 1 pA | 10 pA | 100 pA |
| 1 μA | 0 ≤ \\|I\\| ≤ 1.15 μA | 1 pA | 10 pA | 100 pA | 1 nA |
| 10 μA | 0 ≤ \\|I\\| ≤ 11.5 μA | 10 pA | 100 pA | 1 nA | 10 nA |
| 100 μA | 0 ≤ \\|I\\| ≤ 115 μA | 100 pA | 1 nA | 10 nA | 100 nA |
| 1 mA | 0 ≤ \\|I\\| ≤ 1.15 mA | 1 nA | 10 nA | 100 nA | 1 μA |
| 10 mA | 0 ≤ \\|I\\| ≤ 11.5 mA | 10 nA | 100 nA | 1 μA | 10 μA |
| 100 mA | 0 ≤ \\|I\\| ≤ 100 mA | 100 nA | 1 μA | 10 μA | 100 μA |

---

> **Notes on the measurement tables**
>
> - The **measurement value** column applies to **auto** or **limited auto** ranging. For **fixed** ranging, the maximum measurement value is the **Range** column value.
> - Measurement resolution depends on the **integration time** setting. For Knob-sweep measurements, use the **80 – 560 μs** column.
> - The **high-speed sampling** column applies to a sampling measurement whose initial interval is set to **480 μs or shorter**.
>
> For the **HPSMU** output and measurement ranges, refer to *"HPSMU — High Power
> SMU"* in Chapter 7 of the User's Guide.

> Source: *Agilent 4155C/4156C User's Guide Vol.2*, Edition 6 — Measurement Units and Functions ▸ Measurement Units.
""".strip()
