"""
test/models/graph/test_functional.py
------------------------------------
Unit tests for duplicate-X averaging, non-functional detection and
cursor snapping (never interpolated).
"""

import math

import pytest

from wizard_4155_4156.models.graph.functional import (
    nearest_point,
    prepare_function,
)

NAN = float("nan")


# =============================================================================
# prepare_function — functional traces
# =============================================================================


def test_plain_sweep_passes_through_sorted():
    x, y = prepare_function([2.0, 0.0, 1.0], [4.0, 0.0, 1.0])
    assert x == [0.0, 1.0, 2.0]
    assert y == [0.0, 1.0, 4.0]


def test_repeated_acquisitions_average_per_x():
    # Two runs of the same sweep with small noise → averaged function.
    x = [0.0, 1.0, 2.0, 0.0, 1.0, 2.0]
    y = [0.0, 1.0, 2.0, 0.02, 1.02, 2.02]
    out_x, out_y = prepare_function(x, y)
    assert out_x == [0.0, 1.0, 2.0]
    assert out_y == pytest.approx([0.01, 1.01, 2.01])


def test_nan_y_ignored_in_average():
    out_x, out_y = prepare_function([0.0, 0.0, 1.0, 1.0], [1.0, NAN, NAN, NAN])
    assert out_x == [0.0, 1.0]
    assert out_y[0] == 1.0
    assert math.isnan(out_y[1])


def test_nan_x_points_dropped():
    x, y = prepare_function([NAN, 0.0, 1.0], [9.0, 0.0, 1.0])
    assert x == [0.0, 1.0]
    assert y == [0.0, 1.0]


# =============================================================================
# prepare_function — non-functional traces
# =============================================================================


def test_hysteresis_double_sweep_is_non_functional():
    # Up/down sweep where the return branch diverges widely.
    x = [0.0, 1.0, 2.0, 2.0, 1.0, 0.0]
    y = [0.0, 1.0, 2.0, 2.0, 5.0, 8.0]
    assert prepare_function(x, y) is None


def test_single_distinct_x_is_non_functional():
    assert prepare_function([1.0, 1.0, 1.0], [0.0, 0.001, 0.002]) is None


def test_empty_trace_is_non_functional():
    assert prepare_function([], []) is None


def test_spread_within_tolerance_is_functional():
    # 1% spread against a span of 100 → still repeated-acquisition noise.
    x = [0.0, 10.0, 0.0, 10.0]
    y = [0.0, 100.0, 1.0, 99.0]
    assert prepare_function(x, y) is not None


def test_spread_beyond_tolerance_is_non_functional():
    # 50% spread on one x value → structurally multi-valued.
    x = [0.0, 10.0, 0.0]
    y = [0.0, 100.0, 50.0]
    assert prepare_function(x, y) is None


def test_constant_y_duplicates_are_functional():
    x, y = prepare_function([0.0, 0.0, 1.0, 1.0], [5.0, 5.0, 5.0, 5.0])
    assert x == [0.0, 1.0]
    assert y == [5.0, 5.0]


# =============================================================================
# nearest_point
# =============================================================================


@pytest.mark.parametrize(
    ("target", "expected_index"),
    [(-10.0, 0), (0.4, 0), (0.6, 1), (1.4, 1), (99.0, 2)],
)
def test_nearest_point_snaps_to_closest_sample(target, expected_index):
    x = [0.0, 1.0, 2.0]
    y = [0.0, 10.0, 20.0]
    index, sx, sy = nearest_point(x, y, target)
    assert index == expected_index
    assert sx == x[expected_index]
    assert sy == y[expected_index]  # exact sample — never interpolated


def test_nearest_point_skips_non_finite_samples():
    last = 2
    index, sx, sy = nearest_point([0.0, 1.0, 2.0], [0.0, NAN, 20.0], 1.1)
    assert index == last
    assert (sx, sy) == (2.0, 20.0)


def test_nearest_point_requires_finite_data():
    with pytest.raises(ValueError, match="no finite"):
        nearest_point([NAN], [NAN], 0.0)
