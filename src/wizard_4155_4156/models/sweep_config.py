"""
models/sweep_config.py
-----------------------
Domain model for the Sweep measurement configuration.

Layer contract
--------------
- No Qt imports.
- All enum values are the SCPI-legal strings.
- SweepConstraints is now intentionally LEAN: it only contains
  cross-parameter validation rules (step count, total points).
  Per-widget bounds are enforced directly by _SciDoubleEdit in the view
  using the constants exported from this module.

4155/56 corrected hardware limits
----------------------------------
Short integration time : 80 µs (8e-5) – 1.92 ms (1.92e-3)
Long integration cycles: 2 – 100 PLC
Wait-time multiplier   : 0.0 – 10.0 (dimensionless, not seconds)
Hold time              : 0.0 – 655.35 s
Delay time             : 0.0 – 65.535 s
SMU voltage sweep      : ±100 V  |  step ±200 V
SMU current sweep      : ±0.1 A  |  step ±0.2 A
VAR2 / VARD step (V)   : ±200 V
VARD offset (V/I)      : ±200 V / ±0.2 A
VSU voltage            : ±20 V
Compliance (I)         : 1 pA – 0.1 A   (when sweeping V)
Compliance (V)         : 1 mV – 100 V   (when sweeping I)
Interlock open         : SMU voltage ±40 V | step ±80 V | compliance (V) ≤ 40 V
Power compliance       : 1 mW – 20 W
VAR2 number of steps   : 1 – 128
VAR1 points            : 1 – 1001  (cross-rule)
Total points           : measurable vars × indexes ≤ 15 200  (cross-rule)
VARD ratio             : ±1000
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ── Enumerations ─────────────────────────────────────────────────────────────


class IntegrationMode(str, Enum):
    SHORT = "SHORT"
    MED = "MED"
    LONG = "LONG"


class SweepStop(str, Enum):
    """Values match SweepStopModeType in SCPI/literals_definition.py."""

    ABNORMAL = "ABNORMAL"
    COMPLIANCE = "COMPLIANCE"
    OFF = "OFF"


class VAR1Mode(str, Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"


class SweepSpacing(str, Enum):
    """Log spacings use points-per-decade notation matching 4155/56 SCPI."""

    LINEAR = "LINEAR"
    L10 = "L10"  # 10 points/decade
    L25 = "L25"  # 25 points/decade
    L50 = "L50"  # 50 points/decade


# ── Hardware limit constants (view widget bounds) ──────────────────────

# Measurement setup
SHORT_TIME_MIN: float = 8e-5  # 80 µs
SHORT_TIME_MAX: float = 1.92e-3  # 1.92 ms  (NOT 2 ms)
LONG_CYCLES_MIN: int = 2  # PLC  (NOT 1)
LONG_CYCLES_MAX: int = 100
WAIT_MULT_MIN: float = 0.0  # dimensionless multiplier
WAIT_MULT_MAX: float = 10.0

# Timing
HOLD_TIME_MIN: float = 0.0
HOLD_TIME_MAX: float = 655.35  # s  (NOT 65.535)
DELAY_MIN: float = 0.0
DELAY_MAX: float = 65.535  # s

# SMU voltage source
VOLTAGE_MIN: float = -100.0  # V
VOLTAGE_MAX: float = 100.0  # V
VOLTAGE_STEP_MIN: float = -200.0  # V — negative step sweeps downward
VOLTAGE_STEP_MAX: float = 200.0  # V

# Interlock terminal open → SMU output limited to ±40 V
VOLTAGE_ILOCK_MAX: float = 40.0  # V — start/stop/source cap
V_STEP_ILOCK_MAX: float = 80.0  # V — step/offset cap (±2× source range)
COMP_V_ILOCK_MAX: float = 40.0  # V — voltage compliance cap

# SMU current source
CURRENT_MIN: float = -0.1  # A
CURRENT_MAX: float = 0.1  # A
CURRENT_STEP_MIN: float = -0.2  # A — can be negative for I sweep
CURRENT_STEP_MAX: float = 0.2  # A

# VAR2 step & VARD offset (wider range than VAR1 step)
VAR2_V_STEP_MIN: float = -200.0  # V
VAR2_V_STEP_MAX: float = 200.0  # V
VARD_OFFSET_V_MIN: float = -200.0  # V
VARD_OFFSET_V_MAX: float = 200.0  # V
VARD_OFFSET_I_MIN: float = -0.2  # A
VARD_OFFSET_I_MAX: float = 0.2  # A

# VSU — voltage source unit (simpler, single range)
VSU_VOLTAGE_MIN: float = -20.0  # V
VSU_VOLTAGE_MAX: float = 20.0  # V

# Compliance
COMP_I_MIN: float = 1e-12  # 1 pA  (when sweeping V → compliance is I)
COMP_I_MAX: float = 0.1  # 100 mA
COMP_V_MIN: float = 1e-3  # 1 mV  (when sweeping I → compliance is V)
COMP_V_MAX: float = 100.0  # V

# Model-dependent current-compliance minimum (Rule 3).
COMP_I_MIN_MPSMU: float = 1e-12  # 1 pA   (4155 / MPSMU)
COMP_I_MIN_HRSMU: float = 1e-13  # 100 fA (4156 / HRSMU)

# Rule-2: source-current thresholds (A) stepping the voltage-compliance
# ceiling down (each boundary is the 2 W SMU output-power limit).
ICOMP_THRESHOLD_100V: float = 0.02  # |I| ≤ 20 mA → V-comp ≤ 100 V
ICOMP_THRESHOLD_40V: float = 0.05  # |I| ≤ 50 mA → V-comp ≤ 40 V

# Power compliance
PCOMP_MIN: float = 1e-3  # 1 mW
PCOMP_MAX: float = 2.0  # W (all power compliances limited to 2W by equipment)

# VARD ratio
RATIO_MIN: float = -1000.0
RATIO_MAX: float = 1000.0

# SMU pulse source (mode VPULSE/IPULSE) — MEASURE: SWEEP SETUP pulse block.
# Bounds mirror MeasureSweepCommandBuilder (SCPI pulse builders).
PULSE_PERIOD_MIN: float = 5e-3  # 5 ms
PULSE_PERIOD_MAX: float = 1.0  # 1 s
PULSE_WIDTH_MIN: float = 5e-4  # 0.5 ms
PULSE_WIDTH_MAX: float = 0.1  # 100 ms
PULSE_PERIOD_WIDTH_MARGIN: float = 4e-3  # period ≥ width + 4 ms

# Point counts
VAR1_POINTS_MIN: int = 1
VAR1_POINTS_MAX: int = 1001
VAR2_N_OF_STEPS_MIN: int = 1
VAR2_N_OF_STEPS_MAX: int = 128  # strictly defined in measure_sweep.py
TOTAL_POINTS_MAX: int = 15_200  # measurable vars × total indexes (data buffer)
DISPLAY_VARS_MAX: int = 8

# Default measurement range for current-measuring units: limited-auto (LIM)
# capped at 1 nA — the smallest current range common to both the 4155 (MPSMU)
# and 4156 (HRSMU), so it is a valid default for any instrument model.
DEFAULT_LIMITED_CURRENT_RANGE: float = 1e-9  # 1 nA
# Range values for SMU and VMU measurement modes
# 4155 (MPSMU) Current ranges (Current mode)
RANGE_VALUES_MPSMU_CURRENT: Tuple[Tuple[str, float], ...] = (
    ("1 nA", 1e-9),
    ("10 nA", 10e-9),
    ("100 nA", 100e-9),
    ("1 uA", 1e-6),
    ("10 uA", 10e-6),
    ("100 uA", 100e-6),
    ("1 mA", 1e-3),
    ("10 mA", 10e-3),
    ("100 mA", 100e-3),
)

# 4156 (HRSMU) Current ranges (Current mode)
RANGE_VALUES_HRSMU_CURRENT: Tuple[Tuple[str, float], ...] = (
    ("10 pA", 10e-12),
    ("100 pA", 100e-12),
    ("1 nA", 1e-9),
    ("10 nA", 10e-9),
    ("100 nA", 100e-9),
    ("1 uA", 1e-6),
    ("10 uA", 10e-6),
    ("100 uA", 100e-6),
    ("1 mA", 1e-3),
    ("10 mA", 10e-3),
    ("100 mA", 100e-3),
)

# SMU Voltage ranges (Voltage modes)
RANGE_VALUES_SMU_VOLTAGE: Tuple[Tuple[str, float], ...] = (
    ("2 V", 2.0),
    ("20 V", 20.0),
    ("40 V", 40.0),
    ("100 V", 100.0),
)

# VMU Voltage ranges (V mode)
RANGE_VALUES_VMU_V: Tuple[Tuple[str, float], ...] = (
    ("2 V", 2.0),
    ("20 V", 20.0),
)

# VMU DVOL ranges (DVOLT mode)
RANGE_VALUES_VMU_DVOL: Tuple[Tuple[str, float], ...] = (
    ("0.2 V", 0.2),
    ("2 V", 2.0),
)

# Output setting resolution per output range: (range value, resolution).
# The instrument selects the lowest output range covering the max |output|,
# and the sweep step cannot be finer than that range's resolution.
# SMU voltage ranges — identical for HRSMU (4156) and MPSMU (4155).
RESOLUTION_SMU_VOLTAGE: Tuple[Tuple[float, float], ...] = (
    (2.0, 100e-6),
    (20.0, 1e-3),
    (40.0, 2e-3),
    (100.0, 5e-3),
)
# HRSMU (4156) current ranges.
RESOLUTION_HRSMU_CURRENT: Tuple[Tuple[float, float], ...] = (
    (10e-12, 10e-15),
    (100e-12, 10e-15),
    (1e-9, 100e-15),
    (10e-9, 1e-12),
    (100e-9, 10e-12),
    (1e-6, 100e-12),
    (10e-6, 1e-9),
    (100e-6, 10e-9),
    (1e-3, 100e-9),
    (10e-3, 1e-6),
    (100e-3, 10e-6),
)
# MPSMU (4155) current ranges — no 10 pA / 100 pA ranges.
RESOLUTION_MPSMU_CURRENT: Tuple[Tuple[float, float], ...] = (
    RESOLUTION_HRSMU_CURRENT[2:]
)
# VSU: single ±20 V output range.
VSU_OUTPUT_RESOLUTION: float = 1e-3  # 1 mV


# ── Per-section dataclasses ─────────────────────────────────────────────


@dataclass
class MeasurementSetup:
    integration_mode: IntegrationMode = IntegrationMode.MED
    short_time: float = 2e-4  # s — only when SHORT
    long_time_cycles: int = 50  # PLC — only when LONG
    wait_multiplier: float = 1.0  # 0.0–10.0, dimensionless
    ranges: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class VAR1Config:
    mode: VAR1Mode = VAR1Mode.SINGLE
    spacing: SweepSpacing = SweepSpacing.LINEAR
    start: float = 0.0
    stop: float = 1.0
    step: float = 0.1
    compliance: float = 0.01
    power_compliance: float = 0.01
    power_compliance_enabled: bool = False


@dataclass
class VAR2Config:
    start: float = 0.0
    step: float = 0.1
    n_of_steps: int = 1
    compliance: float = 0.01
    power_compliance: float = 0.01
    power_compliance_enabled: bool = False


@dataclass
class VARDConfig:
    """Output = VAR1_value x ratio + offset."""

    offset: float = 0.0
    ratio: float = 1.0
    compliance: float = 0.01
    power_compliance: float = 0.01
    power_compliance_enabled: bool = False


@dataclass
class PulseConfig:
    """SMU pulse-source parameters (mode VPULSE/IPULSE, sweep mode only)."""

    period: float = 10e-3  # s — 5 ms – 1 s
    width: float = 1e-3  # s — 0.5 ms – 100 ms
    base: float = 0.0  # V or A, per the pulsed channel's mode


@dataclass
class SweepConfig:
    """Complete snapshot of the Sweep configuration page."""

    measurement_setup: MeasurementSetup = field(
        default_factory=MeasurementSetup
    )
    delay: float = 0.0
    hold_time: float = 0.0
    sweep_stop: SweepStop = SweepStop.OFF
    var1: VAR1Config = field(default_factory=VAR1Config)
    var2: VAR2Config = field(default_factory=VAR2Config)
    vard: VARDConfig = field(default_factory=VARDConfig)
    pulse: PulseConfig = field(default_factory=PulseConfig)
    channel_standby: Dict[str, bool] = field(default_factory=dict)
    display_vars: List[str] = field(default_factory=list)
    constants: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class SweepUnitFlags:
    """Boolean flags describing which unit types are active."""

    has_var1: bool = False
    has_var2: bool = False
    has_vard: bool = False
    var1_is_voltage: bool = True
    var1_is_vsu: bool = False
    var2_is_voltage: bool = True
    var2_is_vsu: bool = False
    vard_is_vsu: bool = False


# ── Shared validation helpers ────────────────────────────────────────────────


def measured_variable(channel: Dict[str, Any]) -> Optional[str]:
    """
    Variable actually measured by a channel context dict, or None for
    source-only units.  An SMU forcing V/VPULSE (or acting as a COMM return)
    measures current; an SMU forcing I/IPULSE measures voltage; a VMU
    measures its voltage.  VSUs are source-only and measure nothing.
    """
    unit_type = channel.get("unit_type")
    if unit_type == "VMU":
        return channel.get("v_name") or None
    if unit_type == "SMU":
        if channel.get("mode") in ("I", "IPULSE"):
            return channel.get("v_name") or None
        return channel.get("i_name") or None
    return None


def count_measured_units(
    active_channels: List[dict],
    display_vars: List[str],
    *,
    dvol_weight: int = 1,
) -> int:
    """
    Number of measuring units whose measured variable is selected for display.

    A VMU in differential (DVOLT) mode contributes ``dvol_weight``: use 2 for
    time estimation (the differential measures both VMUs, doubling integration
    time) and 1 for the data buffer / validation (it stores a single value).
    The dvol secondary is absent from ``active_channels`` (see the config
    presenters), so only the primary is ever weighted.
    """
    selected = set(display_vars)
    count = 0
    for ch in active_channels or []:
        measured = measured_variable(ch)
        if measured is None or measured not in selected:
            continue
        if ch.get("unit_type") == "VMU" and ch.get("mode") == "DVOLT":
            count += dvol_weight
        else:
            count += 1
    return count


def _is_4156(instrument_model: str) -> bool:
    """HRSMU (4156) vs MPSMU (4155); mirrors the RangeRow convention."""
    return "56" in (instrument_model or "")


def current_ranges_for(
    instrument_model: str,
) -> Tuple[Tuple[str, float], ...]:
    """SMU current measurement ranges available on the instrument."""
    return (
        RANGE_VALUES_HRSMU_CURRENT
        if _is_4156(instrument_model)
        else RANGE_VALUES_MPSMU_CURRENT
    )


def smallest_range_at_least(
    value: float, ranges: Tuple[Tuple[str, float], ...]
) -> Optional[float]:
    """Smallest standard range value ≥ |value|; None if it exceeds all."""
    target = abs(value)
    for _label, r_val in ranges:
        if r_val >= target:
            return r_val
    return None


PULSE_SMU_MODES: Tuple[str, ...] = ("VPULSE", "IPULSE")


def pulsed_channel(active_channels: List[dict]) -> Optional[Dict[str, Any]]:
    """
    The single enabled SMU acting as pulse source, or None.

    Only one SMU may be a pulse source (enforced on the Channels page);
    defensively returns None when more than one slips through.
    """
    pulsed = [
        ch
        for ch in active_channels or []
        if ch.get("unit_type") == "SMU" and ch.get("mode") in PULSE_SMU_MODES
    ]
    return pulsed[0] if len(pulsed) == 1 else None


def output_range_resolution(
    is_voltage: bool,
    is_vsu: bool,
    instrument_model: str,
    max_magnitude: float,
) -> Tuple[float, float]:
    """
    ``(output range, output resolution)`` of the lowest output range that
    covers ``max_magnitude``; clamps to the largest range when the magnitude
    exceeds every range.
    """
    if is_vsu:
        return VSU_VOLTAGE_MAX, VSU_OUTPUT_RESOLUTION
    if is_voltage:
        table = RESOLUTION_SMU_VOLTAGE
    else:
        table = (
            RESOLUTION_HRSMU_CURRENT
            if _is_4156(instrument_model)
            else RESOLUTION_MPSMU_CURRENT
        )
    mag = abs(max_magnitude)
    for r_val, res in table:
        if r_val >= mag:
            return r_val, res
    return table[-1]


def default_range_config(channel: Dict[str, Any]) -> Dict[str, Any]:
    """Initial measurement-range entry for a freshly added measurement unit.

    An SMU measuring current (any mode except I / IPULSE) starts in
    "Automatic with limitation" (LIM) capped at 1 nA.  Voltage-measuring
    units (an SMU forcing I, or any VMU) start in plain AUTO, since 1 nA is
    not a voltage range.
    """
    if channel.get("unit_type") == "SMU" and channel.get("mode") not in (
        "I",
        "IPULSE",
    ):
        return {"mode": "LIM", "value": DEFAULT_LIMITED_CURRENT_RANGE}
    return {"mode": "AUTO"}


# Rule-3 table: current-compliance ceiling (A) per voltage output range (V).
_ICOMP_MAX_BY_V_RANGE: Dict[float, float] = {
    2.0: 0.1,  # 100 mA
    20.0: 0.1,  # 100 mA
    40.0: 0.05,  # 50 mA
    100.0: 0.02,  # 20 mA
}


def current_compliance_bounds(
    instrument_model: str,
    source_v_magnitude: float,
    interlock_open: bool = False,
) -> Tuple[float, float]:
    """
    Allowed current-compliance range when an SMU sources voltage (Rule 3).

    The lower bound is model-dependent (HRSMU 100 fA, MPSMU 1 pA); the upper
    bound is set by the voltage *output range* — the smallest standard range
    that covers the source magnitude.  Interlock-open caps the source at 40 V.
    """
    lo = COMP_I_MIN_HRSMU if _is_4156(instrument_model) else COMP_I_MIN_MPSMU
    mag = abs(source_v_magnitude)
    if interlock_open:
        mag = min(mag, VOLTAGE_ILOCK_MAX)
    v_range = smallest_range_at_least(mag, RANGE_VALUES_SMU_VOLTAGE)
    if v_range is None:
        v_range = RANGE_VALUES_SMU_VOLTAGE[-1][1]  # cap at the largest (100 V)
    return lo, _ICOMP_MAX_BY_V_RANGE[v_range]


def voltage_compliance_bounds(
    source_i_magnitude: float,
    interlock_open: bool = False,
) -> Tuple[float, float]:
    """
    Allowed voltage-compliance range when an SMU sources current (Rule 2).

    The ceiling depends on the source-current magnitude (the 100 mA output
    range sub-divides by |I|); interlock-open further caps it at 40 V.
    """
    i = abs(source_i_magnitude)
    if i <= ICOMP_THRESHOLD_100V:
        hi = COMP_V_MAX
    elif i <= ICOMP_THRESHOLD_40V:
        hi = 40.0
    else:
        hi = 20.0
    if interlock_open:
        hi = min(hi, COMP_V_ILOCK_MAX)
    return COMP_V_MIN, hi


def validate_display_vars(
    display_vars: List[str],
    measurement_vars: List[str],
    *,
    min_total: int = 2,
    max_total: int = DISPLAY_VARS_MAX,
) -> List[str]:
    """
    Shared Display-Variables cross-validation (Rule 1 + the display-var cap).

    Errors when: fewer than ``min_total`` variables are selected; no selected
    variable is a measurement variable; or more than ``max_total`` selected.
    """
    errors: List[str] = []
    selected = list(display_vars)
    if len(selected) < min_total:
        errors.append(
            f"Select at least {min_total} display variables "
            f"({len(selected)} selected)."
        )
    measurement_set = set(measurement_vars)
    if not any(name in measurement_set for name in selected):
        errors.append(
            "Select at least one measurement variable in Display Variables."
        )
    if len(selected) > max_total:
        errors.append(
            "Too many display variables selected: "
            f"{len(selected)} (maximum is {max_total})."
        )
    return errors


def validate_range_vs_compliance(
    active_channels: List[dict],
    ranges: Dict[str, Dict[str, Any]],
    compliance_by_unit: Dict[str, float],
    instrument_model: str,
) -> List[str]:
    """
    Rule 4: a FIXED / LIMITED-AUTO measurement range may not exceed the lowest
    standard range that covers the unit's configured compliance.

    SMU forcing V/VPULSE measures current (current ranges); SMU forcing
    I/IPULSE measures voltage (voltage ranges).  COMM SMUs have a fixed
    105 mA compliance covered by no range ⇒ any range allowed.  VMUs have no
    compliance ⇒ skipped.
    """
    errors: List[str] = []
    for ch in active_channels or []:
        if ch.get("unit_type") != "SMU":
            continue
        mode = ch.get("mode")
        if mode == "COMM":
            continue
        unit_id = ch["id"]
        r_cfg = ranges.get(unit_id, {})
        if r_cfg.get("mode") not in ("FIX", "LIM"):
            continue
        r_value = r_cfg.get("value")
        compliance = compliance_by_unit.get(unit_id)
        if r_value is None or compliance is None:
            continue
        if mode in ("I", "IPULSE"):
            cov = smallest_range_at_least(compliance, RANGE_VALUES_SMU_VOLTAGE)
            unit = "V"
        else:
            cov = smallest_range_at_least(
                compliance, current_ranges_for(instrument_model)
            )
            unit = "A"
        if cov is None:
            continue  # compliance above all ranges → any range allowed
        if r_value > cov:
            errors.append(
                f"{unit_id} Range: {r_value:.3g} {unit} exceeds the lowest "
                f"range covering its compliance ({cov:.3g} {unit})"
            )
    return errors


def validate_constant_sources(
    constants: Dict[str, Dict[str, float]],
    active_channels: List[dict],
    interlock_open: bool = False,
    instrument_model: str = "4155C",
    pulse_bases: Optional[Dict[str, float]] = None,
) -> List[str]:
    """
    Validate constant-source values and compliances against the hardware
    limits of each active CONST channel.  Shared by SweepConstraints and
    SamplingConstraints (models/sampling_config.py).
    With the interlock terminal open, SMU voltage limits drop to ±40 V.
    Compliance limits depend on the source magnitude and instrument model
    (Rules 2/3).  ``pulse_bases`` maps a pulsed CONST unit's id to its pulse
    base value, which also counts toward the source magnitude.
    """
    errors: List[str] = []
    v_max = VOLTAGE_ILOCK_MAX if interlock_open else VOLTAGE_MAX
    for ch in active_channels or []:
        if not (
            ch.get("function") == "CONST"
            and ch.get("unit_type") in ("SMU", "VSU")
            and ch.get("mode") != "COMM"
        ):
            continue
        unit_id = ch["id"]
        unit_type = ch["unit_type"]
        mode = ch.get("mode")
        c_entry = constants.get(unit_id, {})
        source = c_entry.get("source")

        if source is not None:
            if unit_type == "VSU":
                if not (VSU_VOLTAGE_MIN <= source <= VSU_VOLTAGE_MAX):
                    errors.append(
                        f"{unit_id} Constant Source: invalid "
                        f"value (range: {VSU_VOLTAGE_MIN:.3g}"
                        f" – {VSU_VOLTAGE_MAX:.3g} V)"
                    )
            elif unit_type == "SMU":
                if mode in ("V", "VPULSE"):
                    if not (-v_max <= source <= v_max):
                        errors.append(
                            f"{unit_id} Constant Source: "
                            f"invalid value (range: "
                            f"{-v_max:.3g} – {v_max:.3g} V)"
                        )
                elif mode in ("I", "IPULSE"):
                    if not (CURRENT_MIN <= source <= CURRENT_MAX):
                        errors.append(
                            f"{unit_id} Constant Source: "
                            f"invalid value (range: "
                            f"{CURRENT_MIN:.3g} – {CURRENT_MAX:.3g} A)"
                        )

        if unit_type == "SMU":
            compliance = c_entry.get("compliance")
            if compliance is not None:
                src_mag = abs(source) if source is not None else 0.0
                if pulse_bases:
                    src_mag = max(
                        src_mag, abs(pulse_bases.get(unit_id, 0.0))
                    )
                if mode in ("V", "VPULSE"):
                    c_lo, c_hi = current_compliance_bounds(
                        instrument_model, src_mag, interlock_open
                    )
                    if not (c_lo <= compliance <= c_hi):
                        errors.append(
                            f"{unit_id} Constant Compliance: "
                            f"invalid value (range: "
                            f"{c_lo:.3g} – {c_hi:.3g} A)"
                        )
                elif mode in ("I", "IPULSE"):
                    c_lo, c_hi = voltage_compliance_bounds(
                        src_mag, interlock_open
                    )
                    if not (c_lo <= compliance <= c_hi):
                        errors.append(
                            f"{unit_id} Constant Compliance: "
                            f"invalid value (range: "
                            f"{c_lo:.3g} – {c_hi:.3g} V)"
                        )
    return errors


# ── Constraint rule-set (cross-parameter only) ───────────────────────────────


class SweepConstraints:
    """
    Only cross-parameter validation lives here.
    Per-widget bounds are enforced by _SciDoubleEdit in the view using
    the module-level constants above — no need to duplicate them here.
    """

    # ── Unit helpers (used by presenter to label widgets) ────────────────────

    @staticmethod
    def source_range(
        is_voltage: bool, is_vsu: bool = False, interlock_open: bool = False
    ) -> Tuple[float, float]:
        if is_vsu:
            return VSU_VOLTAGE_MIN, VSU_VOLTAGE_MAX
        if is_voltage:
            if interlock_open:
                return -VOLTAGE_ILOCK_MAX, VOLTAGE_ILOCK_MAX
            return VOLTAGE_MIN, VOLTAGE_MAX
        return CURRENT_MIN, CURRENT_MAX

    @staticmethod
    def step_range(
        is_voltage: bool,
        is_var2_or_offset: bool = False,
        interlock_open: bool = False,
    ) -> Tuple[float, float]:
        """VAR2 step and VARD offset use a wider ±200 V range."""
        if is_voltage:
            if interlock_open:
                return -V_STEP_ILOCK_MAX, V_STEP_ILOCK_MAX
            if is_var2_or_offset:
                return VAR2_V_STEP_MIN, VAR2_V_STEP_MAX
            return VOLTAGE_STEP_MIN, VOLTAGE_STEP_MAX
        return CURRENT_STEP_MIN, CURRENT_STEP_MAX

    @staticmethod
    def compliance_range(
        sweep_is_voltage: bool, interlock_open: bool = False
    ) -> Tuple[float, float]:
        if sweep_is_voltage:
            return COMP_I_MIN, COMP_I_MAX
        return (
            COMP_V_MIN,
            COMP_V_ILOCK_MAX if interlock_open else COMP_V_MAX,
        )

    @staticmethod
    def source_unit(is_voltage: bool) -> str:
        return "V" if is_voltage else "A"

    @staticmethod
    def compliance_unit(sweep_is_voltage: bool) -> str:
        return "A" if sweep_is_voltage else "V"

    # ── Cross-parameter computations ────────────────────────────────────

    @staticmethod
    def var1_step_count(
        start: float,
        stop: float,
        step: float,
        spacing: str | SweepSpacing = "LINEAR",
    ) -> Optional[int]:
        """Returns point count or None when parameters are invalid."""
        spacing_val = spacing.value if hasattr(spacing, "value") else spacing
        if spacing_val == "LINEAR":
            if step == 0:
                return None
            return round(abs((stop - start) / step)) + 1
        else:
            # Log scaling applies to the magnitude only: start/stop may be
            # negative but must share polarity (cannot cross or touch zero).
            if start == 0 or stop == 0 or (start < 0) != (stop < 0):
                return None
            if stop == start:
                return None
            n_per_decade = 10
            if spacing_val == "L25":
                n_per_decade = 25
            elif spacing_val == "L50":
                n_per_decade = 50
            decades = abs(math.log10(abs(stop) / abs(start)))
            return math.floor(decades * n_per_decade) + 1

    @staticmethod
    def total_indexes(cfg: SweepConfig, has_var2: bool) -> Optional[int]:
        """Total measurement indexes: VAR1 points × (2 if double) × VAR2 steps.

        A measurement *index* is one swept point (one stored value per
        measured variable).  VAR2 contributes ``n_of_steps`` when a VAR2 unit
        is present, otherwise 1.  Returns None when the VAR1 sweep is invalid.
        """
        v1 = cfg.var1
        step = v1.step if v1.spacing == SweepSpacing.LINEAR else 0.0
        points = SweepConstraints.var1_step_count(
            v1.start, v1.stop, step, v1.spacing
        )
        if points is None:
            return None
        double = 2 if v1.mode == VAR1Mode.DOUBLE else 1
        var2_steps = cfg.var2.n_of_steps if has_var2 else 1
        return points * double * var2_steps

    @staticmethod
    def _validate_measurement_setup(
        ms: MeasurementSetup,
    ) -> List[str]:
        errors: List[str] = []
        if not (WAIT_MULT_MIN <= ms.wait_multiplier <= WAIT_MULT_MAX):
            errors.append(
                f"Wait Multiplier: invalid value "
                f"(range: {WAIT_MULT_MIN:.3g} – {WAIT_MULT_MAX:.3g})"
            )
        for unit, r_cfg in ms.ranges.items():
            mode = r_cfg.get("mode")
            if mode in ("LIM", "FIX") and "value" not in r_cfg:
                errors.append(
                    f"Range value for {unit} must be "
                    f"specified when mode is {mode}"
                )
        if ms.integration_mode == IntegrationMode.SHORT:
            if not (SHORT_TIME_MIN <= ms.short_time <= SHORT_TIME_MAX):
                errors.append(
                    f"Short Aperture: invalid value "
                    f"(range: {SHORT_TIME_MIN:.3g}"
                    f" – {SHORT_TIME_MAX:.3g} s)"
                )
        elif ms.integration_mode == IntegrationMode.LONG:
            if not (LONG_CYCLES_MIN <= ms.long_time_cycles <= LONG_CYCLES_MAX):
                errors.append(
                    f"Integration Cycles: invalid value "
                    f"(range: {LONG_CYCLES_MIN}"
                    f" – {LONG_CYCLES_MAX} PLC)"
                )
        return errors

    @staticmethod
    def _validate_timing(
        cfg: SweepConfig, has_pulse: bool = False
    ) -> List[str]:
        """The delay is ignored by the instrument during a pulse sweep
        (each step is paced by the pulse period), so it is not validated
        — nor emitted — when a pulse source is configured."""
        errors: List[str] = []
        if not has_pulse and not (DELAY_MIN <= cfg.delay <= DELAY_MAX):
            errors.append(
                f"Delay: invalid value "
                f"(range: {DELAY_MIN:.3g} – {DELAY_MAX:.3g} s)"
            )
        if not (HOLD_TIME_MIN <= cfg.hold_time <= HOLD_TIME_MAX):
            errors.append(
                f"Hold Time: invalid value "
                f"(range: {HOLD_TIME_MIN:.3g}"
                f" – {HOLD_TIME_MAX:.3g} s)"
            )
        return errors

    @staticmethod
    def _validate_var1(
        cfg: SweepConfig,
        flags: SweepUnitFlags,
        interlock_open: bool,
        instrument_model: str,
        extra_source_magnitude: float = 0.0,
        is_pulsed: bool = False,
    ) -> List[str]:
        """``extra_source_magnitude`` folds a pulse base |value| into the
        source magnitude that gates the compliance bounds.  A pulsed VAR1
        unit has no power compliance (``is_pulsed`` skips its check)."""
        errors: List[str] = []
        v1 = cfg.var1
        src_min, src_max = SweepConstraints.source_range(
            flags.var1_is_voltage, flags.var1_is_vsu, interlock_open
        )
        start_errs = SweepConstraints._validate_source_value(
            "VAR1 Start", v1.start, src_min, src_max
        )
        stop_errs = SweepConstraints._validate_source_value(
            "VAR1 Stop", v1.stop, src_min, src_max
        )
        errors.extend(start_errs)
        errors.extend(stop_errs)
        start_ok = not start_errs
        stop_ok = not stop_errs

        if v1.spacing == SweepSpacing.LINEAR:
            errors.extend(
                SweepConstraints._validate_var1_linear_step(
                    v1,
                    flags,
                    src_min,
                    src_max,
                    interlock_open,
                )
            )
        elif v1.start == 0 or v1.stop == 0:
            errors.append(
                "VAR1: Start and Stop cannot be zero for logarithmic sweeps."
            )
        elif (v1.start < 0) != (v1.stop < 0):
            errors.append(
                "VAR1: Start and Stop must have the same"
                " polarity for logarithmic sweeps."
            )
        elif v1.stop == v1.start:
            errors.append(
                "VAR1: Stop must differ from Start for logarithmic sweeps."
            )

        if not flags.var1_is_vsu:
            if start_ok and stop_ok:
                errors.extend(
                    SweepConstraints._validate_compliance(
                        "VAR1",
                        v1.compliance,
                        flags.var1_is_voltage,
                        max(
                            abs(v1.start),
                            abs(v1.stop),
                            extra_source_magnitude,
                        ),
                        instrument_model,
                        interlock_open,
                    )
                )
            if (
                not is_pulsed
                and v1.power_compliance_enabled
                and not (PCOMP_MIN <= v1.power_compliance <= PCOMP_MAX)
            ):
                errors.append(
                    f"VAR1 Power Compliance: invalid "
                    f"value (range: {PCOMP_MIN:.3g}"
                    f" – {PCOMP_MAX:.3g})"
                )

        return errors

    @staticmethod
    def _validate_source_value(
        label: str, value: float, src_min: float, src_max: float
    ) -> List[str]:
        """Validate one source output value against the channel range."""
        if not (src_min <= value <= src_max):
            return [
                f"{label}: invalid value "
                f"(range: {src_min:.3g} – {src_max:.3g})"
            ]
        return []

    @staticmethod
    def _validate_compliance(
        label: str,
        compliance: float,
        is_voltage_source: bool,
        source_magnitude: float,
        instrument_model: str,
        interlock_open: bool,
    ) -> List[str]:
        """Compliance bounds gated on the source output range (Rules 2/3)."""
        if is_voltage_source:
            comp_min, comp_max = current_compliance_bounds(
                instrument_model, source_magnitude, interlock_open
            )
            unit = "A"
        else:
            comp_min, comp_max = voltage_compliance_bounds(
                source_magnitude, interlock_open
            )
            unit = "V"
        if not (comp_min <= compliance <= comp_max):
            return [
                f"{label} Compliance: invalid value "
                f"(range: {comp_min:.3g} – {comp_max:.3g} {unit})"
            ]
        return []

    @staticmethod
    def _validate_var1_linear_step(
        v1: VAR1Config,
        flags: SweepUnitFlags,
        src_min: float,
        src_max: float,
        interlock_open: bool,
    ) -> List[str]:
        if flags.var1_is_vsu:
            stp_max = abs(src_max - src_min)
            stp_min = -stp_max
        else:
            stp_min, stp_max = SweepConstraints.step_range(
                flags.var1_is_voltage,
                is_var2_or_offset=False,
                interlock_open=interlock_open,
            )
        if v1.step == 0:
            return ["VAR1 Step: cannot be zero"]
        if not (stp_min <= v1.step <= stp_max):
            return [
                f"VAR1 Step: invalid value "
                f"(range: {stp_min:.3g} – {stp_max:.3g})"
            ]
        if v1.step > 0 and v1.stop <= v1.start:
            return [
                "VAR1: Stop must be greater than Start when Step is positive."
            ]
        if v1.step < 0 and v1.stop >= v1.start:
            return [
                "VAR1: Stop must be less than Start when Step is negative."
            ]
        return []

    @staticmethod
    def _validate_point_counts(
        cfg: SweepConfig,
        flags: SweepUnitFlags,
        active_channels: List[dict],
    ) -> List[str]:
        """Check the VAR1 point count and the total measurement points.

        Total points = (measurable display variables) × total indexes and must
        not exceed the instrument data buffer (``TOTAL_POINTS_MAX``).  A DVOL
        VMU counts as one measurable variable (one stored value).
        """
        v1 = cfg.var1
        step_val = v1.step if v1.spacing == SweepSpacing.LINEAR else 0.0
        v1_count = SweepConstraints.var1_step_count(
            v1.start, v1.stop, step_val, v1.spacing
        )
        if v1_count is None or not (
            VAR1_POINTS_MIN <= v1_count <= VAR1_POINTS_MAX
        ):
            return [
                f"VAR1: "
                f"{v1_count if v1_count is not None else 0}"
                f" points (must be "
                f"{VAR1_POINTS_MIN}-{VAR1_POINTS_MAX})"
            ]
        indexes = SweepConstraints.total_indexes(cfg, flags.has_var2)
        n_vars = count_measured_units(
            active_channels or [], cfg.display_vars, dvol_weight=1
        )
        if indexes is not None and n_vars > 0:
            total = n_vars * indexes
            if total > TOTAL_POINTS_MAX:
                return [
                    f"Total points: {n_vars} vars x {indexes} indexes "
                    f"= {total:,} (max {TOTAL_POINTS_MAX:,})"
                ]
        return []

    @staticmethod
    def _validate_var2(
        cfg: SweepConfig,
        flags: SweepUnitFlags,
        interlock_open: bool,
        instrument_model: str,
        extra_source_magnitude: float = 0.0,
    ) -> List[str]:
        errors: List[str] = []
        v2 = cfg.var2
        src_min, src_max = SweepConstraints.source_range(
            flags.var2_is_voltage, flags.var2_is_vsu, interlock_open
        )
        start_errs = SweepConstraints._validate_source_value(
            "VAR2 Start", v2.start, src_min, src_max
        )
        errors.extend(start_errs)
        stp_min, stp_max = SweepConstraints.step_range(
            flags.var2_is_voltage,
            is_var2_or_offset=True,
            interlock_open=interlock_open,
        )
        if v2.step == 0:
            errors.append("VAR2 Step: cannot be zero")
        elif not (stp_min <= v2.step <= stp_max):
            errors.append(
                f"VAR2 Step: invalid value "
                f"(range: {stp_min:.3g} – {stp_max:.3g})"
            )
        n_steps_ok = (
            VAR2_N_OF_STEPS_MIN <= v2.n_of_steps <= VAR2_N_OF_STEPS_MAX
        )
        if not n_steps_ok:
            errors.append(
                f"VAR2 Number of Steps: invalid value "
                f"(range: {VAR2_N_OF_STEPS_MIN}"
                f" – {VAR2_N_OF_STEPS_MAX})"
            )
        step_ok = v2.step != 0 and stp_min <= v2.step <= stp_max

        # The last swept value is Start + Step × (Number of Steps − 1),
        # since Number of Steps is the point count (first point is Start).
        # Like VAR1 Stop / VARD Output it must stay within the channel source
        # range; only meaningful once Step and Number of Steps are valid.
        if step_ok and n_steps_ok:
            last = v2.start + (v2.n_of_steps - 1) * v2.step
            errors.extend(
                SweepConstraints._validate_source_value(
                    "VAR2 Last Value", last, src_min, src_max
                )
            )
            if not flags.var2_is_vsu and not start_errs:
                errors.extend(
                    SweepConstraints._validate_compliance(
                        "VAR2",
                        v2.compliance,
                        flags.var2_is_voltage,
                        max(
                            abs(v2.start),
                            abs(last),
                            extra_source_magnitude,
                        ),
                        instrument_model,
                        interlock_open,
                    )
                )

        if (
            not flags.var2_is_vsu
            and v2.power_compliance_enabled
            and not (PCOMP_MIN <= v2.power_compliance <= PCOMP_MAX)
        ):
            errors.append(
                f"VAR2 Power Compliance: invalid "
                f"value (range: {PCOMP_MIN:.3g}"
                f" – {PCOMP_MAX:.3g})"
            )
        return errors

    @staticmethod
    def _validate_vard(
        cfg: SweepConfig,
        flags: SweepUnitFlags,
        interlock_open: bool,
        instrument_model: str,
        extra_source_magnitude: float = 0.0,
        is_pulsed: bool = False,
    ) -> List[str]:
        errors: List[str] = []
        vd = cfg.vard
        if flags.var1_is_vsu or flags.var1_is_voltage:
            if interlock_open and not flags.vard_is_vsu:
                off_min = -V_STEP_ILOCK_MAX
                off_max = V_STEP_ILOCK_MAX
            else:
                off_min = VARD_OFFSET_V_MIN
                off_max = VARD_OFFSET_V_MAX
        else:
            off_min, off_max = VARD_OFFSET_I_MIN, VARD_OFFSET_I_MAX
        if not (off_min <= vd.offset <= off_max):
            errors.append(
                f"VARD Offset: invalid value "
                f"(range: {off_min:.3g} – {off_max:.3g})"
            )
        if not (RATIO_MIN <= vd.ratio <= RATIO_MAX):
            errors.append(
                f"VARD Ratio: invalid value "
                f"(range: {RATIO_MIN:.3g} – {RATIO_MAX:.3g})"
            )
        vard_mag = abs(vd.offset)
        output_ok = True
        if flags.has_var1:
            out_a = cfg.var1.start * vd.ratio + vd.offset
            out_b = cfg.var1.stop * vd.ratio + vd.offset
            out_lo = min(out_a, out_b)
            out_hi = max(out_a, out_b)
            vard_mag = max(abs(out_lo), abs(out_hi))
            o_min, o_max = SweepConstraints.source_range(
                flags.var1_is_voltage,
                flags.vard_is_vsu,
                interlock_open,
            )
            if out_lo < o_min or out_hi > o_max:
                output_ok = False
                errors.append(
                    f"VARD Output: VAR1 x Ratio + Offset"
                    f" spans {out_lo:.3g} – {out_hi:.3g} "
                    f"(allowed: {o_min:.3g} – {o_max:.3g})"
                )
        if not flags.vard_is_vsu:
            if output_ok:
                errors.extend(
                    SweepConstraints._validate_compliance(
                        "VARD",
                        vd.compliance,
                        flags.var1_is_voltage or flags.var1_is_vsu,
                        max(vard_mag, extra_source_magnitude),
                        instrument_model,
                        interlock_open,
                    )
                )
            if (
                not is_pulsed
                and vd.power_compliance_enabled
                and not (PCOMP_MIN <= vd.power_compliance <= PCOMP_MAX)
            ):
                errors.append(
                    f"VARD Power Compliance: invalid "
                    f"value (range: {PCOMP_MIN:.3g}"
                    f" – {PCOMP_MAX:.3g})"
                )
        return errors

    @staticmethod
    def _validate_pulse(
        cfg: SweepConfig,
        pulse_is_voltage: bool,
        interlock_open: bool,
    ) -> List[str]:
        """SMU pulse-source rules: period/width/base ranges and the
        period ≥ width + 4 ms hardware timing requirement."""
        errors: List[str] = []
        p = cfg.pulse
        period_ok = PULSE_PERIOD_MIN <= p.period <= PULSE_PERIOD_MAX
        if not period_ok:
            errors.append(
                f"Pulse Period: invalid value "
                f"(range: {PULSE_PERIOD_MIN:.3g}"
                f" – {PULSE_PERIOD_MAX:.3g} s)"
            )
        width_ok = PULSE_WIDTH_MIN <= p.width <= PULSE_WIDTH_MAX
        if not width_ok:
            errors.append(
                f"Pulse Width: invalid value "
                f"(range: {PULSE_WIDTH_MIN:.3g}"
                f" – {PULSE_WIDTH_MAX:.3g} s)"
            )
        if (
            period_ok
            and width_ok
            and p.period < p.width + PULSE_PERIOD_WIDTH_MARGIN
        ):
            errors.append(
                f"Pulse Period must be at least Pulse Width + "
                f"{PULSE_PERIOD_WIDTH_MARGIN:.3g} s"
            )
        src_min, src_max = SweepConstraints.source_range(
            pulse_is_voltage, is_vsu=False, interlock_open=interlock_open
        )
        errors.extend(
            SweepConstraints._validate_source_value(
                "Pulse Base", p.base, src_min, src_max
            )
        )
        return errors

    @staticmethod
    def _pulse_warnings(
        cfg: SweepConfig,
        active_channels: List[dict],
    ) -> List[str]:
        """
        Non-blocking pulse-timing feasibility warning.

        The instrument only guarantees the programmed pulse width when
        exactly one channel is measured, integration time is SHORT and the
        measured channel's ranging is FIXED; otherwise the pulse width may
        be extended automatically.
        """
        ms = cfg.measurement_setup
        n_meas = count_measured_units(
            active_channels or [], cfg.display_vars, dvol_weight=1
        )
        selected = set(cfg.display_vars)
        measured_ids = [
            ch["id"]
            for ch in active_channels or []
            if (measured_variable(ch) or None) in selected
        ]
        ranging_fixed = all(
            ms.ranges.get(uid, {}).get("mode") == "FIX"
            for uid in measured_ids
        )
        if (
            n_meas == 1
            and ms.integration_mode == IntegrationMode.SHORT
            and ranging_fixed
        ):
            return []
        return [
            "Pulse width may be extended automatically by the instrument "
            "— the programmed width is only guaranteed with exactly 1 "
            f"measured channel (now {n_meas}), SHORT integration (now "
            f"{ms.integration_mode.value}) and FIXED ranging on the "
            "measured channel."
        ]

    @staticmethod
    def _validate_output_resolution(
        cfg: SweepConfig,
        flags: SweepUnitFlags,
        instrument_model: str,
        pulse_ch: Optional[Dict[str, Any]],
        prior_errors: List[str],
    ) -> List[str]:
        """
        Every output value and step size must be representable in the
        output range covering the unit's max |output value|: a step below
        the range's resolution cannot advance the sweep, and a nonzero
        value below it cannot be output (zero is always representable).
        The pulse base shares the pulsed unit's output range.  Each check
        runs only when the section has no prior errors; log spacings have
        no user-entered step, and a VARD with ratio 0 is constant.
        """
        errors: List[str] = []
        pulse_fn = pulse_ch.get("function") if pulse_ch else None
        base = cfg.pulse.base

        def clean(prefix: str) -> bool:
            return not any(e.startswith(prefix) for e in prior_errors)

        def check(
            values: List[Tuple[str, float]],
            step_pair: Optional[Tuple[str, float]],
            is_voltage: bool,
            is_vsu: bool,
            extra_mags: Tuple[float, ...] = (),
        ) -> None:
            """``values`` are checked as 0 < |v| < resolution; the range
            is picked from all values plus ``extra_mags``."""
            mags = [abs(v) for _lbl, v in values]
            mags.extend(extra_mags)
            rng, res = output_range_resolution(
                is_voltage, is_vsu, instrument_model, max(mags, default=0.0)
            )
            unit = SweepConstraints.source_unit(is_voltage or is_vsu)

            def below(label: str, magnitude: float) -> str:
                return (
                    f"{label}: {magnitude:.3g} {unit} is below the "
                    f"output resolution {res:.3g} {unit} of the "
                    f"{rng:.3g} {unit} output range"
                )

            for label, value in values:
                if 0 < abs(value) < res:
                    errors.append(below(label, abs(value)))
            if step_pair is not None and abs(step_pair[1]) < res:
                errors.append(below(step_pair[0], abs(step_pair[1])))

        v1 = cfg.var1
        v1_linear = v1.spacing == SweepSpacing.LINEAR
        if flags.has_var1 and clean("VAR1"):
            values = [("VAR1 Start", v1.start), ("VAR1 Stop", v1.stop)]
            if pulse_fn == "VAR1" and clean("Pulse Base"):
                values.append(("Pulse Base", base))
            step_pair = (
                ("VAR1 Step", v1.step)
                if v1_linear and v1.step != 0
                else None
            )
            check(
                values,
                step_pair,
                flags.var1_is_voltage,
                flags.var1_is_vsu,
            )
        v2 = cfg.var2
        if flags.has_var2 and clean("VAR2"):
            values = [("VAR2 Start", v2.start)]
            step_pair = None
            if v2.step != 0:
                last = v2.start + (v2.n_of_steps - 1) * v2.step
                values.append(("VAR2 Last Value", last))
                step_pair = ("VAR2 Step", v2.step)
            if pulse_fn == "VAR2" and clean("Pulse Base"):
                values.append(("Pulse Base", base))
            check(
                values,
                step_pair,
                flags.var2_is_voltage,
                flags.var2_is_vsu,
            )
        vd = cfg.vard
        if (
            flags.has_vard
            and flags.has_var1
            and clean("VARD")
            and clean("VAR1")
        ):
            out_a = v1.start * vd.ratio + vd.offset
            out_b = v1.stop * vd.ratio + vd.offset
            values = []
            if pulse_fn == "VAR1'" and clean("Pulse Base"):
                values.append(("Pulse Base", base))
            step_pair = None
            if v1_linear and v1.step != 0 and vd.ratio != 0:
                step_pair = (
                    "VARD Effective Step (VAR1 Step x Ratio)",
                    v1.step * vd.ratio,
                )
            if values or step_pair:
                check(
                    values,
                    step_pair,
                    flags.var1_is_voltage or flags.var1_is_vsu,
                    flags.vard_is_vsu,
                    extra_mags=(abs(out_a), abs(out_b)),
                )
        if pulse_ch is not None and pulse_fn == "CONST":
            if clean("Pulse Base"):
                entry = cfg.constants.get(pulse_ch["id"], {}) or {}
                src = abs(entry.get("source", 0.0) or 0.0)
                check(
                    [("Pulse Base", base)],
                    None,
                    pulse_ch.get("mode") == "VPULSE",
                    False,
                    extra_mags=(src,),
                )
        return errors

    @staticmethod
    def _compliance_by_unit(
        cfg: SweepConfig, active_channels: List[dict]
    ) -> Dict[str, float]:
        """Map each SMU's id to the compliance governing it (by function)."""
        fn_to_comp = {
            "VAR1": cfg.var1.compliance,
            "VAR2": cfg.var2.compliance,
            "VAR1'": cfg.vard.compliance,
        }
        comp_map: Dict[str, float] = {}
        for ch in active_channels or []:
            if ch.get("unit_type") != "SMU":
                continue
            cid = ch["id"]
            fn = ch.get("function")
            if fn in fn_to_comp:
                comp_map[cid] = fn_to_comp[fn]
            elif fn == "CONST":
                comp = cfg.constants.get(cid, {}).get("compliance")
                if comp is not None:
                    comp_map[cid] = comp
        return comp_map

    @staticmethod
    def validate_config(
        cfg: SweepConfig,
        flags: SweepUnitFlags,
        active_channels: List[dict] = None,
        interlock_open: bool = False,
        instrument_model: str = "4155C",
    ) -> Tuple[List[str], List[str]]:
        """
        Validate the full SweepConfig against hardware constraints.

        Returns ``(errors, warnings)``: errors block JSON generation and
        saving; warnings (pulse-timing feasibility) are informational and
        never block.
        """
        errors: List[str] = []
        pulse_ch = pulsed_channel(active_channels or [])
        pulse_fn = pulse_ch.get("function") if pulse_ch else None
        pulse_base_mag = abs(cfg.pulse.base) if pulse_ch else 0.0
        extras = {
            fn: pulse_base_mag if pulse_fn == fn else 0.0
            for fn in ("VAR1", "VAR2", "VAR1'")
        }

        errors.extend(
            SweepConstraints._validate_measurement_setup(
                cfg.measurement_setup,
            )
        )
        errors.extend(
            SweepConstraints._validate_timing(
                cfg, has_pulse=pulse_ch is not None
            )
        )

        if flags.has_var1:
            errors.extend(
                SweepConstraints._validate_var1(
                    cfg,
                    flags,
                    interlock_open,
                    instrument_model,
                    extras["VAR1"],
                    is_pulsed=pulse_fn == "VAR1",
                )
            )
            if not any(e.startswith("VAR1") for e in errors):
                errors.extend(
                    SweepConstraints._validate_point_counts(
                        cfg,
                        flags,
                        active_channels or [],
                    )
                )

        if flags.has_var2:
            errors.extend(
                SweepConstraints._validate_var2(
                    cfg,
                    flags,
                    interlock_open,
                    instrument_model,
                    extras["VAR2"],
                )
            )
        if flags.has_vard:
            errors.extend(
                SweepConstraints._validate_vard(
                    cfg,
                    flags,
                    interlock_open,
                    instrument_model,
                    extras["VAR1'"],
                    is_pulsed=pulse_fn == "VAR1'",
                )
            )

        # Pulse rules run before the resolution block so an out-of-range
        # base gates (rather than duplicates) its resolution check.
        if pulse_ch is not None:
            errors.extend(
                SweepConstraints._validate_pulse(
                    cfg,
                    pulse_ch.get("mode") == "VPULSE",
                    interlock_open,
                )
            )

        errors.extend(
            SweepConstraints._validate_output_resolution(
                cfg,
                flags,
                instrument_model,
                pulse_ch,
                errors,
            )
        )

        # A pulsed VAR1/VARD unit has no power compliance, so it does not
        # trigger the sweep-stop requirement either.
        any_pcomp = (
            (
                flags.has_var1
                and not flags.var1_is_vsu
                and pulse_fn != "VAR1"
                and cfg.var1.power_compliance_enabled
            )
            or (
                flags.has_var2
                and not flags.var2_is_vsu
                and cfg.var2.power_compliance_enabled
            )
            or (
                flags.has_vard
                and not flags.vard_is_vsu
                and pulse_fn != "VAR1'"
                and cfg.vard.power_compliance_enabled
            )
        )
        if any_pcomp and cfg.sweep_stop == SweepStop.OFF:
            errors.append(
                "Sweep stop must be ABNORMAL or COMPLIANCE"
                " when power compliance is set"
            )

        measurement_vars = [
            measured_variable(ch)
            for ch in (active_channels or [])
            if measured_variable(ch)
        ]
        errors.extend(
            validate_display_vars(cfg.display_vars, measurement_vars)
        )

        pulse_bases = (
            {pulse_ch["id"]: cfg.pulse.base}
            if pulse_ch is not None and pulse_fn == "CONST"
            else None
        )
        errors.extend(
            validate_constant_sources(
                cfg.constants,
                active_channels,
                interlock_open,
                instrument_model,
                pulse_bases=pulse_bases,
            )
        )
        errors.extend(
            validate_range_vs_compliance(
                active_channels or [],
                cfg.measurement_setup.ranges,
                SweepConstraints._compliance_by_unit(cfg, active_channels),
                instrument_model,
            )
        )

        warnings: List[str] = []
        if pulse_ch is not None:
            warnings.extend(
                SweepConstraints._pulse_warnings(cfg, active_channels or [])
            )
        return errors, warnings
