"""
models/sweep_config.py
-----------------------
Domain model for the Sweep measurement configuration.

Layer contract
--------------
- No Qt imports.
- All enum values are the SCPI-legal strings.
- SweepConstraints is now intentionally LEAN: it only contains
  cross-parameter validation rules (step count, matrix total).
  Per-widget bounds are enforced directly by _SciDoubleEdit in the view
  using the constants exported from this module.

4155/56 corrected hardware limits
----------------------------------
Short integration time : 80 µs (8e-5) – 1.92 ms (1.92e-3)
Long integration cycles: 2 – 100 PLC
Wait-time multiplier   : 0.0 – 10.0 (dimensionless, not seconds)
Hold time              : 0.0 – 655.35 s
Delay time             : 0.0 – 65.535 s
SMU voltage sweep      : ±100 V  |  step 0 – 200 V
SMU current sweep      : ±0.1 A  |  step ±0.2 A
VAR2 / VARD step (V)   : ±200 V
VARD offset (V/I)      : ±200 V / ±0.2 A
VSU voltage            : ±20 V
Compliance (I)         : 1 pA – 0.1 A   (when sweeping V)
Compliance (V)         : 1 mV – 100 V   (when sweeping I)
Power compliance       : 1 mW – 20 W
VAR2 points            : 1 – 128
VAR1 points            : 1 – 1001  (cross-rule)
Total matrix           : VAR1 × VAR2 ≤ 10 001  (cross-rule)
VARD ratio             : ±1000
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ── Enumerations ─────────────────────────────────────────────────────────────


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
    """Log spacings use points-per-decade notation matching 4155/56 SCPI."""

    LINEAR = "LINEAR"
    L10 = "L10"  # 10 points/decade
    L25 = "L25"  # 25 points/decade
    L50 = "L50"  # 50 points/decade


# ── Hardware limit constants (imported by the view for widget bounds) ─────────

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
VOLTAGE_STEP_MIN: float = 0.0  # V — step is always positive for V sweep
VOLTAGE_STEP_MAX: float = 200.0  # V

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

# Power compliance
PCOMP_MIN: float = 1e-3  # 1 mW
PCOMP_MAX: float = 2.0  # W (all power compliances limited to 2W by equipment)

# VARD ratio
RATIO_MIN: float = -1000.0
RATIO_MAX: float = 1000.0

# Point counts
VAR1_POINTS_MIN: int = 1
VAR1_POINTS_MAX: int = 1001
VAR2_POINTS_MIN: int = 1
VAR2_POINTS_MAX: int = 128  # strictly defined in measure_sweep.py
TOTAL_POINTS_MAX: int = 10_001  # VAR1 × VAR2 cross-rule
DISPLAY_VARS_MAX: int = 8


# ── Per-section dataclasses ───────────────────────────────────────────────────


@dataclass
class MeasurementSetup:
    integration_mode: IntegrationMode = IntegrationMode.MED
    short_time: float = 2e-4  # s — only when SHORT
    long_time_cycles: int = 50  # PLC — only when LONG
    wait_multiplier: float = 1.0  # 0.0–10.0, dimensionless


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
    """Output = VAR1_value x ratio + offset."""

    offset: float = 0.0
    ratio: float = 1.0
    compliance: float = 0.01
    power_compliance: float = 0.01


@dataclass
class SweepConfig:
    """Complete snapshot of the Sweep configuration page."""

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
        is_voltage: bool, is_vsu: bool = False
    ) -> Tuple[float, float]:
        if is_vsu:
            return VSU_VOLTAGE_MIN, VSU_VOLTAGE_MAX
        return (
            (VOLTAGE_MIN, VOLTAGE_MAX)
            if is_voltage
            else (CURRENT_MIN, CURRENT_MAX)
        )

    @staticmethod
    def step_range(
        is_voltage: bool,
        is_var2_or_offset: bool = False,
    ) -> Tuple[float, float]:
        """VAR2 step and VARD offset use a wider ±200 V range."""
        if is_voltage:
            if is_var2_or_offset:
                return VAR2_V_STEP_MIN, VAR2_V_STEP_MAX
            return VOLTAGE_STEP_MIN, VOLTAGE_STEP_MAX
        return CURRENT_STEP_MIN, CURRENT_STEP_MAX

    @staticmethod
    def compliance_range(sweep_is_voltage: bool) -> Tuple[float, float]:
        return (
            (COMP_I_MIN, COMP_I_MAX)
            if sweep_is_voltage
            else (COMP_V_MIN, COMP_V_MAX)
        )

    @staticmethod
    def source_unit(is_voltage: bool) -> str:
        return "V" if is_voltage else "A"

    @staticmethod
    def compliance_unit(sweep_is_voltage: bool) -> str:
        return "A" if sweep_is_voltage else "V"

    # ── Cross-parameter computations ──────────────────────────────────────────

    @staticmethod
    def var1_step_count(
        start: float,
        stop: float,
        step: float,
        spacing: str | SweepSpacing = "LINEAR",
    ) -> Optional[int]:
        """Returns point count or None when parameters are invalid."""
        import math

        spacing_val = spacing.value if hasattr(spacing, "value") else spacing
        if spacing_val == "LINEAR":
            if step == 0:
                return None
            return round(abs((stop - start) / step)) + 1
        else:
            if start <= 0 or stop <= start:
                return None
            n_per_decade = 10
            if spacing_val == "L25":
                n_per_decade = 25
            elif spacing_val == "L50":
                n_per_decade = 50
            decades = math.log10(stop / start)
            return round(decades * n_per_decade) + 1

    @staticmethod
    def validate_cross_params(
        var1_count: Optional[int],
        var2_points: int,
        has_var2: bool,
    ) -> Dict[str, str]:
        """
        Returns {rule_key: error_message} for every failing cross-rule.
        Empty dict = fully valid.

        Per-widget bounds are NOT checked here — they are handled
        independently by _SciDoubleEdit widgets in the view.
        """
        errors: Dict[str, str] = {}

        if var1_count is None:
            errors["var1_step_count"] = "VAR1 step cannot be zero."
            return errors

        if not (VAR1_POINTS_MIN <= var1_count <= VAR1_POINTS_MAX):
            errors["var1_step_count"] = (
                f"VAR1: {var1_count} points "
                f"(must be {VAR1_POINTS_MIN}-{VAR1_POINTS_MAX})"
            )
            return errors

        if has_var2:
            total = var1_count * var2_points
            if total > TOTAL_POINTS_MAX:
                errors["total_matrix"] = (
                    f"Matrix {var1_count} x {var2_points} = {total:,} "
                    f"(max {TOTAL_POINTS_MAX:,})"
                )

        return errors
