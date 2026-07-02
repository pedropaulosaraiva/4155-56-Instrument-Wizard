"""
models/integration_time.py
--------------------------
Effective A/D integration-time model for the 4155C/4156C.

Layer contract
--------------
- No Qt imports.  Pure static functions, unit-testable in isolation.

Why this exists
---------------
The value the user configures as "integration time" (seconds in SHORT mode,
PLC in MEDIUM/LONG) is *not* the time the instrument actually integrates for.
The effective integration time depends on the measurement type (voltage vs
current), the current measurement range, the output voltage range, the
integration mode and the SMU model (HRSMU on the 4156, MPSMU on the 4155).

This module reproduces the manual's behaviour:

- Table 7-22  Integration Time in Long Mode   (without ADC Zero)
- Table 7-23  Integration Time in Medium Mode (without ADC Zero)
- Table 7-24  Integration Time in Short Mode  (Integ time 0.96–1.92 ms)

The "without ADC Zero" tables omit the extra ×2 applied to *current*
measurements in MEDIUM/LONG, so that factor is re-applied here.  Only HRSMU
and MPSMU are in scope; HPSMU rows are ignored.

Because AUTO / limited-auto ranging hides the run-time current range,
``estimated_sample_time_range`` returns a ``(min, max)`` interval spanning the
fastest and slowest possible effective integration times.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from wizard_4155_4156.models.sweep_config import (
    RANGE_VALUES_HRSMU_CURRENT,
    RANGE_VALUES_MPSMU_CURRENT,
    RANGE_VALUES_SMU_VOLTAGE,
    IntegrationMode,
    measured_variable,
    smallest_range_at_least,
)

# SHORT-mode apertures in [0.96 ms, 1.92 ms] follow Table 7-24; below 0.96 ms
# the instrument uses other (not-modelled) tables, so the estimate falls back
# to the raw configured aperture with no per-range factor.
SHORT_TABLE_MIN: float = 0.96e-3  # s

_DEFAULT_LINE_FREQUENCY_HZ: int = 50
_LONG_MAX_PLC: int = 100  # Table 7-22 caps the integration time at 100 PLC
# Extra ×2 applied in MEDIUM/LONG (current: the ADC-Zero factor absent from the
# "without ADC Zero" tables; voltage: the manual's doubling of the setting).
_MED_LONG_FACTOR: int = 2

# Current-range decade exponents (round(log10(range))); table rows are keyed by
# these so no numeric range comparisons are needed.
_DEC_10PA: int = -11
_DEC_100PA: int = -10
_DEC_1NA: int = -9
_DEC_10NA: int = -8
_DEC_100NA: int = -7
_DEC_1UA: int = -6
_DEC_10UA: int = -5

# Named SMU voltage output ranges (V) that gate the Short-mode multipliers.
_V_2, _V_20, _V_40, _V_100 = (val for _label, val in RANGE_VALUES_SMU_VOLTAGE)

# Table 7-23 integration time in PLC (before the ×2 factor); ranges not listed
# default to 1 PLC (10 nA .. 100 mA).
_MED_PLC_HRSMU: Dict[int, float] = {
    _DEC_10PA: 50.0,
    _DEC_100PA: 10.0,
    _DEC_1NA: 5.0,
}
_MED_PLC_MPSMU: Dict[int, float] = {_DEC_1NA: 3.0}


def _plc_seconds(line_frequency_hz: int) -> float:
    return 1.0 / (line_frequency_hz or _DEFAULT_LINE_FREQUENCY_HZ)


def _range_decade(current_range: float) -> int:
    """Decade exponent of a standard current range (10 pA → -11 … 100 mA → -1).

    100 µA and above (exponent ≥ -4) all share the same table row.
    """
    return round(math.log10(current_range))


def _mpsmu_100na_mult(v: float) -> int:
    """Table 7-24 MPSMU 100 nA multiplier by output voltage range."""
    if v <= _V_20:
        return 1
    if v <= _V_40:
        return 2
    return 4


def _mpsmu_10ua_mult(v: float) -> int:
    """Table 7-24 MPSMU 10 µA multiplier by output voltage range."""
    if v <= _V_20:
        return 1
    if v <= _V_40:
        return 2
    return 3


def _hrsmu_short_seconds(
    decade: int, v: float, short_time: float, plc: float
) -> float:
    """Table 7-24 effective integration time (s) for an HRSMU current."""
    table = {
        _DEC_10PA: 10 * plc,
        _DEC_100PA: 2 * plc,
        _DEC_1NA: plc,
        _DEC_10NA: 4 * short_time,
        _DEC_100NA: (4 if v > _V_20 else 2) * short_time,
        _DEC_1UA: short_time,
        _DEC_10UA: (2 if v > _V_2 else 1) * short_time,
    }
    return table.get(decade, short_time)  # 100 µA .. 100 mA → ×1


def _mpsmu_short_seconds(decade: int, v: float, short_time: float) -> float:
    """Table 7-24 effective integration time (s) for an MPSMU current."""
    table = {
        _DEC_1NA: (2 if v > _V_40 else 1) * short_time,
        _DEC_10NA: short_time,
        _DEC_100NA: _mpsmu_100na_mult(v) * short_time,
        _DEC_1UA: short_time,
        _DEC_10UA: _mpsmu_10ua_mult(v) * short_time,
    }
    return table.get(decade, short_time)  # 100 µA .. 100 mA → ×1


def _short_current_seconds(
    current_range: float,
    voltage_range: float,
    is_4156: bool,
    short_time: float,
    plc: float,
) -> float:
    """Table 7-24 effective integration time (s) for a current measurement.

    Entries are either an absolute PLC count (→ ``× plc``) or a multiple of the
    configured aperture (``short_time``).
    """
    decade = _range_decade(current_range)
    if is_4156:
        return _hrsmu_short_seconds(decade, voltage_range, short_time, plc)
    return _mpsmu_short_seconds(decade, voltage_range, short_time)


def _med_current_plc(current_range: float, is_4156: bool) -> float:
    """Table 7-23 integration time in PLC (before the ×2 ADC-Zero factor)."""
    table = _MED_PLC_HRSMU if is_4156 else _MED_PLC_MPSMU
    return table.get(_range_decade(current_range), 1.0)  # ≥10 nA → 1 PLC


def _long_current_plc(
    current_range: float, is_4156: bool, long_cycles: int
) -> float:
    """Table 7-22 integration time in PLC (before the ×2 ADC-Zero factor).

    ``long_cycles`` is the configured setting value; results are capped at
    100 PLC as stated in the manual.
    """
    if is_4156:  # HRSMU has range-dependent factors below 10 nA
        hrsmu = {
            _DEC_10PA: float(_LONG_MAX_PLC),  # always 100 PLC
            _DEC_100PA: float(min(long_cycles * 10, _LONG_MAX_PLC)),
            _DEC_1NA: float(min(long_cycles * 5, _LONG_MAX_PLC)),
        }
        capped = hrsmu.get(_range_decade(current_range))
        if capped is not None:
            return capped
    return float(min(long_cycles, _LONG_MAX_PLC))  # 10 nA .. 100 mA / MPSMU


def _voltage_integration_seconds(
    integration_mode: IntegrationMode,
    short_time: float,
    long_cycles: int,
    plc: float,
) -> float:
    """Voltage measurement: no range dependence; ×2 in MEDIUM/LONG."""
    if integration_mode == IntegrationMode.SHORT:
        return short_time
    if integration_mode == IntegrationMode.LONG:
        return _MED_LONG_FACTOR * long_cycles * plc
    return _MED_LONG_FACTOR * plc  # MEDIUM (base 1 PLC)


def _current_integration_seconds(
    integration_mode: IntegrationMode,
    short_time: float,
    long_cycles: int,
    plc: float,
    current_range: float,
    voltage_range: float,
    is_4156: bool,
) -> float:
    """Current measurement effective integration time (s)."""
    if integration_mode == IntegrationMode.SHORT:
        if short_time < SHORT_TABLE_MIN:
            return short_time  # below Table 7-24 → raw aperture, no factor
        return _short_current_seconds(
            current_range, voltage_range, is_4156, short_time, plc
        )
    if integration_mode == IntegrationMode.LONG:
        plc_count = _long_current_plc(current_range, is_4156, long_cycles)
    else:
        plc_count = _med_current_plc(current_range, is_4156)
    return plc_count * _MED_LONG_FACTOR * plc


def effective_integration_time(
    *,
    integration_mode: IntegrationMode,
    short_time: float,
    long_cycles: int,
    line_frequency_hz: int,
    measures_current: bool,
    current_range: Optional[float] = None,
    voltage_range: Optional[float] = None,
    is_4156: bool = False,
) -> float:
    """Effective A/D integration time (s) for a single measured variable."""
    plc = _plc_seconds(line_frequency_hz)
    if not measures_current:
        return _voltage_integration_seconds(
            integration_mode, short_time, long_cycles, plc
        )
    return _current_integration_seconds(
        integration_mode,
        short_time,
        long_cycles,
        plc,
        current_range,
        voltage_range,
        is_4156,
    )


def possible_current_ranges(
    range_cfg: Dict[str, Any], is_4156: bool
) -> List[float]:
    """Current measurement ranges the instrument might use at run time.

    - ``FIX`` (value)  → exactly that range.
    - ``LIM`` (value)  → every model range ≥ value (limited auto-ranging).
    - ``AUTO`` / missing value → every model range.
    """
    model_ranges = (
        RANGE_VALUES_HRSMU_CURRENT if is_4156 else RANGE_VALUES_MPSMU_CURRENT
    )
    all_ranges = [val for _label, val in model_ranges]
    cfg = range_cfg or {}
    mode = cfg.get("mode", "AUTO")
    value = cfg.get("value")
    if value is not None:
        if mode == "FIX":
            return [value]
        if mode == "LIM":
            subset = [r for r in all_ranges if r >= value]
            return subset or [all_ranges[-1]]
    return all_ranges


def _measures_current(channel: Dict[str, Any]) -> bool:
    """An SMU forcing V/VPULSE (or a COMM return) measures current."""
    return channel.get("unit_type") == "SMU" and channel.get("mode") in (
        "V",
        "VPULSE",
        "COMM",
    )


def _output_voltage_range(
    channel: Dict[str, Any], constants: Dict[str, Dict[str, float]]
) -> float:
    """Voltage output range of a current-measuring SMU.

    Derived from the constant source magnitude via the smallest standard SMU
    voltage range that covers it (COMM / no constant ⇒ 0 V ⇒ smallest range).
    """
    entry = (constants or {}).get(channel.get("id"), {}) or {}
    source = entry.get("source", 0.0) or 0.0
    v_range = smallest_range_at_least(abs(source), RANGE_VALUES_SMU_VOLTAGE)
    if v_range is None:
        return RANGE_VALUES_SMU_VOLTAGE[-1][1]  # cap at the largest (100 V)
    return v_range


def estimated_sample_time_range(
    ms,  # MeasurementSetup
    active_channels: List[dict],
    display_vars: List[str],
    constants: Dict[str, Dict[str, float]],
    instrument_model: str,
    line_frequency_hz: int,
) -> Tuple[float, float]:
    """Per-sample measurement-time interval ``(min, max)`` in seconds.

    Each enabled measure-capable unit whose measured variable is displayed
    contributes its effective integration time.  Current measurements under
    AUTO / limited-auto ranging span an interval because the run-time range is
    unknown; voltage measurements (and fixed current ranges) collapse to a
    single value, so ``min == max``.  A VMU in DVOLT mode counts twice (it
    integrates both VMUs in turn).  The instrument wait time is excluded — it
    is DUT-dependent and does not deterministically lengthen the interval.
    """
    is_4156 = "56" in (instrument_model or "")
    selected = set(display_vars or [])
    t_min = 0.0
    t_max = 0.0

    for ch in active_channels or []:
        measured = measured_variable(ch)
        if measured is None or measured not in selected:
            continue
        weight = (
            2
            if ch.get("unit_type") == "VMU" and ch.get("mode") == "DVOLT"
            else 1
        )

        if _measures_current(ch):
            v_range = _output_voltage_range(ch, constants)
            ranges = possible_current_ranges(
                ms.ranges.get(ch["id"], {}), is_4156
            )
            times = [
                effective_integration_time(
                    integration_mode=ms.integration_mode,
                    short_time=ms.short_time,
                    long_cycles=ms.long_time_cycles,
                    line_frequency_hz=line_frequency_hz,
                    measures_current=True,
                    current_range=r,
                    voltage_range=v_range,
                    is_4156=is_4156,
                )
                for r in ranges
            ]
            lo, hi = min(times), max(times)
        else:
            lo = hi = effective_integration_time(
                integration_mode=ms.integration_mode,
                short_time=ms.short_time,
                long_cycles=ms.long_time_cycles,
                line_frequency_hz=line_frequency_hz,
                measures_current=False,
                is_4156=is_4156,
            )

        t_min += weight * lo
        t_max += weight * hi

    return t_min, t_max
