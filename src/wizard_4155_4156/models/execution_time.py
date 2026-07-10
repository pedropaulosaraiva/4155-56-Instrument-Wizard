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
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from wizard_4155_4156.models.integration_time import (
    estimated_measurement_time_range,
    estimated_sample_time_range,
    measures_current,
    voltage_ranges_spanned,
)
from wizard_4155_4156.models.qscv_config import QscvConfig
from wizard_4155_4156.models.qscv_config import total_indexes as qscv_indexes
from wizard_4155_4156.models.sampling_config import PeriodMode, SamplingConfig
from wizard_4155_4156.models.sweep_config import (
    SweepConfig,
    SweepConstraints,
    count_measured_units,
    pulsed_channel,
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
        end = cfg.var2.start + (cfg.var2.n_of_steps - 1) * cfg.var2.step
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


def _has_var2(active_channels: List[dict]) -> bool:
    return any(ch.get("function") == "VAR2" for ch in active_channels or [])


def _sweep_total_indexes(
    cfg: SweepConfig, active_channels: List[dict]
) -> Optional[int]:
    return SweepConstraints.total_indexes(cfg, _has_var2(active_channels))


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
    # Pulse sweep: the delay is ignored and each step is synchronized with
    # one pulse period, so the execution time is deterministic (a lower
    # bound when the instrument extends the pulse width automatically).
    if pulsed_channel(active_channels) is not None:
        total = cfg.hold_time + cfg.pulse.period * indexes
        return total, total
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


def qscv_execution_time_range(
    cfg: QscvConfig,
) -> Optional[Tuple[float, float]]:
    """QSCV execution-time interval (s); deterministic (min == max)."""
    indexes = qscv_indexes(cfg)
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


# Adaptive time-scale units: (label, seconds-per-unit, exclusive upper bound in
# seconds).  "d"/"y" are included as a precaution for extreme setups.
_MINUTE: float = 60.0
_HOUR: float = 3600.0
_DAY: float = 86_400.0
_YEAR: float = 365.0 * _DAY
_TIME_UNITS: List[Tuple[str, float, float]] = [
    ("ms", 1e-3, 1.0),
    ("s", 1.0, _MINUTE),
    ("min", _MINUTE, _HOUR),
    ("h", _HOUR, _DAY),
    ("d", _DAY, _YEAR),
    ("y", _YEAR, math.inf),
]


def _scale_time(value: float) -> Tuple[float, str]:
    """(magnitude, unit) for a duration in seconds, picking the largest unit
    that keeps the magnitude readable (ms for sub-second, up to years)."""
    for label, factor, upper in _TIME_UNITS:
        if abs(value) < upper:
            return value / factor, label
    return value / _YEAR, "y"


#: At/above this magnitude, drop the fractional part (3 sig figs render as an
#: integer there anyway) and use a thousands separator.
_INT_MAGNITUDE: float = 100.0


def _fmt_magnitude(magnitude: float) -> str:
    if magnitude >= _INT_MAGNITUDE:
        return f"{magnitude:,.0f}"
    return f"{magnitude:.3g}"


def format_execution_interval(
    result: Optional[Tuple[float, float]],
) -> str:
    """Minimum-runtime estimate for display, scaled to the most readable time
    unit: ``> lo - hi UNIT`` (``> v UNIT`` when the bounds coincide).  When the
    two bounds land in different scales each keeps its own unit
    (``> 800 ms - 2 s``).  Returns ``> indeterminate`` when None."""
    if result is None:
        return "> indeterminate"
    lo, hi = result
    if math.isclose(lo, hi, rel_tol=1e-9):
        magnitude, unit = _scale_time(hi)
        return f"> {_fmt_magnitude(magnitude)} {unit}"
    lo_mag, lo_unit = _scale_time(lo)
    hi_mag, hi_unit = _scale_time(hi)
    if lo_unit == hi_unit:
        return (
            f"> {_fmt_magnitude(lo_mag)} - {_fmt_magnitude(hi_mag)} {hi_unit}"
        )
    return (
        f"> {_fmt_magnitude(lo_mag)} {lo_unit} - "
        f"{_fmt_magnitude(hi_mag)} {hi_unit}"
    )


# ── Measurement statistics (status widget) ───────────────────────────────────


@dataclass(frozen=True)
class MeasurementStats:
    """Counts shown in the status widget's Information section.

    ``points`` = ``indexes`` × number of measurable display variables (a DVOL
    VMU counts as one).  ``exec_time`` is the ``(min, max)`` execution-time
    interval in seconds, or None when indeterminate.
    """

    indexes: Optional[int]
    points: Optional[int]
    exec_time: Optional[Tuple[float, float]]


def _points(indexes: Optional[int], n_vars: int) -> Optional[int]:
    return None if indexes is None else indexes * n_vars


def sweep_measurement_stats(
    cfg: SweepConfig,
    active_channels: List[dict],
    instrument_model: str,
    line_frequency_hz: int,
) -> MeasurementStats:
    indexes = SweepConstraints.total_indexes(cfg, _has_var2(active_channels))
    n_vars = count_measured_units(
        active_channels or [], cfg.display_vars, dvol_weight=1
    )
    exec_range = sweep_execution_time_range(
        cfg, active_channels, instrument_model, line_frequency_hz
    )
    return MeasurementStats(indexes, _points(indexes, n_vars), exec_range)


def _qscv_measurable_count(cfg: QscvConfig) -> int:
    selected = set(cfg.display_vars or [])
    names = (cfg.cap_name, cfg.leak_name)
    return sum(1 for name in names if name and name in selected)


def qscv_measurement_stats(cfg: QscvConfig) -> MeasurementStats:
    indexes = qscv_indexes(cfg)
    n_vars = _qscv_measurable_count(cfg)
    return MeasurementStats(
        indexes,
        _points(indexes, n_vars),
        qscv_execution_time_range(cfg),
    )


def sampling_measurement_stats(
    cfg: SamplingConfig,
    active_channels: List[dict],
    instrument_model: str,
    line_frequency_hz: int,
) -> MeasurementStats:
    indexes = cfg.points
    n_vars = count_measured_units(
        active_channels or [], cfg.display_vars, dvol_weight=1
    )
    exec_range = sampling_execution_time_range(
        cfg, active_channels, instrument_model, line_frequency_hz
    )
    return MeasurementStats(indexes, _points(indexes, n_vars), exec_range)


def measurement_stat_values(stats: MeasurementStats) -> Tuple[str, str, str]:
    """(indexes, points, exec-time) as display strings for the widget."""

    def _count(value: Optional[int]) -> str:
        return f"{value:,}" if isinstance(value, int) else "—"

    return (
        _count(stats.indexes),
        _count(stats.points),
        format_execution_interval(stats.exec_time),
    )
