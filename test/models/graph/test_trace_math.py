"""
test/models/graph/test_trace_math.py
------------------------------------
Unit tests for the trace-operation registry (derivative, unary, binary).
"""

import math

import pytest

from wizard_4155_4156.models.graph.functional import (
    NonFunctionalTraceError,
)
from wizard_4155_4156.models.graph.trace_math import (
    OPERATIONS,
    OpCategory,
    TraceMathError,
    apply_operation,
    operations_in,
)

NAN = float("nan")


# =============================================================================
# Registry
# =============================================================================


def test_every_category_has_operations():
    for category in OpCategory:
        assert operations_in(category), category


def test_arity_matches_category():
    for op in OPERATIONS.values():
        expected = 2 if op.category is OpCategory.BINARY else 1
        assert op.arity == expected


# =============================================================================
# Derivative
# =============================================================================


def test_derivative_of_line_is_constant_slope():
    x = [0.0, 1.0, 2.0, 3.0]
    y = [1.0, 3.0, 5.0, 7.0]
    out_x, out_y = apply_operation("dy_dx", [(x, y)])
    assert out_x == x
    assert out_y == pytest.approx([2.0, 2.0, 2.0, 2.0])


def test_derivative_on_non_uniform_grid():
    # y = x² on an uneven grid: dy/dx == 2x at interior points.
    x = [0.0, 1.0, 3.0, 4.0]
    y = [v**2 for v in x]
    _, out_y = apply_operation("dy_dx", [(x, y)])
    assert out_y[1] == pytest.approx(2.0, abs=1e-9)
    assert out_y[2] == pytest.approx(6.0, abs=1e-9)


# =============================================================================
# Unary operations
# =============================================================================


@pytest.mark.parametrize(
    ("op_id", "y_in", "y_expected"),
    [
        ("abs", [-1.0, 2.0], [1.0, 2.0]),
        ("negate", [-1.0, 2.0], [1.0, -2.0]),
        ("log10", [-100.0, 10.0], [2.0, 1.0]),  # log10 of |y|
        ("ln_abs", [-math.e, 1.0], [1.0, 0.0]),  # ln of |y|
        ("sqrt", [4.0, 9.0], [2.0, 3.0]),
        ("square", [3.0, -2.0], [9.0, 4.0]),
        ("reciprocal", [2.0, 4.0], [0.5, 0.25]),
        ("inv_square", [2.0, -4.0], [0.25, 0.0625]),
    ],
)
def test_unary_operations(op_id, y_in, y_expected):
    out_x, out_y = apply_operation(op_id, [([0.0, 1.0], y_in)])
    assert out_x == [0.0, 1.0]
    assert out_y == pytest.approx(y_expected)


@pytest.mark.parametrize(
    ("op_id", "y_in"),
    [
        ("log10", [0.0, 1.0]),  # log10(0) → nan, not -inf
        ("ln_abs", [0.0, 1.0]),  # ln(0) → nan, not -inf
        ("sqrt", [-4.0, 1.0]),  # sqrt of negative → nan
        ("reciprocal", [0.0, 1.0]),  # 1/0 → nan, not inf
        ("inv_square", [0.0, 1.0]),  # 1/0² → nan, not inf
    ],
)
def test_unary_invalid_inputs_become_nan(op_id, y_in):
    _, out_y = apply_operation(op_id, [([0.0, 1.0], y_in)])
    assert math.isnan(out_y[0])
    assert math.isfinite(out_y[1])


# =============================================================================
# Binary operations
# =============================================================================


def test_binary_on_identical_grids():
    x = [0.0, 1.0, 2.0]
    a = [1.0, 2.0, 3.0]
    b = [10.0, 20.0, 30.0]
    _, added = apply_operation("add", [(x, a), (x, b)])
    _, divided = apply_operation("divide", [(x, a), (x, b)])
    assert added == pytest.approx([11.0, 22.0, 33.0])
    assert divided == pytest.approx([0.1, 0.1, 0.1])


def test_binary_interpolates_b_onto_a_overlap():
    # A on [0..3], B on [1..5] → result restricted to [1..3] on A's grid.
    xa = [0.0, 1.0, 2.0, 3.0]
    ya = [0.0, 0.0, 0.0, 0.0]
    xb = [1.0, 3.0, 5.0]
    yb = [10.0, 30.0, 50.0]  # linear: y = 10·x
    out_x, out_y = apply_operation("add", [(xa, ya), (xb, yb)])
    assert out_x == [1.0, 2.0, 3.0]
    assert out_y == pytest.approx([10.0, 20.0, 30.0])


def test_binary_without_overlap_raises():
    with pytest.raises(TraceMathError, match="overlap"):
        apply_operation(
            "add",
            [([0.0, 1.0], [0.0, 0.0]), ([5.0, 6.0], [0.0, 0.0])],
        )


def test_divide_by_zero_becomes_nan():
    x = [0.0, 1.0]
    _, out_y = apply_operation("divide", [(x, [1.0, 1.0]), (x, [0.0, 2.0])])
    assert math.isnan(out_y[0])
    assert out_y[1] == pytest.approx(0.5)


# =============================================================================
# Error handling
# =============================================================================


def test_unknown_operation_raises():
    with pytest.raises(TraceMathError, match="Unknown"):
        apply_operation("fft", [([0.0, 1.0], [0.0, 1.0])])


def test_wrong_arity_raises():
    with pytest.raises(TraceMathError, match="source trace"):
        apply_operation("add", [([0.0, 1.0], [0.0, 1.0])])


def test_non_functional_source_rejected():
    x = [0.0, 1.0, 1.0, 0.0]  # hysteresis-style
    y = [0.0, 1.0, 5.0, 8.0]
    with pytest.raises(NonFunctionalTraceError):
        apply_operation("dy_dx", [(x, y)])


def test_duplicate_x_source_is_averaged_then_processed():
    # Repeated acquisition of y = 2x → derivative ≈ 2 after averaging.
    x = [0.0, 1.0, 2.0, 0.0, 1.0, 2.0]
    y = [0.0, 2.0, 4.0, 0.0, 2.0, 4.0]
    out_x, out_y = apply_operation("dy_dx", [(x, y)])
    assert out_x == [0.0, 1.0, 2.0]
    assert out_y == pytest.approx([2.0, 2.0, 2.0])
