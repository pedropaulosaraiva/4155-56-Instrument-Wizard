"""
models/graph/fitting.py
-----------------------
Registry of curve-fit models (linear, polynomial up to degree 6).

Adding a model is one ``FitModelSpec`` entry in ``FIT_MODELS`` — the
Analysis tab renders its model combo from the registry, so no UI change
is needed (same pattern as ``trace_math.OPERATIONS``).

``run_fit`` masks the source to the ROI x-range when one is given,
normalizes it through ``functional.prepare_function`` (duplicate-x
averaging; non-functional sources are rejected) and evaluates the fitted
polynomial back on the source x grid so the fit overlays exactly where
it was computed.

No PySide6 / pyqtgraph imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wizard_4155_4156.models.graph.functional import (
    NonFunctionalTraceError,
    prepare_function,
)


class FitError(ValueError):
    """Raised when a fit cannot be computed (too few points…)."""


@dataclass(frozen=True)
class FitModelSpec:
    """One fit model offered by the Analysis tab."""

    model_id: str
    label: str
    has_degree: bool  # False → the degree spinbox is hidden/ignored
    min_degree: int
    max_degree: int


#: Registry — insertion order drives the model combo order.
FIT_MODELS: dict[str, FitModelSpec] = {
    spec.model_id: spec
    for spec in (
        FitModelSpec("linear", "Linear", False, 1, 1),
        FitModelSpec("polynomial", "Polynomial", True, 2, 6),
    )
}


@dataclass(frozen=True)
class FitOutcome:
    """Result of one fit: the overlay trace plus reporting metadata."""

    model_id: str
    degree: int
    coefficients: list[float]  # np.polyfit order: highest power first
    equation_text: str
    r_squared: float
    x: list[float]
    y: list[float]


def _format_equation(coefficients: np.ndarray) -> str:
    """Human-readable polynomial, highest power first (y = a·x² + b…)."""
    degree = coefficients.size - 1
    terms: list[str] = []
    for power, coeff in zip(range(degree, -1, -1), coefficients):
        magnitude = f"{abs(coeff):.4g}"
        if power > 1:
            term = f"{magnitude}·x^{power}"
        elif power == 1:
            term = f"{magnitude}·x"
        else:
            term = magnitude
        sign = "−" if coeff < 0 else "+"
        terms.append(
            f"{sign} {term}" if terms else (f"−{term}" if coeff < 0 else term)
        )
    return "y = " + " ".join(terms)


def _r_squared(y: np.ndarray, y_fit: np.ndarray) -> float:
    residual = float(np.sum((y - y_fit) ** 2))
    total = float(np.sum((y - y.mean()) ** 2))
    if total == 0.0:
        return 1.0 if residual == 0.0 else 0.0
    return 1.0 - residual / total


def run_fit(
    model_id: str,
    degree: int,
    x: list[float],
    y: list[float],
    x_range: tuple[float, float] | None = None,
) -> FitOutcome:
    """
    Fit *model_id* over the (optionally ROI-restricted) trace.

    Raises ``FitError`` for unknown models / bad degrees / too few
    points and ``NonFunctionalTraceError`` for non-functional sources.
    """
    spec = FIT_MODELS.get(model_id)
    if spec is None:
        raise FitError(f"Unknown fit model: {model_id}")
    if not spec.has_degree:
        degree = spec.min_degree
    if not spec.min_degree <= degree <= spec.max_degree:
        raise FitError(
            f"{spec.label} degree must be between "
            f"{spec.min_degree} and {spec.max_degree}"
        )

    prepared = prepare_function(x, y)
    if prepared is None:
        raise NonFunctionalTraceError("Source trace is not a function of X")
    xs = np.asarray(prepared[0])
    ys = np.asarray(prepared[1])

    mask = np.isfinite(ys)
    if x_range is not None:
        lo, hi = min(x_range), max(x_range)
        mask &= (xs >= lo) & (xs <= hi)
    xs, ys = xs[mask], ys[mask]

    if xs.size < degree + 1:
        raise FitError(
            f"Need at least {degree + 1} points inside the fit range, "
            f"found {xs.size}"
        )

    coefficients = np.polyfit(xs, ys, degree)
    y_fit = np.polyval(coefficients, xs)
    return FitOutcome(
        model_id=model_id,
        degree=degree,
        coefficients=coefficients.tolist(),
        equation_text=_format_equation(coefficients),
        r_squared=_r_squared(ys, y_fit),
        x=xs.tolist(),
        y=y_fit.tolist(),
    )
