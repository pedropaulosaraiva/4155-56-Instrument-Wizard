"""
test/models/graph/test_fitting.py
---------------------------------
Unit tests for the curve-fit registry (linear, polynomial ≤ 6).
"""

import numpy as np
import pytest

from wizard_4155_4156.models.graph.fitting import (
    FIT_MODELS,
    FitError,
    run_fit,
)
from wizard_4155_4156.models.graph.functional import (
    NonFunctionalTraceError,
)

NAN = float("nan")


# =============================================================================
# Registry
# =============================================================================


_MAX_POLY_DEGREE = 6


def test_registry_contains_expected_models():
    assert set(FIT_MODELS) == {"linear", "polynomial"}
    assert not FIT_MODELS["linear"].has_degree
    assert FIT_MODELS["polynomial"].max_degree == _MAX_POLY_DEGREE


# =============================================================================
# Linear
# =============================================================================


def test_linear_recovers_slope_and_intercept():
    x = [0.0, 1.0, 2.0, 3.0]
    y = [1.5, 3.5, 5.5, 7.5]  # y = 2x + 1.5
    outcome = run_fit("linear", 1, x, y)
    assert outcome.coefficients == pytest.approx([2.0, 1.5])
    assert outcome.r_squared == pytest.approx(1.0)
    assert outcome.x == x
    assert outcome.y == pytest.approx(y)


def test_linear_ignores_degree_argument():
    outcome = run_fit("linear", 5, [0.0, 1.0], [0.0, 1.0])
    assert outcome.degree == 1
    assert len(outcome.coefficients) == outcome.degree + 1


def test_equation_text_mentions_x():
    outcome = run_fit("linear", 1, [0.0, 1.0, 2.0], [1.0, 3.0, 5.0])
    assert outcome.equation_text.startswith("y = ")
    assert "x" in outcome.equation_text


# =============================================================================
# Polynomial
# =============================================================================


@pytest.mark.parametrize("degree", [2, 3, 4, 5, 6])
def test_polynomial_recovers_known_coefficients(degree):
    rng = np.linspace(-2.0, 2.0, 50)
    coeffs = np.arange(degree + 1, dtype=float) + 1.0  # [1, 2, …]
    y = np.polyval(coeffs, rng)
    outcome = run_fit("polynomial", degree, rng.tolist(), y.tolist())
    assert outcome.coefficients == pytest.approx(coeffs.tolist(), abs=1e-6)
    assert outcome.r_squared == pytest.approx(1.0)


@pytest.mark.parametrize("degree", [0, 1, 7])
def test_polynomial_degree_out_of_range_raises(degree):
    x = list(range(20))
    y = [float(v) for v in x]
    with pytest.raises(FitError, match="degree"):
        run_fit("polynomial", degree, x, y)


# =============================================================================
# ROI masking / robustness
# =============================================================================


def test_roi_restricts_fit_window():
    # Piecewise: slope 1 up to the knee, slope 10 beyond it.
    knee = 5.0
    x = [float(v) for v in range(11)]
    y = [v if v <= knee else knee + (v - knee) * 10.0 for v in x]
    outcome = run_fit("linear", 1, x, y, x_range=(0.0, knee))
    assert outcome.coefficients[0] == pytest.approx(1.0)
    assert max(outcome.x) <= knee


def test_roi_bounds_order_does_not_matter():
    x = [0.0, 1.0, 2.0, 3.0]
    y = [0.0, 2.0, 4.0, 6.0]
    outcome = run_fit("linear", 1, x, y, x_range=(3.0, 0.0))
    assert outcome.coefficients[0] == pytest.approx(2.0)


def test_nan_y_points_excluded():
    x = [0.0, 1.0, 2.0, 3.0]
    y = [0.0, NAN, 4.0, 6.0]
    outcome = run_fit("linear", 1, x, y)
    assert outcome.coefficients[0] == pytest.approx(2.0)
    assert len(outcome.x) == len(x) - 1


def test_too_few_points_raises():
    with pytest.raises(FitError, match="at least"):
        run_fit("polynomial", 3, [0.0, 1.0, 2.0], [0.0, 1.0, 2.0])


def test_unknown_model_raises():
    with pytest.raises(FitError, match="Unknown"):
        run_fit("exponential", 1, [0.0, 1.0], [0.0, 1.0])


def test_non_functional_source_rejected():
    x = [0.0, 1.0, 1.0, 0.0]
    y = [0.0, 1.0, 5.0, 8.0]
    with pytest.raises(NonFunctionalTraceError):
        run_fit("linear", 1, x, y)


def test_duplicate_x_source_averaged_before_fit():
    # Two noisy acquisitions of y = 3x + 1.
    x = [0.0, 1.0, 2.0] * 2
    y = [1.0, 4.0, 7.0, 1.0, 4.0, 7.0]
    outcome = run_fit("linear", 1, x, y)
    assert outcome.coefficients == pytest.approx([3.0, 1.0])
