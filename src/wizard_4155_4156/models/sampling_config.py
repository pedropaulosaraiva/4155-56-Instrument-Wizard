"""
models/sampling_config.py
-------------------------
Domain model for the Sampling (time domain) measurement configuration.

Layer contract
--------------
- No Qt imports.
- All enum values are the SCPI-legal strings consumed by
  SCPI/command_builders/measure_sampling.py.
- SamplingConstraints encodes the 4155/56 sampling rules as pure static
  functions: per-mode bounds used by the view widgets, plus the
  authoritative cross-parameter validate_config().

4155/56 verified hardware limits
--------------------------------
Source: Agilent 4155C/4156C User's Guide Vol.2 "Measurement and Analysis",
Edition 3, Chapter 3 (sampling specs are identical on 4155B/4156B).

Initial interval   : LINEAR 60 µs – 65.535 s | LOG 560 µs – | THIN 720 µs –
No. of samples     : 1 – 10 001 and ≤ 10 001/(measurement units);
                     LOG10 ≤ 111, LOG25 ≤ 276, LOG50 ≤ 551
Total samp. time   : LINEAR — AUTO only when IINT ≤ 480 µs, else
                     IINT×(N−1) … 1e11 s, AUTO or NO LIMIT;
                     THINNED-OUT — NO LIMIT or IINT×(N−1) … 1e11 s;
                     LOG — field not applicable
Hold time          : 0 – 655.35 s (IINT ≥ 2 ms) | −30 ms – 655.35 s
                     (IINT < 2 ms); 100 µs resolution
Stop condition     : only when IINT ≥ 2 ms; enable delay 0 … IINT×32767 s
                     (resolution IINT); event count 1 – 200
IINT < 2 ms forces : single measurement unit, FIXED range, SHORT integration

A unit counts as a *measurement unit* when it is an enabled measure-capable
source (SMU or VMU) AND its measured variable is selected for display:
SMU in V/COMM mode measures I (i_name), SMU in I mode measures V (v_name),
a VMU measures its v_name.  VSUs never count (source only).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple

from wizard_4155_4156.models.integration_time import (
    estimated_sample_time_range,
)
from wizard_4155_4156.models.sweep_config import (
    DISPLAY_VARS_MAX,
    LONG_CYCLES_MAX,
    LONG_CYCLES_MIN,
    SHORT_TIME_MAX,
    SHORT_TIME_MIN,
    WAIT_MULT_MAX,
    WAIT_MULT_MIN,
    IntegrationMode,
    MeasurementSetup,
    count_measured_units,
    measured_variable,
    validate_constant_sources,
    validate_display_vars,
    validate_range_vs_compliance,
)

# ── Enumerations ─────────────────────────────────────────────────────────────


class SamplingMode(str, Enum):
    """Values match the SamplingModeType SCPI literal exactly."""

    LINEAR = "LINEAR"
    L10 = "L10"  # 10 samples / decade
    L25 = "L25"  # 25 samples / decade
    L50 = "L50"  # 50 samples / decade
    THINNEDOUT = "THINNEDOUT"

    def is_log(self) -> bool:
        return self in {SamplingMode.L10, SamplingMode.L25, SamplingMode.L50}


class PeriodMode(str, Enum):
    """
    UI-level state of the TOTAL SAMP. TIME field.  Mapped at JSON-build
    time: AUTO → period_auto "ON", NO_LIMIT → period "INFINITY",
    NUMERIC → period <float>.
    """

    AUTO = "AUTO"
    NO_LIMIT = "NO_LIMIT"
    NUMERIC = "NUMERIC"


class SConEvent(str, Enum):
    """Values match the SConEventType SCPI literal exactly."""

    HIGH = "HIGH"  # Val > Th
    LOW = "LOW"  # Val < Th
    ABSHIGH = "ABSHIGH"  # |Val| > |Th|
    ABSLOW = "ABSLOW"  # |Val| < |Th|


# ── Hardware limit constants (imported by the view for widget bounds) ────────

IINT_MIN_LINEAR: float = 60e-6  # s
IINT_MIN_LOG: float = 560e-6  # s — L10 / L25 / L50
IINT_MIN_THINNED: float = 720e-6  # s
IINT_MAX: float = 65.535  # s
IINT_AUTO_ONLY_THRESHOLD: float = 480e-6  # LINEAR: IINT ≤ → AUTO only
IINT_STOP_COND_MIN: float = 2e-3  # stop condition & relaxed hold time

SAMPLES_MIN: int = 1
SAMPLES_MAX: int = 10_001
SAMPLES_MAX_L10: int = 111
SAMPLES_MAX_L25: int = 276
SAMPLES_MAX_L50: int = 551

PERIOD_MAX: float = 1e11  # s

SAMP_HOLD_MIN: float = 0.0  # s — when IINT ≥ 2 ms
SAMP_HOLD_MIN_FAST: float = -0.03  # s — when IINT < 2 ms
SAMP_HOLD_MAX: float = 655.35  # s
SAMP_HOLD_RESOLUTION: float = 100e-6  # s

EDELAY_MIN: float = 0.0
EDELAY_MAX_MULTIPLIER: int = 32_767  # max enable delay = IINT × 32767

EVENT_COUNT_MIN: int = 1
EVENT_COUNT_MAX: int = 200

# ── Timing-warning heuristics (non-blocking) ─────────────────────────────────
# Per-sample measurement-time estimate: integration_time × n_meas_units.
# MED integration is 1 PLC; the PLC duration is derived from the user's
# configured AC line frequency (1 / f), not assumed to be 50 Hz.
# The instrument wait time is deliberately excluded: it is DUT-dependent
# (can be an arbitrarily long settling interval) and does not deterministically
# lengthen the achievable sampling interval.
DEFAULT_LINE_FREQUENCY_HZ: int = 50  # fallback when no preference is supplied
SAMPLE_TIME_CLOSE_RATIO: float = 0.75  # estimate ≥ 75 % of IINT → warn
SAMPLE_TIME_EXCEED_RATIO: float = 2.0  # estimate ≥ 2 × IINT → strong warn

# Built-in display variables always offered by the sampling page
BUILTIN_DISPLAY_VARS: Tuple[str, ...] = ("@TIME", "@INDEX")


def _format_time_interval(lo: float, hi: float) -> str:
    """Render a per-sample time estimate: a single value when the bounds
    coincide, otherwise a ``~lo–hi s`` interval."""
    if math.isclose(lo, hi, rel_tol=1e-9):
        return f"~{hi:.3g} s"
    return f"~{lo:.3g}–{hi:.3g} s"


# ── Per-section dataclasses ──────────────────────────────────────────────────


@dataclass
class StopCondition:
    enabled: bool = False
    name: str = ""  # monitored measurement variable
    threshold: float = 0.0
    event: SConEvent = SConEvent.HIGH
    event_count: int = 1
    enable_delay: float = 0.0  # s


@dataclass
class SamplingConfig:
    """Complete snapshot of the Sampling configuration page."""

    measurement_setup: MeasurementSetup = field(
        default_factory=MeasurementSetup
    )
    mode: SamplingMode = SamplingMode.LINEAR
    initial_interval: float = 2e-3  # s
    points: int = 11  # NO. OF SAMPLES
    hold_time: float = 0.0  # s
    period_mode: PeriodMode = PeriodMode.AUTO
    period: float = 1.0  # s — used only when period_mode == NUMERIC
    filter_on: bool = True
    stop_condition: StopCondition = field(default_factory=StopCondition)
    channel_standby: Dict[str, bool] = field(default_factory=dict)
    display_vars: List[str] = field(default_factory=list)
    constants: Dict[str, Dict[str, float]] = field(default_factory=dict)


# ── Constraint rule-set ──────────────────────────────────────────────────────


class SamplingConstraints:
    """
    Static, pure-function rule-set for the sampling page.

    Bound helpers are consumed by the presenter to (re)configure widget
    limits; validate_config() is the authoritative validator and returns
    (errors, warnings) — warnings never block JSON generation or saving.
    """

    # ── Bound helpers ────────────────────────────────────────────────────

    @staticmethod
    def iint_min(mode: SamplingMode) -> float:
        if mode == SamplingMode.THINNEDOUT:
            return IINT_MIN_THINNED
        if mode.is_log():
            return IINT_MIN_LOG
        return IINT_MIN_LINEAR

    @staticmethod
    def points_max(mode: SamplingMode, n_meas_units: int) -> int:
        if mode == SamplingMode.L10:
            return SAMPLES_MAX_L10
        if mode == SamplingMode.L25:
            return SAMPLES_MAX_L25
        if mode == SamplingMode.L50:
            return SAMPLES_MAX_L50
        return SAMPLES_MAX // max(1, n_meas_units)

    @staticmethod
    def allowed_period_modes(
        mode: SamplingMode, iint: float
    ) -> List[PeriodMode]:
        """Empty list means the TOTAL SAMP. TIME field is not applicable."""
        if mode.is_log():
            return []
        if mode == SamplingMode.THINNEDOUT:
            return [PeriodMode.NO_LIMIT, PeriodMode.NUMERIC]
        if iint <= IINT_AUTO_ONLY_THRESHOLD:
            return [PeriodMode.AUTO]
        return [PeriodMode.AUTO, PeriodMode.NO_LIMIT, PeriodMode.NUMERIC]

    @staticmethod
    def period_numeric_bounds(iint: float, points: int) -> Tuple[float, float]:
        return iint * max(0, points - 1), PERIOD_MAX

    @staticmethod
    def hold_time_min(iint: float) -> float:
        return (
            SAMP_HOLD_MIN_FAST if iint < IINT_STOP_COND_MIN else SAMP_HOLD_MIN
        )

    @staticmethod
    def stop_condition_allowed(iint: float) -> bool:
        return iint >= IINT_STOP_COND_MIN

    @staticmethod
    def measured_variable(channel: dict) -> str | None:
        """Delegates to the shared :func:`measured_variable` helper."""
        return measured_variable(channel)

    @staticmethod
    def count_measurement_units(
        active_channels: List[dict], display_vars: List[str]
    ) -> int:
        """
        Number of units that will actually measure: enabled SMUs/VMUs whose
        measured variable is selected for display.

        Drives the data-buffer split (``points_max``), so a dvol pair counts
        as one stored value.  For the per-sample *time* estimate, which scales
        with integration count, use ``count_measured_units`` with
        ``dvol_weight=2`` (see :meth:`_timing_warnings`).
        """
        return count_measured_units(
            active_channels, display_vars, dvol_weight=1
        )

    # ── Authoritative validation ─────────────────────────────────────────

    @staticmethod
    def _validate_measurement_setup(ms: MeasurementSetup) -> List[str]:
        errors: List[str] = []
        if not (WAIT_MULT_MIN <= ms.wait_multiplier <= WAIT_MULT_MAX):
            errors.append(
                "Wait Multiplier: invalid value "
                f"(range: {WAIT_MULT_MIN:.3g} – {WAIT_MULT_MAX:.3g})"
            )
        for unit, r_cfg in ms.ranges.items():
            r_mode = r_cfg.get("mode")
            if r_mode in {"LIM", "FIX"} and "value" not in r_cfg:
                errors.append(
                    f"Range value for {unit} must be specified "
                    f"when mode is {r_mode}"
                )
        if ms.integration_mode == IntegrationMode.SHORT:
            if not (SHORT_TIME_MIN <= ms.short_time <= SHORT_TIME_MAX):
                errors.append(
                    "Short Aperture: invalid value "
                    f"(range: {SHORT_TIME_MIN:.3g} – {SHORT_TIME_MAX:.3g} s)"
                )
        elif ms.integration_mode == IntegrationMode.LONG:
            if not (LONG_CYCLES_MIN <= ms.long_time_cycles <= LONG_CYCLES_MAX):
                errors.append(
                    "Integration Cycles: invalid value "
                    f"(range: {LONG_CYCLES_MIN} – {LONG_CYCLES_MAX} PLC)"
                )
        return errors

    @staticmethod
    def _validate_sampling_params(
        cfg: SamplingConfig, n_units: int
    ) -> List[str]:
        errors: List[str] = []
        iint = cfg.initial_interval

        iint_lo = SamplingConstraints.iint_min(cfg.mode)
        if not (iint_lo <= iint <= IINT_MAX):
            errors.append(
                f"Initial Interval: invalid value for {cfg.mode.value} "
                f"(range: {iint_lo:.3g} – {IINT_MAX:.3g} s)"
            )

        pts_max = SamplingConstraints.points_max(cfg.mode, n_units)
        if not (SAMPLES_MIN <= cfg.points <= pts_max):
            errors.append(
                f"No. of Samples: invalid value for {cfg.mode.value} with "
                f"{n_units} measurement unit(s) "
                f"(range: {SAMPLES_MIN} – {pts_max})"
            )

        allowed_periods = SamplingConstraints.allowed_period_modes(
            cfg.mode, iint
        )
        if allowed_periods:
            if cfg.period_mode not in allowed_periods:
                names = "/".join(p.value for p in allowed_periods)
                errors.append(
                    f"Total Samp. Time: {cfg.period_mode.value} not "
                    f"allowed here (allowed: {names})"
                )
            elif cfg.period_mode == PeriodMode.NUMERIC:
                p_lo, p_hi = SamplingConstraints.period_numeric_bounds(
                    iint, cfg.points
                )
                if not (p_lo <= cfg.period <= p_hi):
                    errors.append(
                        "Total Samp. Time: invalid value "
                        f"(range: {p_lo:.3g} – {p_hi:.3g} s)"
                    )

        h_lo = SamplingConstraints.hold_time_min(iint)
        if not (h_lo <= cfg.hold_time <= SAMP_HOLD_MAX):
            errors.append(
                "Hold Time: invalid value "
                f"(range: {h_lo:.3g} – {SAMP_HOLD_MAX:.3g} s)"
            )
        return errors

    @staticmethod
    def _validate_stop_condition(
        cfg: SamplingConfig, available_vars: List[str]
    ) -> List[str]:
        sc = cfg.stop_condition
        if not sc.enabled:
            return []
        errors: List[str] = []
        iint = cfg.initial_interval
        if not SamplingConstraints.stop_condition_allowed(iint):
            errors.append(
                "Stop Condition: requires Initial Interval ≥ "
                f"{IINT_STOP_COND_MIN:.3g} s"
            )
        edel_max = iint * EDELAY_MAX_MULTIPLIER
        if not (EDELAY_MIN <= sc.enable_delay <= edel_max):
            errors.append(
                "Stop Condition Enable Delay: invalid value "
                f"(range: {EDELAY_MIN:.3g} – {edel_max:.3g} s)"
            )
        if not (EVENT_COUNT_MIN <= sc.event_count <= EVENT_COUNT_MAX):
            errors.append(
                "Stop Condition Event No.: invalid value "
                f"(range: {EVENT_COUNT_MIN} – {EVENT_COUNT_MAX})"
            )
        if sc.name not in available_vars:
            errors.append(
                f"Stop Condition Name: '{sc.name}' is not a measured variable"
            )
        return errors

    @staticmethod
    def _validate_fast_rules(
        cfg: SamplingConfig, active_channels: List[dict], n_units: int
    ) -> List[str]:
        """Cross rules that apply only when IINT < 2 ms."""
        if cfg.initial_interval >= IINT_STOP_COND_MIN:
            return []
        errors: List[str] = []
        ms = cfg.measurement_setup
        if n_units > 1:
            errors.append(
                f"Initial Interval < {IINT_STOP_COND_MIN:.3g} s allows "
                f"only 1 measurement unit ({n_units} selected via "
                "display variables)"
            )
        selected = set(cfg.display_vars)
        measured_units = {
            ch["id"]
            for ch in active_channels or []
            if SamplingConstraints.measured_variable(ch) in selected
        }
        for unit in sorted(measured_units):
            r_mode = ms.ranges.get(unit, {}).get("mode")
            if r_mode != "FIX":
                errors.append(
                    f"{unit} Range: must be FIXED when Initial "
                    f"Interval < {IINT_STOP_COND_MIN:.3g} s"
                )
        if ms.integration_mode != IntegrationMode.SHORT:
            errors.append(
                "Integration Time: must be SHORT when Initial "
                f"Interval < {IINT_STOP_COND_MIN:.3g} s"
            )
        return errors

    @staticmethod
    def _timing_warnings(
        cfg: SamplingConfig,
        active_channels: List[dict],
        instrument_model: str = "4155C",
        line_frequency_hz: int = DEFAULT_LINE_FREQUENCY_HZ,
    ) -> List[str]:
        """Non-blocking feasibility warnings on the sampling interval.

        The estimate is a ``(min, max)`` interval: current measurements under
        AUTO / limited-auto ranging span a range of effective integration
        times, while voltage measurements (and fixed current ranges) collapse
        to a single value.  The warning triggers on the worst case (max).
        """
        iint = cfg.initial_interval
        t_min, t_max = estimated_sample_time_range(
            cfg.measurement_setup,
            active_channels,
            cfg.display_vars,
            cfg.constants,
            instrument_model,
            line_frequency_hz,
        )
        if t_max <= 0 or iint <= 0:
            return []
        interval = _format_time_interval(t_min, t_max)
        if t_max >= SAMPLE_TIME_EXCEED_RATIO * iint:
            return [
                f"Estimation time per measurement index ({interval}) exceeds "
                f"the Initial Interval ({iint:.3g} s)"
            ]
        if t_max >= SAMPLE_TIME_CLOSE_RATIO * iint:
            return [
                f"Estimation time per measurement index ({interval}) is close "
                f"to the Initial Interval ({iint:.3g} s)"
            ]
        return []

    @staticmethod
    def validate_config(
        cfg: SamplingConfig,
        active_channels: List[dict],
        available_vars: List[str],
        interlock_open: bool = False,
        instrument_model: str = "4155C",
        line_frequency_hz: int = DEFAULT_LINE_FREQUENCY_HZ,
    ) -> Tuple[List[str], List[str]]:
        """
        Validate the full sampling configuration.

        Returns (errors, warnings).  Errors block JSON generation and
        saving; warnings (timing feasibility) are informational only.
        """
        sampling_constraints = SamplingConstraints
        n_units = sampling_constraints.count_measurement_units(
            active_channels, cfg.display_vars
        )

        errors: List[str] = []
        errors.extend(
            sampling_constraints._validate_measurement_setup(
                cfg.measurement_setup
            )
        )
        errors.extend(
            sampling_constraints._validate_sampling_params(cfg, n_units)
        )
        errors.extend(
            sampling_constraints._validate_stop_condition(cfg, available_vars)
        )
        errors.extend(
            sampling_constraints._validate_fast_rules(
                cfg, active_channels, n_units
            )
        )
        errors.extend(
            validate_constant_sources(
                cfg.constants,
                active_channels,
                interlock_open,
                instrument_model,
            )
        )

        measurement_vars = [
            measured_variable(ch)
            for ch in (active_channels or [])
            if measured_variable(ch)
        ]
        errors.extend(
            validate_display_vars(
                cfg.display_vars,
                measurement_vars,
                max_total=DISPLAY_VARS_MAX,
            )
        )

        compliance_by_unit = {
            cid: c["compliance"]
            for cid, c in cfg.constants.items()
            if c.get("compliance") is not None
        }
        errors.extend(
            validate_range_vs_compliance(
                active_channels or [],
                cfg.measurement_setup.ranges,
                compliance_by_unit,
                instrument_model,
            )
        )

        warnings = sampling_constraints._timing_warnings(
            cfg, active_channels, instrument_model, line_frequency_hz
        )
        return errors, warnings
