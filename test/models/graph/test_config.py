"""
test/models/graph/test_config.py
--------------------------------
Unit tests for multipliers, units, ranges, compatibility and the
scene/plot serialization round-trip.
"""

import json

import pytest

from wizard_4155_4156.models.graph.config import (
    GRID_MAX,
    MULTIPLIER_FACTORS,
    MULTIPLIERS,
    PLOT_SLOTS,
    AxisConfig,
    Multiplier,
    SceneConfig,
    axis_label,
    axis_scale,
    compute_axis_range,
    infer_unit,
    variables_compatible,
)
from wizard_4155_4156.models.graph.trace import (
    Trace,
    TraceKind,
    TraceStyle,
    traces_to_dataset,
)

NAN = float("nan")


# =============================================================================
# Multipliers & units
# =============================================================================


def test_multiplier_factors_cover_all_members():
    assert set(MULTIPLIER_FACTORS) == set(Multiplier)
    assert set(MULTIPLIERS) == set(Multiplier)


@pytest.mark.parametrize(
    ("multiplier", "factor"),
    [
        (Multiplier.PICO, 1e-12),
        (Multiplier.MILLI, 1e-3),
        (Multiplier.NONE, 1.0),
        (Multiplier.MEGA, 1e6),
    ],
)
def test_axis_scale_is_reciprocal_of_factor(multiplier, factor):
    # 1 mA with the "m" multiplier must display as tick "1" → scale 1e3.
    assert axis_scale(multiplier) == pytest.approx(1.0 / factor)


@pytest.mark.parametrize(
    ("name", "unit"),
    [
        ("V1", "V"),
        ("VMU2", "V"),
        ("VSU1", "V"),
        ("I3", "A"),
        ("@TIME", "s"),
        ("@INDEX", ""),
    ],
)
def test_infer_unit(name, unit):
    assert infer_unit(name) == unit


def test_axis_label_bakes_multiplier_prefix():
    assert axis_label("I1", Multiplier.MILLI) == "I1 (mA)"
    assert axis_label("V2", Multiplier.NONE) == "V2 (V)"
    assert axis_label("@INDEX", Multiplier.NONE) == "@INDEX"


# =============================================================================
# Compatibility & ranges
# =============================================================================


def test_variables_compatible_is_set_equality():
    assert variables_compatible(["V1", "I1"], ["I1", "V1"])
    assert not variables_compatible(["V1", "I1"], ["V1", "I2"])


def test_compute_axis_range_pads_linear():
    data_lo, data_hi = 0.0, 10.0
    lo, hi = compute_axis_range([data_lo, data_hi], log=False)
    assert lo < data_lo
    assert hi > data_hi


def test_compute_axis_range_drops_non_positive_for_log():
    data_hi = 100.0
    lo, hi = compute_axis_range([-5.0, 0.0, 1.0, data_hi], log=True)
    assert lo > 0.0
    assert lo < 1.0
    assert hi > data_hi


def test_compute_axis_range_handles_empty_and_nan():
    assert compute_axis_range([NAN], log=False) == (0.0, 1.0)
    lo, hi = compute_axis_range([], log=True)
    assert lo > 0.0
    assert hi > lo


def test_compute_axis_range_single_value():
    value = 5.0
    lo, hi = compute_axis_range([value], log=False)
    assert lo < value < hi


# =============================================================================
# Serialization round-trip
# =============================================================================


_ACTIVE_SLOT = 4


def _sample_scene() -> SceneConfig:
    scene = SceneConfig(
        name="Compare", rows=2, cols=3, active_index=_ACTIVE_SLOT
    )
    plot = scene.plots[_ACTIVE_SLOT]
    plot.title = "Transfer"
    plot.x_var = "V1"
    plot.y_var = "I1"
    plot.axis_y = AxisConfig(
        auto_scale=False,
        log=True,
        min_val=1e-9,
        max_val=1e-3,
        multiplier=Multiplier.NONE,
    )
    plot.axis_x = AxisConfig(multiplier=Multiplier.MILLI, label="Gate V")
    plot.selected_exec_ids = [3, 7]
    plot.roi_enabled = True
    plot.roi = (0.2, 0.8)
    plot.next_calc_id = 3
    plot.next_fit_id = 2
    plot.traces = [
        Trace(id="exec:3", name="I1 run A", source_exec_id=3),
        Trace(
            id="calc:1",
            name="gm",
            kind=TraceKind.COMPUTED,
            style=TraceStyle(color="#ff0000", line_style="dash"),
            definition={"op_id": "dy_dx", "sources": ["exec:3"]},
        ),
        Trace(
            id="fit:1",
            name="linear fit",
            kind=TraceKind.FIT,
            definition={
                "model_id": "linear",
                "degree": 1,
                "source": "calc:1",
                "x_range": [0.2, 0.8],
            },
        ),
    ]
    return scene


