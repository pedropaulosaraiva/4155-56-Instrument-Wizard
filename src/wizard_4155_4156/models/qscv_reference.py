"""
models/qscv_reference.py
------------------------
Manufacturer reference data for the maximum measurable capacitance in QSCV.

Layer contract
--------------
- No Qt imports.  Pure data + arithmetic, unit-testable without a GUI.

Background
----------
A quasi-static C-V measurement starts to oscillate above a capacitance ceiling
that depends on the selected current range, the integration time and the
capacitance measurement voltage.  The manufacturer publishes reference curves
for that ceiling; on a log-log plot each (range, integration time) pair is a
straight line::

    log10(C_max) = slope * log10(V) + intercept   <=>   C_max = A * V**slope

Every published curve has a slope of -1.000, so the model collapses to a
single-coefficient inverse law and only the intercept is stored here::

    C_max(V) = A / V        with        A = 10**intercept


Restrictions
------------
The curves exist only for a discrete set of integration times, and were
measured with the capacitance and leakage integration times set equal.  The
"Referenced Mode" of the QSCV page enforces both restrictions; outside that
mode no maximum capacitance can be derived.

The reference times are additionally gated by the AC line frequency, because
the instrument bounds CINT and IINT in power-line cycles.  With both times
forced equal, only times inside the *intersection* of the two windows are
reachable — see ``supported_integration_times``.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from wizard_4155_4156.models.qscv_config import (
    cap_integration_bounds,
    leak_integration_bounds,
)

__all__ = [
    "REFERENCE_SLOPE",
    "REFERENCE_INTEGRATION_TIMES",
    "REFERENCE_INTERCEPTS",
    "MIN_ACCURATE_CSTEP",
    "supported_integration_times",
    "nearest_supported_time",
    "max_capacitance",
    "format_capacitance",
    "format_integration_time",
]

# Slope shared by every published curve: C_max is inversely proportional to V.
REFERENCE_SLOPE: float = -1.0

# Capacitance measurement voltage below which the manufacturer's capacitance
# accuracy specification no longer applies.
MIN_ACCURATE_CSTEP: float = 0.1  # V

# Integration times covered by the reference curves, longest first (seconds).
REFERENCE_INTEGRATION_TIMES: Tuple[float, ...] = (
    2.0,
    1.0,
    0.5,
    0.3,
    0.1,
    0.05,
    0.03,
)

# Current-range SCPI values, mirroring QSCV_RANGES_4155 / QSCV_RANGES_4156.
_R_10PA: float = 10e-12
_R_100PA: float = 100e-12
_R_1NA: float = 1e-9
_R_10NA: float = 10e-9

# The 10 pA and 100 pA ranges share one published curve set.
_INTERCEPTS_10PA_100PA: Dict[float, float] = {
    2.0: -10.11,
    1.0: -11.69,
    0.5: -12.99,
    0.3: -13.58,
}
_INTERCEPTS_1NA: Dict[float, float] = {
    2.0: -7.819,
    1.0: -8.127,
    0.5: -8.451,
    0.3: -8.876,
    0.1: -9.244,
    0.05: -9.734,
    0.03: -10.430,
}
_INTERCEPTS_10NA: Dict[float, float] = {
    2.0: -7.724,
    1.0: -8.032,
    0.5: -8.353,
    0.3: -8.772,
    0.1: -9.147,
    0.05: -9.633,
    0.03: -10.326,
}

# (range value [A], integration time [s]) -> intercept b;  A = 10**b
REFERENCE_INTERCEPTS: Dict[Tuple[float, float], float] = {
    **{(_R_10PA, t): b for t, b in _INTERCEPTS_10PA_100PA.items()},
    **{(_R_100PA, t): b for t, b in _INTERCEPTS_10PA_100PA.items()},
    **{(_R_1NA, t): b for t, b in _INTERCEPTS_1NA.items()},
    **{(_R_10NA, t): b for t, b in _INTERCEPTS_10NA.items()},
}

# Integration times are compared against a float table, so matches must be
# tolerant of the usual binary-float noise (0.1 + 0.2 style round-trips).
_TIME_REL_TOL: float = 1e-9


def _canonical_time(seconds: float) -> Optional[float]:
    """Snap ``seconds`` onto the reference grid; None when it is off-grid."""
    for t in REFERENCE_INTEGRATION_TIMES:
        if math.isclose(seconds, t, rel_tol=_TIME_REL_TOL):
            return t
    return None


def supported_integration_times(
    range_value: float, line_frequency_hz: int = 50
) -> List[float]:
    """Reference integration times usable for ``range_value``, longest first.

    A time qualifies when the range has a published curve for it *and* the
    value is legal for the capacitance **and** leakage integration windows at
    once — Referenced Mode keeps the two equal, so only their intersection is
    reachable.  At 50 Hz that drops 30 ms (below the 2 PLC CINT minimum); at
    60 Hz it drops both 2 s (above the 100 PLC IINT maximum) and 30 ms.
    """
    cap_lo, cap_hi = cap_integration_bounds(line_frequency_hz)
    leak_lo, leak_hi = leak_integration_bounds(line_frequency_hz)
    lo, hi = max(cap_lo, leak_lo), min(cap_hi, leak_hi)
    return [
        t
        for t in REFERENCE_INTEGRATION_TIMES
        if (range_value, t) in REFERENCE_INTERCEPTS and lo <= t <= hi
    ]


def nearest_supported_time(
    seconds: float, range_value: float, line_frequency_hz: int = 50
) -> Optional[float]:
    """Closest supported reference time to ``seconds`` (None when none exist).

    "Closest" is measured on a log scale: the reference grid spans two decades,
    so a linear distance would bias every entry towards the longest time.
    """
    options = supported_integration_times(range_value, line_frequency_hz)
    if not options:
        return None
    if seconds <= 0:
        return options[0]
    return min(options, key=lambda t: abs(math.log10(t) - math.log10(seconds)))


def max_capacitance(
    range_value: float, integration_time: float, voltage: float
) -> Optional[float]:
    """Maximum measurable capacitance (F) per the manufacturer reference fit.

    Returns None when the voltage is non-positive or the (range, integration
    time) pair has no published curve.
    """
    if voltage <= 0:
        return None
    time = _canonical_time(integration_time)
    if time is None:
        return None
    intercept = REFERENCE_INTERCEPTS.get((range_value, time))
    if intercept is None:
        return None
    return (10.0**intercept) / voltage


# ── Formatting helpers ──────────────────────────────────────────────

_CAP_PREFIXES: Tuple[Tuple[float, str], ...] = (
    (1e-3, "mF"),
    (1e-6, "µF"),
    (1e-9, "nF"),
    (1e-12, "pF"),
    (1e-15, "fF"),
)


def format_capacitance(value: Optional[float]) -> str:
    """Render a capacitance with an SI prefix, e.g. ``7.46 nF``."""
    if value is None or value <= 0 or not math.isfinite(value):
        return "—"
    for scale, suffix in _CAP_PREFIXES:
        if value >= scale:
            return f"{value / scale:.3g} {suffix}"
    return f"{value:.3g} F"


def format_integration_time(seconds: float) -> str:
    """Render a reference integration time, e.g. ``500 ms`` or ``2 s``."""
    if seconds < 1.0:
        return f"{seconds * 1000:.6g} ms"
    return f"{seconds:.6g} s"
