"""
models/execution_time.py
------------------------
Estimated *execution time* (total run duration) for a measurement setup.

Layer contract
--------------
- No Qt imports.  Pure static functions, unit-testable in isolation.

This module sits above the per-method config models: it imports
``integration_time`` (the effective per-measurement interval) plus the three
config models.  It lives here — rather than inside each config model — because
``sweep_config`` cannot import ``integration_time`` (that would create a cycle,
since ``integration_time`` imports ``sweep_config``).

Formulas (from the 4155/56 measurement model)
---------------------------------------------
Sweep / QSCV::

    Execution = Hold + (Delay + MeasInterval) × TotalIndexes
    TotalIndexes = VAR1Points × (2 if Double Sweep else 1) × VAR2Steps

where VAR2Steps is ``var2.n_of_steps`` for a sweep with a VAR2 unit, otherwise
1 (QSCV always uses 1).

Sampling::

    NUMERIC total time → Hold + period
    AUTO (LINEAR)      → Hold + adjusted_interval × samples
    LOG / NO_LIMIT     → indeterminate (None)

where ``adjusted_interval`` is the smallest multiple of the initial interval
that is ≥ the estimated measurement interval (the instrument cannot start a new
sample before the current measurement finishes).

``MeasInterval`` is a ``(min, max)`` pair, so execution time is returned as a
``(min, max)`` tuple (collapsing to ``min == max`` when deterministic), or
``None`` for the indeterminate sampling cases.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from wizard_4155_4156.models.integration_time import (
    estimated_measurement_time_range,
    estimated_sample_time_range,
    measures_current,
    voltage_ranges_spanned,
)
from wizard_4155_4156.models.qscv_config import QscvConfig, no_of_step
from wizard_4155_4156.models.sampling_config import PeriodMode, SamplingConfig
from wizard_4155_4156.models.sweep_config import (
    SweepConfig,
    SweepConstraints,
    SweepSpacing,
    VAR1Mode,
)

# ── Sweep ────────────────────────────────────────────────────────────────────


def _magnitude_bounds(a: float, b: float) -> Tuple[float, float]:
    """(min, max) of ``|v|`` over the closed interval [a, b].

    When the interval crosses zero the minimum magnitude is 0.
    """
    if (a < 0) != (b < 0):
        return 0.0, max(abs(a), abs(b))
    return min(abs(a), abs(b)), max(abs(a), abs(b))


def _sweep_source_magnitudes(
    cfg: SweepConfig, channel: dict
) -> Tuple[float, float]:
    """(min, max) output-voltage magnitude of a current-measuring SMU.

    A CONST/COMM source is fixed; a VAR1/VAR2/VAR1' source sweeps over a range
    of output voltages that the caller maps to the traversed output ranges.
    """
    function = channel.get("function")
    if function == "VAR1":
        return _magnitude_bounds(cfg.var1.start, cfg.var1.stop)
    if function == "VAR2":
        end = cfg.var2.start + cfg.var2.n_of_steps * cfg.var2.step
        return _magnitude_bounds(cfg.var2.start, end)
    if function == "VAR1'":  # VARD: output = VAR1 × ratio + offset
        a = cfg.var1.start * cfg.vard.ratio + cfg.vard.offset
        b = cfg.var1.stop * cfg.vard.ratio + cfg.vard.offset
        return _magnitude_bounds(a, b)
    # CONST / COMM — fixed source (COMM has no constant entry ⇒ 0 V).
    entry = cfg.constants.get(channel.get("id"), {}) or {}
    magnitude = abs(entry.get("source", 0.0) or 0.0)
    return magnitude, magnitude


def _sweep_voltage_ranges_by_unit(
    cfg: SweepConfig, active_channels: List[dict]
) -> Dict[str, List[float]]:
    """Output voltage ranges each current-measuring SMU traverses."""
    result: Dict[str, List[float]] = {}
    for ch in active_channels or []:
        if not measures_current(ch):
            continue
        lo, hi = _sweep_source_magnitudes(cfg, ch)
        result[ch["id"]] = voltage_ranges_spanned(lo, hi)
    return result


def _sweep_total_indexes(
    cfg: SweepConfig, active_channels: List[dict]
) -> Optional[int]:
    v1 = cfg.var1
    step = v1.step if v1.spacing == SweepSpacing.LINEAR else 0.0
    points = SweepConstraints.var1_step_count(
        v1.start, v1.stop, step, v1.spacing
    )
    if points is None:
        return None
    double = 2 if v1.mode == VAR1Mode.DOUBLE else 1
    has_var2 = any(
        ch.get("function") == "VAR2" for ch in active_channels or []
    )
    var2_steps = cfg.var2.n_of_steps if has_var2 else 1
    return points * double * var2_steps


def sweep_execution_time_range(
    cfg: SweepConfig,
    active_channels: List[dict],
    instrument_model: str,
    line_frequency_hz: int,
) -> Optional[Tuple[float, float]]:
    """Estimated Sweep execution-time interval (s), or None if undetermined."""
    indexes = _sweep_total_indexes(cfg, active_channels)
    if indexes is None:
        return None
    is_4156 = "56" in (instrument_model or "")
    voltage_ranges = _sweep_voltage_ranges_by_unit(cfg, active_channels)
    t_min, t_max = estimated_measurement_time_range(
        cfg.measurement_setup,
        active_channels,
        cfg.display_vars,
        voltage_ranges,
        is_4156,
        line_frequency_hz,
    )
    lo = cfg.hold_time + (cfg.delay + t_min) * indexes
    hi = cfg.hold_time + (cfg.delay + t_max) * indexes
    return lo, hi


# ── QSCV ─────────────────────────────────────────────────────────────────────


def _qscv_measurement_interval(cfg: QscvConfig) -> float:
    """Deterministic per-point interval (s): capacitance + optional leakage.

    Capacitance is always measured; the leakage current adds its integration
    time only when its variable is selected for display.
    """
    interval = cfg.cap_integration_time
    if cfg.leak_name and cfg.leak_name in set(cfg.display_vars or []):
        interval += cfg.leak_integration_time
    return interval


def _qscv_total_indexes(cfg: QscvConfig) -> Optional[int]:
    points = no_of_step(cfg.var1.start, cfg.var1.stop, cfg.var1.step)
    if points is None:
        return None
    double = 2 if cfg.var1.mode == VAR1Mode.DOUBLE else 1
    return points * double  # no VAR2 ⇒ VAR2Steps = 1


def qscv_execution_time_range(
    cfg: QscvConfig,
) -> Optional[Tuple[float, float]]:
    """QSCV execution-time interval (s); deterministic (min == max)."""
    indexes = _qscv_total_indexes(cfg)
    if indexes is None:
        return None
    interval = _qscv_measurement_interval(cfg)
    total = cfg.hold_time + (cfg.delay + interval) * indexes
    return total, total


# ── Sampling ─────────────────────────────────────────────────────────────────


def _adjusted_interval(
    measurement_time: float, initial_interval: float
) -> float:
    """Smallest multiple of the initial interval ≥ the measurement time."""
    if initial_interval <= 0:
        return 0.0
    multiple = max(1, math.ceil(measurement_time / initial_interval))
    return multiple * initial_interval


def sampling_execution_time_range(
    cfg: SamplingConfig,
    active_channels: List[dict],
    instrument_model: str,
    line_frequency_hz: int,
) -> Optional[Tuple[float, float]]:
    """Estimated Sampling execution-time interval (s).

    Returns None (indeterminate) for logarithmic modes and for a No-Limit total
    sampling time — neither has a bounded, predictable duration.
    """
    if cfg.mode.is_log() or cfg.period_mode == PeriodMode.NO_LIMIT:
        return None
    if cfg.period_mode == PeriodMode.NUMERIC:
        total = cfg.hold_time + cfg.period
        return total, total
    # AUTO (LINEAR): the effective interval rounds up to a multiple of IINT.
    t_min, t_max = estimated_sample_time_range(
        cfg.measurement_setup,
        active_channels,
        cfg.display_vars,
        cfg.constants,
        instrument_model,
        line_frequency_hz,
    )
    iint = cfg.initial_interval
    lo = cfg.hold_time + _adjusted_interval(t_min, iint) * cfg.points
    hi = cfg.hold_time + _adjusted_interval(t_max, iint) * cfg.points
    return lo, hi


# ── Formatting ───────────────────────────────────────────────────────────────

_LARGE_SECONDS: float = 100.0  # above this, drop fractional seconds


def _fmt_seconds(value: float) -> str:
    if value >= _LARGE_SECONDS:
        return f"{value:,.0f}"
    return f"{value:.3g}"


def format_execution_time(result: Optional[Tuple[float, float]]) -> str:
    """Render an execution-time estimate for the config status line."""
    if result is None:
        return "est. run time: indeterminate"
    lo, hi = result
    if math.isclose(lo, hi, rel_tol=1e-9):
        return f"est. {_fmt_seconds(hi)} s"
    return f"est. {_fmt_seconds(lo)}–{_fmt_seconds(hi)} s"
