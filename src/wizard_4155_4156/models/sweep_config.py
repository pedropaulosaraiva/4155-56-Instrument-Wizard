"""
models/sweep_config.py
-----------------------
Domain model for the Sweep measurement configuration.

Layer contract
--------------
- No Qt imports.
- All enum values are SCPI-legal strings (sent verbatim to the instrument).
- SweepConstraints encodes every 4155/56 hardware limit as a static pure
  function; the presenter calls these before mutating state and before
  building the JSON output.

4155/56 limits (documented in HP 4155/4156 User's Guide)
---------------------------------------------------------
Short integration time : 80 µs – 2 ms
Long integration cycles: 1 – 100 NPLC
Timing (wait/delay/hold): 0 – 65.535 s
Voltage sweep range    : ±210 V
Current sweep range    : ±100 mA  (±0.1 A)
Compliance (I)         : 1 pA – 100 mA
Compliance (V)         : 1 mV – 210 V
Power compliance       : 0 – 2 W
VAR1 / VAR2 points     : 1 – 1001
VARD ratio             : any real; typical UI bounds ±1000
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ── Enumerations ──────────────────────────────────────────────────────────────


class IntegrationMode(str, Enum):
    SHORT = "SHORT"
    MED = "MED"
    LONG = "LONG"


class SweepStop(str, Enum):
    COMPLIANCE = "COMPLIANCE"
    END = "END"


class VAR1Mode(str, Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"


class SweepSpacing(str, Enum):
    LINEAR = "LINEAR"
    L10 = "L10"
    L25 = "L25"
    L50 = "L50"


# ── Hardware limit constants ──────────────────────────────────────────────────

# Timing
SHORT_TIME_MIN: float = 8e-5  # 80 µs
SHORT_TIME_MAX: float = 2e-3  # 2 ms
LONG_CYCLES_MIN: int = 1
LONG_CYCLES_MAX: int = 100
TIMING_MIN: float = 0.0
TIMING_MAX: float = 65.535  # seconds

# Sweep source values
VOLTAGE_MIN: float = -210.0
VOLTAGE_MAX: float = 210.0
CURRENT_MIN: float = -0.1  # A
CURRENT_MAX: float = 0.1  # A

# Compliance
COMP_I_MIN: float = 1e-12  # 1 pA
COMP_I_MAX: float = 0.1  # 100 mA
COMP_V_MIN: float = 0.001  # 1 mV
COMP_V_MAX: float = 210.0

# Power compliance
PCOMP_MIN: float = 0.0
PCOMP_MAX: float = 2.0  # W

# Point counts
POINTS_MIN: int = 1
POINTS_MAX: int = 1001

# VARD ratio
RATIO_MIN: float = -1000.0
RATIO_MAX: float = 1000.0


# ── Per-section dataclasses ───────────────────────────────────────────────────


@dataclass
class MeasurementSetup:
    integration_mode: IntegrationMode = IntegrationMode.MED
    short_time: float = 2e-4  # s  — used only when SHORT
    long_time_cycles: int = 50  # NPLC — used only when LONG
    wait_time: float = 1.0  # s


@dataclass
class VAR1Config:
    mode: VAR1Mode = VAR1Mode.SINGLE
    spacing: SweepSpacing = SweepSpacing.LINEAR
    start: float = 0.0
    stop: float = 1.0
    step: float = 0.1
    compliance: float = 0.01
    power_compliance: float = 0.01


@dataclass
class VAR2Config:
    start: float = 0.0
    step: float = 0.1
    points: int = 3
    compliance: float = 0.01
    power_compliance: float = 0.01


@dataclass
class VARDConfig:
    """
    VAR1-derivative channel.  Output = VAR1_value * ratio + offset.
    """

    offset: float = 0.0
    ratio: float = 1.0
    compliance: float = 0.01
    power_compliance: float = 0.01


@dataclass
class SweepConfig:
    """
    Complete snapshot of the Sweep configuration page.

    channel_standby maps channel-id strings (e.g. "SMU1") to bool standby
    state.  Only SMU channels carry this field; the dict is populated from
    the channel summary section.

    display_vars is the ordered list of variable names chosen for display.
    """

    measurement_setup: MeasurementSetup = field(
        default_factory=MeasurementSetup
    )
    delay: float = 0.0
    hold_time: float = 0.5
    sweep_stop: SweepStop = SweepStop.COMPLIANCE
    var1: VAR1Config = field(default_factory=VAR1Config)
    var2: VAR2Config = field(default_factory=VAR2Config)
    vard: VARDConfig = field(default_factory=VARDConfig)
    channel_standby: Dict[str, bool] = field(default_factory=dict)
    display_vars: List[str] = field(default_factory=list)


# ── Constraint rule-set ───────────────────────────────────────────────────────


class SweepConstraints:
    """
    Static pure-function rule-set for sweep configuration validation.
    All methods return either a validated/clamped value or an error string.
    No Qt, no I/O, no side effects.

    Convention: validate_* returns (value, None) on success or
    (fallback, error_message) on failure.
    """

    # ── Range helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def source_range(is_voltage: bool) -> Tuple[float, float]:
        """Start/Stop/Step limits for the sweep channel."""
        if is_voltage:
            return VOLTAGE_MIN, VOLTAGE_MAX
        return CURRENT_MIN, CURRENT_MAX

    @staticmethod
    def compliance_range(sweep_is_voltage: bool) -> Tuple[float, float]:
        """Compliance range is the *opposite* type to the sweep."""
        if sweep_is_voltage:
            return COMP_I_MIN, COMP_I_MAX  # sweeping V → comply I
        return COMP_V_MIN, COMP_V_MAX  # sweeping I → comply V

    @staticmethod
    def source_unit(is_voltage: bool) -> str:
        return "V" if is_voltage else "A"

    @staticmethod
    def compliance_unit(sweep_is_voltage: bool) -> str:
        return "A" if sweep_is_voltage else "V"

    # ── Individual field validators ───────────────────────────────────────────

    @staticmethod
    def validate_short_time(val: float) -> Tuple[float, Optional[str]]:
        if SHORT_TIME_MIN <= val <= SHORT_TIME_MAX:
            return val, None
        return SHORT_TIME_MIN, (
            f"Short integration time must be {SHORT_TIME_MIN:.0e} – "
            f"{SHORT_TIME_MAX:.0e} s."
        )

    @staticmethod
    def validate_long_cycles(val: int) -> Tuple[int, Optional[str]]:
        if LONG_CYCLES_MIN <= val <= LONG_CYCLES_MAX:
            return val, None
        return LONG_CYCLES_MIN, (
            f"Integration cycles must be {LONG_CYCLES_MIN} – {LONG_CYCLES_MAX}."
        )

    @staticmethod
    def validate_timing(val: float, label: str) -> Tuple[float, Optional[str]]:
        if TIMING_MIN <= val <= TIMING_MAX:
            return val, None
        return TIMING_MIN, (
            f"{label} must be {TIMING_MIN} – {TIMING_MAX:.3f} s."
        )

    @staticmethod
    def validate_source(
        val: float, is_voltage: bool, label: str
    ) -> Tuple[float, Optional[str]]:
        lo, hi = SweepConstraints.source_range(is_voltage)
        if lo <= val <= hi:
            return val, None
        unit = SweepConstraints.source_unit(is_voltage)
        return lo, f"{label} must be {lo} – {hi} {unit}."

    @staticmethod
    def validate_compliance(
        val: float, sweep_is_voltage: bool
    ) -> Tuple[float, Optional[str]]:
        lo, hi = SweepConstraints.compliance_range(sweep_is_voltage)
        if lo <= val <= hi:
            return val, None
        unit = SweepConstraints.compliance_unit(sweep_is_voltage)
        return lo, f"Compliance must be {lo:.2e} – {hi} {unit}."

    @staticmethod
    def validate_pcomp(val: float) -> Tuple[float, Optional[str]]:
        if PCOMP_MIN <= val <= PCOMP_MAX:
            return val, None
        return (
            PCOMP_MIN,
            f"Power compliance must be {PCOMP_MIN} – {PCOMP_MAX} W.",
        )

    @staticmethod
    def validate_points(val: int, label: str) -> Tuple[int, Optional[str]]:
        if POINTS_MIN <= val <= POINTS_MAX:
            return val, None
        return POINTS_MIN, f"{label} must be {POINTS_MIN} – {POINTS_MAX}."

    @staticmethod
    def validate_var1_step_count(
        start: float, stop: float, step: float
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Returns the integer step count if valid, else (None, error_msg).
        Avoids division by zero and enforces 1–1001 range.
        """
        if step == 0:
            return None, "VAR1 step cannot be zero."
        count = round(abs((stop - start) / step)) + 1
        if POINTS_MIN <= count <= POINTS_MAX:
            return count, None
        return None, (
            f"VAR1 step count = {count} (from start/stop/step); "
            f"must be {POINTS_MIN} – {POINTS_MAX}."
        )

    @staticmethod
    def validate_ratio(val: float) -> Tuple[float, Optional[str]]:
        if RATIO_MIN <= val <= RATIO_MAX:
            return val, None
        return 1.0, f"VARD ratio must be {RATIO_MIN} – {RATIO_MAX}."

    # ── Full-config validation ─────────────────────────────────────────────────

    @staticmethod
    def validate_all(
        config: SweepConfig,
        var1_is_voltage: bool,
        var2_is_voltage: bool,
        has_var1: bool,
        has_var2: bool,
        has_vard: bool,
    ) -> Dict[str, str]:
        """
        Run all validators and return {field_key: error_message} for every
        failing field.  An empty dict means the config is fully valid.
        """
        errors: Dict[str, str] = {}
        ms = config.measurement_setup

        _, e = SweepConstraints.validate_short_time(ms.short_time)
        if e:
            errors["short_time"] = e

        _, e = SweepConstraints.validate_long_cycles(ms.long_time_cycles)
        if e:
            errors["long_cycles"] = e

        _, e = SweepConstraints.validate_timing(ms.wait_time, "Wait time")
        if e:
            errors["wait_time"] = e

        _, e = SweepConstraints.validate_timing(config.delay, "Delay")
        if e:
            errors["delay"] = e

        _, e = SweepConstraints.validate_timing(config.hold_time, "Hold time")
        if e:
            errors["hold_time"] = e

        if has_var1:
            v1 = config.var1
            for fld, val in [
                ("var1_start", v1.start),
                ("var1_stop", v1.stop),
                ("var1_step", v1.step),
            ]:
                _, e = SweepConstraints.validate_source(
                    val, var1_is_voltage, fld
                )
                if e:
                    errors[fld] = e
            _, e = SweepConstraints.validate_compliance(
                v1.compliance, var1_is_voltage
            )
            if e:
                errors["var1_compliance"] = e
            _, e = SweepConstraints.validate_pcomp(v1.power_compliance)
            if e:
                errors["var1_pcomp"] = e
            _, e = SweepConstraints.validate_var1_step_count(
                v1.start, v1.stop, v1.step
            )
            if e:
                errors["var1_step_count"] = e

        if has_var2:
            v2 = config.var2
            for fld, val in [("var2_start", v2.start), ("var2_step", v2.step)]:
                _, e = SweepConstraints.validate_source(
                    val, var2_is_voltage, fld
                )
                if e:
                    errors[fld] = e
            _, e = SweepConstraints.validate_points(v2.points, "VAR2 points")
            if e:
                errors["var2_points"] = e
            _, e = SweepConstraints.validate_compliance(
                v2.compliance, var2_is_voltage
            )
            if e:
                errors["var2_compliance"] = e
            _, e = SweepConstraints.validate_pcomp(v2.power_compliance)
            if e:
                errors["var2_pcomp"] = e

        if has_vard:
            vd = config.vard
            _, e = SweepConstraints.validate_ratio(vd.ratio)
            if e:
                errors["vard_ratio"] = e
            _, e = SweepConstraints.validate_source(
                vd.offset, var1_is_voltage, "VARD offset"
            )
            if e:
                errors["vard_offset"] = e
            _, e = SweepConstraints.validate_compliance(
                vd.compliance, var1_is_voltage
            )
            if e:
                errors["vard_compliance"] = e
            _, e = SweepConstraints.validate_pcomp(vd.power_compliance)
            if e:
                errors["vard_pcomp"] = e

        return errors