def test_scene_round_trip_through_json():
    scene = _sample_scene()
    payload = json.loads(json.dumps(scene.to_dict()))
    restored = SceneConfig.from_dict(payload)

    assert restored.name == "Compare"
    assert (restored.rows, restored.cols) == (2, 3)
    assert restored.active_index == _ACTIVE_SLOT
    assert len(restored.plots) == PLOT_SLOTS

    plot = restored.plots[_ACTIVE_SLOT]
    assert plot.title == "Transfer"
    assert (plot.x_var, plot.y_var) == ("V1", "I1")
    assert plot.axis_y.log
    assert not plot.axis_y.auto_scale
    assert plot.axis_y.min_val == pytest.approx(1e-9)
    assert plot.axis_x.multiplier is Multiplier.MILLI
    assert plot.axis_x.label == "Gate V"
    assert plot.selected_exec_ids == [3, 7]
    assert plot.roi == (0.2, 0.8)
    assert (plot.next_calc_id, plot.next_fit_id) == (3, 2)


def test_traces_persist_definitions_but_never_points():
    scene = _sample_scene()
    scene.plots[_ACTIVE_SLOT].traces[0].x = [0.0, 1.0]
    scene.plots[_ACTIVE_SLOT].traces[0].y = [0.0, 1.0]
    payload = scene.to_dict()

    serialized = payload["plots"][_ACTIVE_SLOT]["traces"]
    assert all("x" not in t and "y" not in t for t in serialized)

    restored = SceneConfig.from_dict(payload).plots[_ACTIVE_SLOT].traces
    assert restored[0].kind is TraceKind.DATA
    assert (
        restored[0].source_exec_id
        == scene.plots[_ACTIVE_SLOT].selected_exec_ids[0]
    )
    assert restored[1].kind is TraceKind.COMPUTED
    assert restored[1].definition["op_id"] == "dy_dx"
    assert restored[1].style.color == "#ff0000"
    assert restored[2].kind is TraceKind.FIT
    assert restored[2].definition["model_id"] == "linear"
    assert restored[0].x == []  # rebuilt from the DB, not persisted


def test_from_dict_tolerates_missing_and_unknown_keys():
    restored = SceneConfig.from_dict(
        {"name": "S", "future_key": True, "plots": [{"whatever": 1}]}
    )
    assert restored.name == "S"
    assert len(restored.plots) == PLOT_SLOTS
    assert restored.plots[0].mouse_mode == "pan"


# =============================================================================
# Grid geometry
# =============================================================================


def test_visible_indices_are_row_major_into_3x3_slots():
    scene = SceneConfig(rows=2, cols=2)
    assert scene.visible_indices() == [0, 1, GRID_MAX, GRID_MAX + 1]


def test_cell_config_survives_grid_shrink_and_regrow():
    corner = PLOT_SLOTS - 1
    scene = SceneConfig(rows=3, cols=3)
    scene.plots[corner].title = "corner"
    scene.rows = scene.cols = 1
    assert corner not in scene.visible_indices()
    scene.rows = scene.cols = 3
    assert scene.plots[corner].title == "corner"


# =============================================================================
# traces_to_dataset (CSV export bridge)
# =============================================================================


def test_traces_to_dataset_two_columns_per_trace():
    traces = [
        Trace(id="exec:1", name="I1", x=[0.0, 1.0], y=[5.0, 6.0]),
        Trace(id="calc:1", name="I1", x=[0.0], y=[9.0]),  # name clash
    ]
    dataset = traces_to_dataset(traces)
    assert list(dataset) == ["I1 [x]", "I1 [y]", "I1 (2) [x]", "I1 (2) [y]"]
    assert dataset["I1 [y]"] == [5.0, 6.0]
    assert dataset["I1 (2) [y]"] == [9.0]
