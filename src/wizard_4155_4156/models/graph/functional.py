"""
models/graph/functional.py
--------------------------
Turning raw measurement traces into mathematical *functions*.

A captured trace is just an ordered cloud of (x, y) points; math and curve
fitting require y = f(x).  Two special cases exist:

* **Repeated acquisitions** — the same sweep captured several times, so
  multiple y values exist for one x purely from repetition/noise.  These
  collapse into a valid function by averaging y per distinct x.
* **Non-functional traces** — multiple y values per x for *structural*
  reasons (hysteresis double sweep, y transitioning while x is held).
  These must never feed trace math or fitting.

The discriminator is the y **spread** inside each duplicate-x group: noise
from repeated acquisitions stays small against the full y span of the trace,
while hysteresis-style branches diverge widely.  ``prepare_function``
returns ``None`` when any group's spread exceeds ``rel_tolerance`` of the
global y span (see its docstring for the exact rule, pinned by unit tests).

No PySide6 / pyqtgraph imports.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

#: A duplicate-x group whose y spread exceeds this fraction of the whole
#: trace's y span marks the trace as non-functional (not mere noise).
REL_SPREAD_TOLERANCE = 0.05

#: Fewer distinct x values than this cannot form a usable function.
_MIN_DISTINCT_X = 2


class NonFunctionalTraceError(ValueError):
    """Raised when a trace cannot be treated as y = f(x)."""


def prepare_function(
    x: Sequence[float],
    y: Sequence[float],
    *,
    rel_tolerance: float = REL_SPREAD_TOLERANCE,
) -> tuple[list[float], list[float]] | None:
    """
    Normalize a raw trace into a function: sorted, one y per distinct x.

    Rules (pinned by ``test_functional.py``):

    1. Points with a non-finite x are dropped (they cannot be placed on
       the axis).  Non-finite y values survive grouping but are ignored
       when averaging; a group with no finite y yields ``nan``.
    2. Duplicate x values are collapsed by **averaging** their finite y
       values (repeated-acquisition case).
    3. The trace is **non-functional** (returns ``None``) when either:
       - fewer than two distinct finite x values exist, or
       - any duplicate-x group has a y spread (max - min of its finite
         y values) greater than ``rel_tolerance`` × the global finite
         y span.  A zero global span never trips this rule.
    4. The result is sorted by ascending x.
    """
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    n = min(xs.size, ys.size)
    xs, ys = xs[:n], ys[:n]

    keep = np.isfinite(xs)
    xs, ys = xs[keep], ys[keep]

    distinct, inverse = np.unique(xs, return_inverse=True)
    if distinct.size < _MIN_DISTINCT_X:
        return None

    finite_y = ys[np.isfinite(ys)]
    span = float(finite_y.max() - finite_y.min()) if finite_y.size else 0.0

    out_y = np.empty(distinct.size, dtype=float)
    for group in range(distinct.size):
        group_y = ys[inverse == group]
        group_finite = group_y[np.isfinite(group_y)]
        if group_finite.size == 0:
            out_y[group] = math.nan
            continue
        spread = float(group_finite.max() - group_finite.min())
        if span > 0.0 and spread > rel_tolerance * span:
            return None
        out_y[group] = float(group_finite.mean())

    return distinct.tolist(), out_y.tolist()


def nearest_point(
    x: Sequence[float],
    y: Sequence[float],
    target_x: float,
) -> tuple[int, float, float]:
    """
    The data point whose x is closest to *target_x* — never interpolated.

    Only points where both x and y are finite qualify (a cursor must sit
    on a drawable point).  Returns ``(index, x, y)`` into the original
    arrays.  Raises ``ValueError`` when the trace has no finite points.
    """
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    n = min(xs.size, ys.size)
    xs, ys = xs[:n], ys[:n]

    valid = np.isfinite(xs) & np.isfinite(ys)
    if not valid.any():
        raise ValueError("Trace has no finite data points")

    distances = np.abs(xs - float(target_x))
    distances[~valid] = math.inf
    index = int(distances.argmin())
    return index, float(xs[index]), float(ys[index])
