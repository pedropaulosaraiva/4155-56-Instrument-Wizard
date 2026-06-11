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
Total points           : VAR1 × VAR2 ≤ 10 001  (cross-rule)
VARD ratio             : ±1000
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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


# ── Per-section dataclasses ───────────────────────────────────────────────────


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
    constants: Dict[str, Dict[str, float]] = field(default_factory=dict)


# ── Shared validation helpers ────────────────────────────────────────────────


def validate_constant_sources(
    constants: Dict[str, Dict[str, float]],
    active_channels: List[dict],
) -> List[str]:
    """
    Validate constant-source values and compliances against the hardware
    limits of each active CONST channel.  Shared by SweepConstraints and
    SamplingConstraints (models/sampling_config.py).
    """
    errors: List[str] = []
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
                        f"{unit_id} Constant Source: invalid value (range: {VSU_VOLTAGE_MIN:.3g} – {VSU_VOLTAGE_MAX:.3g} V)"
                    )
            elif unit_type == "SMU":
                if mode in ("V", "VPULSE"):
                    if not (VOLTAGE_MIN <= source <= VOLTAGE_MAX):
                        errors.append(
                            f"{unit_id} Constant Source: invalid value (range: {VOLTAGE_MIN:.3g} – {VOLTAGE_MAX:.3g} V)"
                        )
                elif mode in ("I", "IPULSE"):
                    if not (CURRENT_MIN <= source <= CURRENT_MAX):
                        errors.append(
                            f"{unit_id} Constant Source: invalid value (range: {CURRENT_MIN:.3g} – {CURRENT_MAX:.3g} A)"
                        )

        if unit_type == "SMU":
            compliance = c_entry.get("compliance")
            if compliance is not None:
                if mode in ("V", "VPULSE"):
                    if not (COMP_I_MIN <= compliance <= COMP_I_MAX):
                        errors.append(
                            f"{unit_id} Constant Compliance: invalid value (range: {COMP_I_MIN:.3g} – {COMP_I_MAX:.3g} A)"
                        )
                elif mode in ("I", "IPULSE"):
                    if not (COMP_V_MIN <= compliance <= COMP_V_MAX):
                        errors.append(
                            f"{unit_id} Constant Compliance: invalid value (range: {COMP_V_MIN:.3g} – {COMP_V_MAX:.3g} V)"
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
            return math.floor(decades * n_per_decade) + 1

    @staticmethod
    def validate_config(
        cfg: SweepConfig,
        has_var1: bool,
        has_var2: bool,
        has_vard: bool,
        var1_is_voltage: bool = True,
        var1_is_vsu: bool = False,
        var2_is_voltage: bool = True,
        var2_is_vsu: bool = False,
        active_channels: List[dict] = None,
    ) -> List[str]:
        """
        Runs rigorous logic validation checks on the SweepConfig configuration.
        Returns a list of error message strings. An empty list indicates configuration is valid.
        """
        errors: List[str] = []

        # 1. Measurement Setup
        ms = cfg.measurement_setup
        if not (WAIT_MULT_MIN <= ms.wait_multiplier <= WAIT_MULT_MAX):
            errors.append(
                f"Wait Multiplier: invalid value (range: {WAIT_MULT_MIN:.3g} – {WAIT_MULT_MAX:.3g})"
            )

        # Ranges validation
        for unit, r_cfg in ms.ranges.items():
            mode = r_cfg.get("mode")
            if mode in ("LIM", "FIX") and "value" not in r_cfg:
                errors.append(
                    f"Range value for {unit} must be specified when mode is {mode}"
                )

        if ms.integration_mode == IntegrationMode.SHORT:
            if not (SHORT_TIME_MIN <= ms.short_time <= SHORT_TIME_MAX):
                errors.append(
                    f"Short Aperture: invalid value (range: {SHORT_TIME_MIN:.3g} – {SHORT_TIME_MAX:.3g} s)"
                )
        elif ms.integration_mode == IntegrationMode.LONG:
            if not (LONG_CYCLES_MIN <= ms.long_time_cycles <= LONG_CYCLES_MAX):
                errors.append(
                    f"Integration Cycles: invalid value (range: {LONG_CYCLES_MIN} – {LONG_CYCLES_MAX} PLC)"
                )

        # 2. Sweep Timing
        if not (DELAY_MIN <= cfg.delay <= DELAY_MAX):
            errors.append(
                f"Delay: invalid value (range: {DELAY_MIN:.3g} – {DELAY_MAX:.3g} s)"
            )
        if not (HOLD_TIME_MIN <= cfg.hold_time <= HOLD_TIME_MAX):
            errors.append(
                f"Hold Time: invalid value (range: {HOLD_TIME_MIN:.3g} – {HOLD_TIME_MAX:.3g} s)"
            )

        # Range determination helpers
        def get_src_range(
            is_v: bool, is_vsu_flag: bool
        ) -> Tuple[float, float]:
            if is_vsu_flag:
                return VSU_VOLTAGE_MIN, VSU_VOLTAGE_MAX
            return (
                (VOLTAGE_MIN, VOLTAGE_MAX)
                if is_v
                else (CURRENT_MIN, CURRENT_MAX)
            )

        def get_step_range(
            is_v: bool, is_var2_or_offset: bool
        ) -> Tuple[float, float]:
            if is_v:
                return (
                    (VAR2_V_STEP_MIN, VAR2_V_STEP_MAX)
                    if is_var2_or_offset
                    else (VOLTAGE_STEP_MIN, VOLTAGE_STEP_MAX)
                )
            return (CURRENT_STEP_MIN, CURRENT_STEP_MAX)

        def get_comp_range(is_v: bool) -> Tuple[float, float]:
            return (
                (COMP_I_MIN, COMP_I_MAX) if is_v else (COMP_V_MIN, COMP_V_MAX)
            )

        # 3. VAR1
        if has_var1:
            v1 = cfg.var1
            src_min, src_max = get_src_range(var1_is_voltage, var1_is_vsu)
            if not (src_min <= v1.start <= src_max):
                errors.append(
                    f"VAR1 Start: invalid value (range: {src_min:.3g} – {src_max:.3g})"
                )
            if not (src_min <= v1.stop <= src_max):
                errors.append(
                    f"VAR1 Stop: invalid value (range: {src_min:.3g} – {src_max:.3g})"
                )

            if v1.spacing == SweepSpacing.LINEAR:
                stp_min, stp_max = get_step_range(
                    var1_is_voltage, is_var2_or_offset=False
                )
                if v1.step <= 0:
                    errors.append("VAR1 Step: cannot be zero or negative")
                elif not (stp_min <= v1.step <= stp_max):
                    errors.append(
                        f"VAR1 Step: invalid value (range: {stp_min:.3g} – {stp_max:.3g})"
                    )
            else:
                # Log spacing constraints
                if v1.start <= 0:
                    errors.append(
                        "VAR1: Start must be greater than zero for logarithmic sweeps."
                    )
                if v1.stop <= v1.start:
                    errors.append("VAR1: Stop must be greater than Start.")

            if v1.spacing == SweepSpacing.LINEAR and v1.stop <= v1.start:
                errors.append("VAR1: Stop must be greater than Start.")

            comp_min, comp_max = get_comp_range(var1_is_voltage or var1_is_vsu)
            if not (comp_min <= v1.compliance <= comp_max):
                errors.append(
                    f"VAR1 Compliance: invalid value (range: {comp_min:.3g} – {comp_max:.3g})"
                )
            if not (PCOMP_MIN <= v1.power_compliance <= PCOMP_MAX):
                errors.append(
                    f"VAR1 Power Compliance: invalid value (range: {PCOMP_MIN:.3g} – {PCOMP_MAX:.3g})"
                )

            # Point count & total points checks
            # (only if basic VAR1 parameters are logical)
            has_var1_errs = any(e.startswith("VAR1") for e in errors)
            if not has_var1_errs:
                step_val = (
                    v1.step if v1.spacing == SweepSpacing.LINEAR else 0.0
                )
                v1_count = SweepConstraints.var1_step_count(
                    v1.start, v1.stop, step_val, v1.spacing
                )
                if v1_count is None or not (
                    VAR1_POINTS_MIN <= v1_count <= VAR1_POINTS_MAX
                ):
                    errors.append(
                        f"VAR1: {v1_count if v1_count is not None else 0} points (must be {VAR1_POINTS_MIN}-{VAR1_POINTS_MAX})"
                    )
                elif has_var2:
                    v2 = cfg.var2
                    total = v1_count * v2.points
                    if total > TOTAL_POINTS_MAX:
                        errors.append(
                            f"Total points: {v1_count} x {v2.points} = {total:,} (max {TOTAL_POINTS_MAX:,})"
                        )

        # 4. VAR2
        if has_var2:
            v2 = cfg.var2
            src_min, src_max = get_src_range(var2_is_voltage, var2_is_vsu)
            if not (src_min <= v2.start <= src_max):
                errors.append(
                    f"VAR2 Start: invalid value (range: {src_min:.3g} – {src_max:.3g})"
                )
            stp_min, stp_max = get_step_range(
                var2_is_voltage, is_var2_or_offset=True
            )
            if v2.step == 0:
                errors.append("VAR2 Step: cannot be zero")
            elif not (stp_min <= v2.step <= stp_max):
                errors.append(
                    f"VAR2 Step: invalid value (range: {stp_min:.3g} – {stp_max:.3g})"
                )
            if not (VAR2_POINTS_MIN <= v2.points <= VAR2_POINTS_MAX):
                errors.append(
                    f"VAR2 Points: invalid value (range: {VAR2_POINTS_MIN} – {VAR2_POINTS_MAX})"
                )
            comp_min, comp_max = get_comp_range(var2_is_voltage or var2_is_vsu)
            if not (comp_min <= v2.compliance <= comp_max):
                errors.append(
                    f"VAR2 Compliance: invalid value (range: {comp_min:.3g} – {comp_max:.3g})"
                )
            if not (PCOMP_MIN <= v2.power_compliance <= PCOMP_MAX):
                errors.append(
                    f"VAR2 Power Compliance: invalid value (range: {PCOMP_MIN:.3g} – {PCOMP_MAX:.3g})"
                )

        # 5. VARD
        if has_vard:
            vd = cfg.vard
            if var1_is_vsu:
                off_min, off_max = VARD_OFFSET_V_MIN, VARD_OFFSET_V_MAX
            elif var1_is_voltage:
                off_min, off_max = VARD_OFFSET_V_MIN, VARD_OFFSET_V_MAX
            else:
                off_min, off_max = VARD_OFFSET_I_MIN, VARD_OFFSET_I_MAX
            if not (off_min <= vd.offset <= off_max):
                errors.append(
                    f"VARD Offset: invalid value (range: {off_min:.3g} – {off_max:.3g})"
                )
            if not (RATIO_MIN <= vd.ratio <= RATIO_MAX):
                errors.append(
                    f"VARD Ratio: invalid value (range: {RATIO_MIN:.3g} – {RATIO_MAX:.3g})"
                )
            comp_min, comp_max = get_comp_range(var1_is_voltage or var1_is_vsu)
            if not (comp_min <= vd.compliance <= comp_max):
                errors.append(
                    f"VARD Compliance: invalid value (range: {comp_min:.3g} – {comp_max:.3g})"
                )
            if not (PCOMP_MIN <= vd.power_compliance <= PCOMP_MAX):
                errors.append(
                    f"VARD Power Compliance: invalid value (range: {PCOMP_MIN:.3g} – {PCOMP_MAX:.3g})"
                )

        # 6. Display variables limit
        if len(cfg.display_vars) > DISPLAY_VARS_MAX:
            errors.append(
                f"Too many display variables selected: {len(cfg.display_vars)} (maximum is {DISPLAY_VARS_MAX})."
            )

        # 7. Constant Sources Validation
        errors.extend(
            validate_constant_sources(cfg.constants, active_channels)
        )

        return errors
