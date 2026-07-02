"""
Tests for models/execution_time.py — estimated run duration (min–max interval,
or Indeterminate) for the Sweep, QSCV and Sampling methods.
"""

import pytest

from wizard_4155_4156.models.execution_time import (
    _adjusted_interval,
    _sweep_total_indexes,
    _sweep_voltage_ranges_by_unit,
    format_execution_time,
    qscv_execution_time_range,
    sampling_execution_time_range,
    sweep_execution_time_range,
)
from wizard_4155_4156.models.qscv_config import QscvConfig, QscvVar1Config
from wizard_4155_4156.models.sampling_config import (
    PeriodMode,
    SamplingConfig,
    SamplingMode,
)
from wizard_4155_4156.models.sweep_config import (
    IntegrationMode,
    SweepConfig,
    VAR1Mode,
)

PLC50 = 0.02  # 1 PLC at 50 Hz
_VAR1_POINTS = 11  # var1 0 → 1 V, step 0.1 → 11 points


# ── Helpers ──────────────────────────────────────────────────────────────────


def _smu(idx=1, mode="V", function="CONST"):
    return {
        "id": f"SMU{idx}",
        "unit_type": "SMU",
        "function": function,
        "mode": mode,
        "v_name": f"V{idx}",
        "i_name": f"I{idx}",
    }


def _sweep_cfg(**overrides):
    cfg = SweepConfig()
    cfg.measurement_setup.integration_mode = IntegrationMode.MED
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "AUTO"}}
    cfg.display_vars = ["I1"]
    cfg.hold_time = 0.5
    cfg.delay = 0.0
    cfg.var1.start = 0.0
    cfg.var1.stop = 1.0
    cfg.var1.step = 0.1  # LINEAR → 11 points
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


# ── Sweep: total indexes ─────────────────────────────────────────────────────


def test_sweep_total_indexes_single_no_var2():
    cfg = _sweep_cfg()
    assert _sweep_total_indexes(cfg, [_smu(function="VAR1")]) == _VAR1_POINTS


def test_sweep_total_indexes_double():
    cfg = _sweep_cfg()
    cfg.var1.mode = VAR1Mode.DOUBLE
    indexes = _sweep_total_indexes(cfg, [_smu(function="VAR1")])
    assert indexes == 2 * _VAR1_POINTS


def test_sweep_total_indexes_with_var2():
    cfg = _sweep_cfg()
    cfg.var2.n_of_steps = 3
    channels = [_smu(1, function="VAR1"), _smu(2, function="VAR2")]
    # ×n_of_steps, no +1
    assert _sweep_total_indexes(cfg, channels) == _VAR1_POINTS * 3


def test_sweep_total_indexes_none_when_step_invalid():
    cfg = _sweep_cfg()
    cfg.var1.step = 0.0
    assert _sweep_total_indexes(cfg, [_smu(function="VAR1")]) is None


# ── Sweep: output voltage range span ─────────────────────────────────────────


def test_sweep_span_var1_crossing_zero():
    # A V-sweep from −5 V to +5 V traverses the 2 V and 20 V output ranges.
    cfg = _sweep_cfg()
    cfg.var1.start = -5.0
    cfg.var1.stop = 5.0
    spans = _sweep_voltage_ranges_by_unit(
        cfg, [_smu(function="VAR1", mode="V")]
    )
    assert spans["SMU1"] == [2.0, 20.0]


def test_sweep_span_var1_narrow_single_range():
    cfg = _sweep_cfg()  # 0 → 1 V stays inside the 2 V range
    spans = _sweep_voltage_ranges_by_unit(
        cfg, [_smu(function="VAR1", mode="V")]
    )
    assert spans["SMU1"] == [2.0]


def test_sweep_span_const_from_source():
    cfg = _sweep_cfg()
    cfg.constants = {"SMU1": {"source": 30.0, "compliance": 0.01}}
    spans = _sweep_voltage_ranges_by_unit(
        cfg, [_smu(function="CONST", mode="V")]
    )
    assert spans["SMU1"] == [40.0]  # smallest range covering 30 V


def test_sweep_span_var2_source():
    cfg = _sweep_cfg()
    cfg.var2.start = 0.0
    cfg.var2.step = 10.0
    cfg.var2.n_of_steps = 3  # 0 → 30 V
    spans = _sweep_voltage_ranges_by_unit(
        cfg, [_smu(2, function="VAR2", mode="V")]
    )
    assert spans["SMU2"] == [2.0, 20.0, 40.0]


def test_sweep_span_vard_source():
    cfg = _sweep_cfg()
    cfg.var1.start = 0.0
    cfg.var1.stop = 2.0
    cfg.vard.ratio = 10.0
    cfg.vard.offset = 0.0  # output 0 → 20 V
    spans = _sweep_voltage_ranges_by_unit(
        cfg, [_smu(function="VAR1'", mode="V")]
    )
    assert spans["SMU1"] == [2.0, 20.0]


def test_sweep_span_excludes_voltage_measuring_smu():
    # An I-mode source measures voltage → no current-range/voltage span entry.
    cfg = _sweep_cfg()
    spans = _sweep_voltage_ranges_by_unit(
        cfg, [_smu(function="VAR1", mode="I")]
    )
    assert spans == {}


# ── Sweep: execution time ────────────────────────────────────────────────────


