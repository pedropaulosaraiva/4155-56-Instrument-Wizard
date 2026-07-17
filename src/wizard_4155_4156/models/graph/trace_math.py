"""
models/graph/trace_math.py
--------------------------
Registry of trace operations (derivative / unary / binary).

Adding a new operation is one ``OpSpec`` entry in ``OPERATIONS`` — the
Analysis tab builds its combos from the registry, so no UI change is
required (same pattern as ``models/data_export.FORMATS``).

Every operation first normalizes its sources through
``functional.prepare_function`` (duplicate-x averaging); a non-functional
source raises ``NonFunctionalTraceError``.  Binary operations align
mismatched x grids by interpolating B onto A's x over the overlapping
range (required by FR-6.3 of ``graph_page_requirements.md``); the
"never interpolate" rule applies to cursors only.

No PySide6 / pyqtgraph imports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from wizard_4155_4156.models.graph.functional import (
    NonFunctionalTraceError,
    prepare_function,
)

XY = tuple[list[float], list[float]]


class TraceMathError(ValueError):
    """Raised when an operation cannot be applied (arity, overlap…)."""


class OpCategory(StrEnum):
    """Analysis-tab grouping of the operations."""

    DERIVATIVE = "derivative"
    UNARY = "unary"
    BINARY = "binary"


@dataclass(frozen=True)
class OpSpec:
    """One trace operation.

    ``name_template`` builds the default computed-trace name from the
    source trace names (``{a}`` and, for binary ops, ``{b}``).
    """

    op_id: str
    label: str
    category: OpCategory
    arity: int
    name_template: str
    func: Callable[..., np.ndarray]


def _with_nan_guard(values: np.ndarray) -> np.ndarray:
    """Replace non-finite results (1/0, log of <=0 …) with nan."""
    values = np.asarray(values, dtype=float)
    values[~np.isfinite(values)] = np.nan
    return values


def _derivative(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return _with_nan_guard(np.gradient(y, x))


def _unary(transform: Callable[[np.ndarray], np.ndarray]) -> Callable:
    def apply(_x: np.ndarray, y: np.ndarray) -> np.ndarray:
        with np.errstate(all="ignore"):
            return _with_nan_guard(transform(y))

    return apply


def _binary(combine: Callable[[np.ndarray, np.ndarray], np.ndarray]):
    def apply(_x: np.ndarray, ya: np.ndarray, yb: np.ndarray) -> np.ndarray:
        with np.errstate(all="ignore"):
            return _with_nan_guard(combine(ya, yb))

    return apply


#: Registry — insertion order drives the Analysis-tab combo order.
OPERATIONS: dict[str, OpSpec] = {
    spec.op_id: spec
    for spec in (
        OpSpec(
            "dy_dx",
            "dY/dX",
            OpCategory.DERIVATIVE,
            1,
            "d({a})/dx",
            _derivative,
        ),
        OpSpec("abs", "|Y|", OpCategory.UNARY, 1, "|{a}|", _unary(np.abs)),
        OpSpec(
            "negate",
            "-Y",
            OpCategory.UNARY,
            1,
            "-({a})",
            _unary(np.negative),
        ),
        OpSpec(
            "log10",
            "log10|Y|",
            OpCategory.UNARY,
            1,
            "log10|{a}|",
            _unary(lambda y: np.log10(np.abs(y))),
        ),
        OpSpec(
            "ln_abs",
            "ln|Y|",
            OpCategory.UNARY,
            1,
            "ln|{a}|",
            _unary(lambda y: np.log(np.abs(y))),
        ),
        OpSpec(
            "sqrt",
            "√Y",
            OpCategory.UNARY,
            1,
            "sqrt({a})",
            _unary(np.sqrt),
        ),
        OpSpec(
            "square",
            "Y²",
            OpCategory.UNARY,
            1,
            "({a})²",
            _unary(np.square),
        ),
        OpSpec(
            "reciprocal",
            "1/Y",
            OpCategory.UNARY,
            1,
            "1/({a})",
            _unary(lambda y: 1.0 / y),
        ),
        OpSpec(
            "inv_square",
            "1/Y²",
            OpCategory.UNARY,
            1,
            "1/({a})²",
            _unary(lambda y: 1.0 / np.square(y)),
        ),
        OpSpec(
            "add",
            "A + B",
            OpCategory.BINARY,
            2,
            "{a} + {b}",
            _binary(np.add),
        ),
        OpSpec(
            "subtract",
            "A − B",
            OpCategory.BINARY,
            2,
            "{a} − {b}",
            _binary(np.subtract),
        ),
        OpSpec(
            "multiply",
            "A × B",
            OpCategory.BINARY,
            2,
            "{a} × {b}",
            _binary(np.multiply),
        ),
        OpSpec(
            "divide",
            "A ÷ B",
            OpCategory.BINARY,
            2,
            "{a} ÷ {b}",
            _binary(np.divide),
        ),
    )
}


def operations_in(category: OpCategory) -> list[OpSpec]:
    """Registry entries of one category, in declaration order."""
    return [op for op in OPERATIONS.values() if op.category is category]


def _prepare(x, y) -> tuple[np.ndarray, np.ndarray]:
    prepared = prepare_function(x, y)
    if prepared is None:
        raise NonFunctionalTraceError("Source trace is not a function of X")
    return np.asarray(prepared[0]), np.asarray(prepared[1])


def _align(
    xa: np.ndarray,
    ya: np.ndarray,
    xb: np.ndarray,
    yb: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A's grid restricted to the x overlap, with B interpolated onto it."""
    if xa.size == xb.size and np.allclose(xa, xb):
        return xa, ya, yb
    lo = max(float(xa[0]), float(xb[0]))
    hi = min(float(xa[-1]), float(xb[-1]))
    if lo > hi:
        raise TraceMathError("Traces have no overlapping X range")
    inside = (xa >= lo) & (xa <= hi)
    finite_b = np.isfinite(yb)
    if finite_b.sum() < 2:  # noqa: PLR2004 — np.interp needs two points
        raise TraceMathError("Second trace has too few finite points")
    yb_on_a = np.interp(xa[inside], xb[finite_b], yb[finite_b])
    return xa[inside], ya[inside], yb_on_a


def apply_operation(op_id: str, sources: list[XY]) -> XY:
    """
    Run a registered operation over prepared sources.

    ``sources`` holds the raw (x, y) arrays of the selected trace(s);
    each is normalized via ``prepare_function`` first.  Returns the new
    trace's (x, y).  Raises ``NonFunctionalTraceError`` for ineligible
    sources and ``TraceMathError`` for arity/alignment problems.
    """
    spec = OPERATIONS.get(op_id)
    if spec is None:
        raise TraceMathError(f"Unknown operation: {op_id}")
    if len(sources) != spec.arity:
        raise TraceMathError(
            f"{spec.label} needs {spec.arity} source trace(s), "
            f"got {len(sources)}"
        )

    prepared = [_prepare(x, y) for x, y in sources]
    if spec.arity == 1:
        x, y = prepared[0]
        return x.tolist(), spec.func(x, y).tolist()

    xa, ya = prepared[0]
    xb, yb = prepared[1]
    x, ya, yb_on_a = _align(xa, ya, xb, yb)
    return x.tolist(), spec.func(x, ya, yb_on_a).tolist()