def test_sweep_execution_time_interval():
    # MPSMU AUTO current in MED spans 0.04–0.12 s; 11 indexes; hold 0.5.
    cfg = _sweep_cfg()
    lo, hi = sweep_execution_time_range(
        cfg, [_smu(function="VAR1")], "4155C", 50
    )
    assert lo == pytest.approx(0.5 + 0.04 * 11)
    assert hi == pytest.approx(0.5 + 0.12 * 11)


def test_sweep_execution_time_voltage_only_collapses():
    # I-mode source measures voltage → single-valued interval.
    cfg = _sweep_cfg()
    cfg.display_vars = ["V1"]
    lo, hi = sweep_execution_time_range(
        cfg, [_smu(function="VAR1", mode="I")], "4155C", 50
    )
    expected = 0.5 + (2 * PLC50) * 11  # MED voltage = 2·plc
    assert lo == hi == pytest.approx(expected)


def test_sweep_execution_time_includes_delay():
    cfg = _sweep_cfg()
    cfg.delay = 0.01
    lo, _ = sweep_execution_time_range(
        cfg, [_smu(function="VAR1")], "4155C", 50
    )
    assert lo == pytest.approx(0.5 + (0.01 + 0.04) * 11)


# ── QSCV ─────────────────────────────────────────────────────────────────────


def _qscv_cfg(**overrides):
    cfg = QscvConfig(
        cap_integration_time=0.1,
        leak_integration_time=0.05,
        delay=0.0,
        hold_time=0.5,
        var1=QscvVar1Config(start=0.0, stop=10.0, step=1.0),  # 9 steps
    )
    cfg.display_vars = ["C"]
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


def test_qscv_capacitance_only():
    cfg = _qscv_cfg()
    lo, hi = qscv_execution_time_range(cfg)
    assert lo == hi == pytest.approx(0.5 + 0.1 * 9)


def test_qscv_with_leakage_displayed():
    cfg = _qscv_cfg(display_vars=["C", "IL"])
    lo, hi = qscv_execution_time_range(cfg)
    assert lo == hi == pytest.approx(0.5 + (0.1 + 0.05) * 9)


def test_qscv_double_sweep_doubles_indexes():
    cfg = _qscv_cfg()
    cfg.var1.mode = VAR1Mode.DOUBLE
    lo, _ = qscv_execution_time_range(cfg)
    assert lo == pytest.approx(0.5 + 0.1 * 18)


def test_qscv_none_when_step_invalid():
    cfg = _qscv_cfg()
    cfg.var1.step = 0.0
    assert qscv_execution_time_range(cfg) is None


# ── Sampling ─────────────────────────────────────────────────────────────────


def _samp_cfg(**overrides):
    cfg = SamplingConfig()
    cfg.measurement_setup.integration_mode = IntegrationMode.MED
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "AUTO"}}
    cfg.constants = {"SMU1": {"source": 0.0, "compliance": 0.01}}
    cfg.display_vars = ["@TIME", "I1"]
    cfg.hold_time = 0.0
    cfg.initial_interval = 0.02
    cfg.points = 11
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


_SAMP_CHANNELS = [_smu(1, mode="V")]


def test_sampling_numeric_total_time():
    cfg = _samp_cfg(period_mode=PeriodMode.NUMERIC, period=5.0, hold_time=0.5)
    lo, hi = sampling_execution_time_range(cfg, _SAMP_CHANNELS, "4155C", 50)
    assert lo == hi == pytest.approx(5.5)


def test_sampling_no_limit_is_indeterminate():
    cfg = _samp_cfg(period_mode=PeriodMode.NO_LIMIT)
    assert (
        sampling_execution_time_range(cfg, _SAMP_CHANNELS, "4155C", 50) is None
    )


def test_sampling_log_mode_is_indeterminate():
    cfg = _samp_cfg(mode=SamplingMode.L10, period_mode=PeriodMode.AUTO)
    assert (
        sampling_execution_time_range(cfg, _SAMP_CHANNELS, "4155C", 50) is None
    )


def test_sampling_auto_uses_adjusted_interval():
    # MPSMU AUTO MED interval 0.04–0.12 s; IINT 0.02 → adjusted 0.04–0.12.
    cfg = _samp_cfg(period_mode=PeriodMode.AUTO)
    lo, hi = sampling_execution_time_range(cfg, _SAMP_CHANNELS, "4155C", 50)
    assert lo == pytest.approx(0.04 * 11)
    assert hi == pytest.approx(0.12 * 11)


# ── Adjusted interval & formatting ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("measurement_time", "iint", "expected"),
    [
        (0.03, 0.02, 0.04),  # 1.5 → ceil 2
        (0.05, 0.02, 0.06),  # 2.5 → ceil 3
        (0.02, 0.02, 0.02),  # exact multiple
        (0.005, 0.02, 0.02),  # below one interval → ×1
        (0.0, 0.02, 0.02),  # zero → ×1
    ],
)
def test_adjusted_interval(measurement_time, iint, expected):
    result = _adjusted_interval(measurement_time, iint)
    assert result == pytest.approx(expected)


def test_format_execution_time_interval():
    assert format_execution_time((12.0, 48.0)) == "est. 12–48 s"


def test_format_execution_time_single_value():
    assert format_execution_time((12.0, 12.0)) == "est. 12 s"


def test_format_execution_time_indeterminate():
    assert format_execution_time(None) == "est. run time: indeterminate"
