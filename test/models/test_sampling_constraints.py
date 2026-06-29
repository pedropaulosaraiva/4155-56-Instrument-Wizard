"""
Tests for models/sampling_config.py — pure-Python hardware rules for
the SAMPLING measurement mode (verified against the Agilent 4155C/4156C
User's Guide Vol.2 "Measurement and Analysis", Edition 3, Chapter 3).
"""

import pytest

from wizard_4155_4156.models.sampling_config import (
    IINT_MAX,
    IINT_STOP_COND_MIN,
    PERIOD_MAX,
    SAMPLE_TIME_CLOSE_RATIO,
    SAMPLE_TIME_EXCEED_RATIO,
    PeriodMode,
    SamplingConfig,
    SamplingConstraints,
    SamplingMode,
    StopCondition,
)
from wizard_4155_4156.models.sweep_config import (
    IntegrationMode,
    count_measured_units,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def smu(idx, mode="V", function="CONST"):
    return {
        "id": f"SMU{idx}",
        "unit_type": "SMU",
        "function": function,
        "mode": mode,
        "v_name": f"V{idx}",
        "i_name": f"I{idx}",
        "standby": False,
    }


def vmu(idx, mode="V"):
    return {
        "id": f"VMU{idx}",
        "unit_type": "VMU",
        "function": "MONITOR",
        "mode": mode,
        "v_name": f"VMU{idx}",
        "i_name": "",
        "standby": False,
    }


def vsu(idx):
    return {
        "id": f"VSU{idx}",
        "unit_type": "VSU",
        "function": "CONST",
        "mode": "V",
        "v_name": f"VSU{idx}",
        "i_name": "",
        "standby": False,
    }


def make_valid_config(**overrides):
    """SMU1 in V mode measuring I1; safe defaults for everything else."""
    cfg = SamplingConfig()
    cfg.display_vars = ["@TIME", "I1"]
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "AUTO"}}
    cfg.constants = {"SMU1": {"source": 0.0, "compliance": 0.01}}
    cfg.initial_interval = 0.1
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


CHANNELS_1SMU = [smu(1)]
MEASURED_1SMU = ["I1"]


def validate(cfg, channels=None, available=None):
    return SamplingConstraints.validate_config(
        cfg,
        channels if channels is not None else CHANNELS_1SMU,
        available if available is not None else MEASURED_1SMU,
    )


# ── Bound helpers ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "expected_min"),
    [
        (SamplingMode.LINEAR, 60e-6),
        (SamplingMode.L10, 560e-6),
        (SamplingMode.L25, 560e-6),
        (SamplingMode.L50, 560e-6),
        (SamplingMode.THINNEDOUT, 720e-6),
    ],
)
def test_iint_min_per_mode(mode, expected_min):
    assert SamplingConstraints.iint_min(mode) == expected_min


@pytest.mark.parametrize(
    ("mode", "n_units", "expected_max"),
    [
        (SamplingMode.LINEAR, 1, 10_001),
        (SamplingMode.LINEAR, 2, 5_000),
        (SamplingMode.LINEAR, 4, 2_500),
        (SamplingMode.LINEAR, 0, 10_001),
        (SamplingMode.THINNEDOUT, 2, 5_000),
        (SamplingMode.L10, 1, 111),
        (SamplingMode.L25, 1, 276),
        (SamplingMode.L50, 1, 551),
    ],
)
def test_points_max(mode, n_units, expected_max):
    assert SamplingConstraints.points_max(mode, n_units) == expected_max


@pytest.mark.parametrize(
    ("mode", "iint", "expected"),
    [
        # LINEAR with IINT ≤ 480 µs → AUTO only
        (SamplingMode.LINEAR, 60e-6, [PeriodMode.AUTO]),
        (SamplingMode.LINEAR, 480e-6, [PeriodMode.AUTO]),
        # LINEAR above 480 µs → all three
        (
            SamplingMode.LINEAR,
            481e-6,
            [PeriodMode.AUTO, PeriodMode.NO_LIMIT, PeriodMode.NUMERIC],
        ),
        # THINNED-OUT never offers AUTO
        (
            SamplingMode.THINNEDOUT,
            1.0,
            [PeriodMode.NO_LIMIT, PeriodMode.NUMERIC],
        ),
        # LOG modes — field not applicable
        (SamplingMode.L10, 1.0, []),
        (SamplingMode.L25, 1.0, []),
        (SamplingMode.L50, 1.0, []),
    ],
)
def test_allowed_period_modes(mode, iint, expected):
    assert SamplingConstraints.allowed_period_modes(mode, iint) == expected


def test_period_numeric_bounds():
    lo, hi = SamplingConstraints.period_numeric_bounds(0.01, 101)
    assert lo == pytest.approx(0.01 * 100)
    assert hi == PERIOD_MAX


@pytest.mark.parametrize(
    ("iint", "expected_min"),
    [
        (2e-3, 0.0),  # IINT ≥ 2 ms → 0
        (0.1, 0.0),
        (1.9e-3, -0.03),  # IINT < 2 ms → −30 ms
        (60e-6, -0.03),
    ],
)
def test_hold_time_min(iint, expected_min):
    assert SamplingConstraints.hold_time_min(iint) == expected_min


@pytest.mark.parametrize(
    ("iint", "allowed"),
    [(2e-3, True), (0.1, True), (1.9e-3, False), (60e-6, False)],
)
def test_stop_condition_allowed(iint, allowed):
    assert SamplingConstraints.stop_condition_allowed(iint) is allowed


# ── Measurement-unit counting (display-var gated) ────────────────────────────


@pytest.mark.parametrize(
    ("channel", "display_vars", "expected"),
    [
        # SMU forcing V measures I → counts only when I-name displayed
        (smu(1, mode="V"), ["I1"], 1),
        (smu(1, mode="V"), ["V1"], 0),
        # SMU forcing I measures V → counts only when V-name displayed
        (smu(1, mode="I"), ["V1"], 1),
        (smu(1, mode="I"), ["I1"], 0),
        # COMM SMU monitors current
        (smu(1, mode="COMM"), ["I1"], 1),
        # VMU measures its voltage
        (vmu(1), ["VMU1"], 1),
        (vmu(1), ["@TIME"], 0),
        # VSU never counts (source only)
        (vsu(1), ["VSU1"], 0),
    ],
)
def test_count_measurement_units_single(channel, display_vars, expected):
    count = SamplingConstraints.count_measurement_units(
        [channel], display_vars
    )
    assert count == expected


EXPECTED_MIXED_UNIT_COUNT = 3


def test_count_measurement_units_mixed():
    channels = [smu(1, "V"), smu(2, "I"), vmu(1), vsu(1)]
    count = SamplingConstraints.count_measurement_units(
        channels, ["@TIME", "I1", "V2", "VMU1"]
    )
    assert count == EXPECTED_MIXED_UNIT_COUNT


def test_count_measured_units_dvol_weighting():
    channels = [vmu(1, mode="DVOLT")]
    display = ["VMU1"]
    # Data buffer / validation: a dvol pair stores one differential value.
    assert count_measured_units(channels, display, dvol_weight=1) == 1
    # Time estimate: the differential integrates both VMUs in turn.
    expected_dvol_time_units = 2
    assert (
        count_measured_units(channels, display, dvol_weight=2)
        == expected_dvol_time_units
    )


def test_count_measurement_units_dvol_counts_one_for_buffer():
    # SamplingConstraints.count_measurement_units drives points_max → weight 1.
    channels = [vmu(1, mode="DVOLT")]
    assert SamplingConstraints.count_measurement_units(channels, ["VMU1"]) == 1


# ── validate_config: errors ──────────────────────────────────────────────────


def test_valid_config_no_errors_no_warnings():
    cfg = make_valid_config()
    errors, warnings = validate(cfg)
    assert errors == []
    assert warnings == []


@pytest.mark.parametrize(
    ("mode", "iint", "ok"),
    [
        (SamplingMode.LINEAR, 60e-6, True),
        (SamplingMode.LINEAR, 59e-6, False),
        (SamplingMode.L10, 560e-6, True),
        (SamplingMode.L10, 500e-6, False),
        (SamplingMode.THINNEDOUT, 720e-6, True),
        (SamplingMode.THINNEDOUT, 700e-6, False),
        (SamplingMode.LINEAR, IINT_MAX + 1, False),
    ],
)
def test_iint_validation(mode, iint, ok):
    cfg = make_valid_config(mode=mode, initial_interval=iint)
    if mode == SamplingMode.THINNEDOUT:
        cfg.period_mode = PeriodMode.NO_LIMIT
    if iint < IINT_STOP_COND_MIN:
        # avoid unrelated fast-sampling errors
        cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
        cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.01}}
    errors, _ = validate(cfg)
    iint_errors = [e for e in errors if e.startswith("Initial Interval")]
    assert bool(iint_errors) != ok


def test_points_capped_by_unit_count():
    # Two measurement units → max 5000 points
    channels = [smu(1, "V"), smu(2, "V")]
    cfg = make_valid_config(points=5_001)
    cfg.display_vars = ["I1", "I2"]
    cfg.constants["SMU2"] = {"source": 0.0, "compliance": 0.01}
    errors, _ = validate(cfg, channels, ["I1", "I2"])
    assert any(e.startswith("No. of Samples") for e in errors)


def test_points_log_mode_cap():
    cfg = make_valid_config(mode=SamplingMode.L10, points=112)
    errors, _ = validate(cfg)
    assert any(e.startswith("No. of Samples") for e in errors)


def test_period_auto_only_below_threshold():
    cfg = make_valid_config(
        initial_interval=400e-6, period_mode=PeriodMode.NUMERIC
    )
    cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.01}}
    errors, _ = validate(cfg)
    assert any(e.startswith("Total Samp. Time") for e in errors)


def test_period_numeric_lower_bound():
    # period must be ≥ IINT × (N − 1)
    cfg = make_valid_config(
        period_mode=PeriodMode.NUMERIC, period=0.5, points=11
    )
    cfg.initial_interval = 0.1  # min period = 1.0
    errors, _ = validate(cfg)
    assert any(e.startswith("Total Samp. Time") for e in errors)
    cfg.period = 1.0
    errors, _ = validate(cfg)
    assert not any(e.startswith("Total Samp. Time") for e in errors)


def test_thinned_out_auto_not_allowed():
    cfg = make_valid_config(
        mode=SamplingMode.THINNEDOUT, period_mode=PeriodMode.AUTO
    )
    errors, _ = validate(cfg)
    assert any(e.startswith("Total Samp. Time") for e in errors)


@pytest.mark.parametrize(
    ("iint", "hold", "ok"),
    [
        (0.1, 0.0, True),
        (0.1, 655.35, True),
        (0.1, -0.01, False),  # negative only when IINT < 2 ms
        (1e-3, -0.03, True),
        (1e-3, -0.031, False),
        (0.1, 655.36, False),
    ],
)
def test_hold_time_validation(iint, hold, ok):
    cfg = make_valid_config(initial_interval=iint, hold_time=hold)
    if iint < IINT_STOP_COND_MIN:
        cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
        cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.01}}
        cfg.period_mode = PeriodMode.AUTO
    errors, _ = validate(cfg)
    hold_errors = [e for e in errors if e.startswith("Hold Time")]
    assert bool(hold_errors) != ok


# ── Stop condition ───────────────────────────────────────────────────────────


def stop_cond(**overrides):
    sc = StopCondition(enabled=True, name="I1")
    for key, val in overrides.items():
        setattr(sc, key, val)
    return sc


def test_stop_condition_requires_2ms():
    cfg = make_valid_config(
        initial_interval=1e-3, stop_condition=stop_cond()
    )
    cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.01}}
    cfg.period_mode = PeriodMode.AUTO
    errors, _ = validate(cfg)
    assert any(e.startswith("Stop Condition: requires") for e in errors)


def test_stop_condition_delay_max():
    cfg = make_valid_config(
        stop_condition=stop_cond(enable_delay=0.1 * 32_767 + 1)
    )
    errors, _ = validate(cfg)
    assert any(e.startswith("Stop Condition Enable Delay") for e in errors)


@pytest.mark.parametrize(
    ("count", "ok"),
    [(1, True), (200, True), (0, False), (201, False)],
)
def test_stop_condition_event_count(count, ok):
    cfg = make_valid_config(stop_condition=stop_cond(event_count=count))
    errors, _ = validate(cfg)
    count_errors = [
        e for e in errors if e.startswith("Stop Condition Event No.")
    ]
    assert bool(count_errors) != ok


def test_stop_condition_unknown_name():
    cfg = make_valid_config(stop_condition=stop_cond(name="NOPE"))
    errors, _ = validate(cfg)
    assert any(e.startswith("Stop Condition Name") for e in errors)


def test_stop_condition_disabled_skips_checks():
    cfg = make_valid_config(
        stop_condition=StopCondition(enabled=False, name="NOPE")
    )
    errors, _ = validate(cfg)
    assert not any(e.startswith("Stop Condition") for e in errors)


# ── Fast-sampling rules (IINT < 2 ms) ────────────────────────────────────────


def fast_config(**overrides):
    cfg = make_valid_config(initial_interval=1e-3, **overrides)
    cfg.period_mode = PeriodMode.AUTO
    cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.01}}
    return cfg


def test_fast_sampling_valid_single_unit():
    errors, _ = validate(fast_config())
    assert errors == []


def test_fast_sampling_multi_unit_error():
    channels = [smu(1, "V"), smu(2, "V")]
    cfg = fast_config()
    cfg.display_vars = ["I1", "I2"]
    cfg.measurement_setup.ranges["SMU2"] = {"mode": "FIX", "value": 0.01}
    cfg.constants["SMU2"] = {"source": 0.0, "compliance": 0.01}
    errors, _ = validate(cfg, channels, ["I1", "I2"])
    assert any("only 1 measurement unit" in e for e in errors)


def test_fast_sampling_requires_fixed_range():
    cfg = fast_config()
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "AUTO"}}
    errors, _ = validate(cfg)
    assert any("must be FIXED" in e for e in errors)


def test_fast_sampling_requires_short_integration():
    cfg = fast_config()
    cfg.measurement_setup.integration_mode = IntegrationMode.MED
    errors, _ = validate(cfg)
    assert any("must be SHORT" in e for e in errors)


# ── Constants & display vars ─────────────────────────────────────────────────


def test_constant_source_out_of_range():
    cfg = make_valid_config()
    cfg.constants["SMU1"]["source"] = 150.0  # > ±100 V
    errors, _ = validate(cfg)
    assert any("Constant Source" in e for e in errors)


def test_too_many_display_vars():
    cfg = make_valid_config()
    cfg.display_vars = [f"X{i}" for i in range(9)]
    errors, _ = validate(cfg)
    assert any("Too many display variables" in e for e in errors)


def test_display_vars_requires_two():
    cfg = make_valid_config()
    cfg.display_vars = ["I1"]
    errors, _ = validate(cfg)
    assert any("at least 2 display variables" in e for e in errors)


def test_display_vars_requires_measurement_variable():
    cfg = make_valid_config()
    cfg.display_vars = ["@TIME", "@INDEX"]  # builtins only, no measured var
    errors, _ = validate(cfg)
    assert any("at least one measurement variable" in e for e in errors)


def test_range_vs_compliance_blocks_oversized_fixed_range():
    cfg = make_valid_config()
    cfg.constants["SMU1"]["compliance"] = 0.005  # 5 mA → covering = 10 mA
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.1}}
    errors, _ = validate(cfg)
    assert any(e.startswith("SMU1 Range") for e in errors)


# ── Timing warnings (non-blocking) ───────────────────────────────────────────


def test_timing_warning_close():
    # MED integration (20 ms) × 1 unit + 1 ms wait ≈ 21 ms busy time.
    # IINT chosen so estimate sits between CLOSE and EXCEED ratios.
    cfg = make_valid_config(initial_interval=0.025)
    errors, warnings = validate(cfg)
    assert errors == []
    assert len(warnings) == 1
    assert "close to the Initial Interval" in warnings[0]


def test_timing_warning_exceed():
    # Estimate (~21 ms) ≥ 2 × IINT (10 ms) → strong warning
    cfg = make_valid_config(initial_interval=0.01)
    errors, warnings = validate(cfg)
    assert errors == []
    assert len(warnings) == 1
    assert "much bigger than the Initial Interval" in warnings[0]


def test_timing_warning_none_when_slow():
    cfg = make_valid_config(initial_interval=1.0)
    _, warnings = validate(cfg)
    assert warnings == []


def test_timing_warning_none_without_units():
    cfg = make_valid_config(initial_interval=0.01)
    cfg.display_vars = ["@TIME"]  # no measured variable displayed
    _, warnings = validate(cfg)
    assert warnings == []


def test_warning_ratios_are_ordered():
    assert SAMPLE_TIME_CLOSE_RATIO < SAMPLE_TIME_EXCEED_RATIO


def test_estimated_sample_time():
    cfg = SamplingConfig()
    cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
    cfg.measurement_setup.short_time = 4e-4
    cfg.measurement_setup.wait_multiplier = 2.0
    est = SamplingConstraints.estimated_sample_time(
        cfg.measurement_setup, 3
    )
    # 2.0 × 1 ms wait reference + 3 × 0.4 ms integration
    assert est == pytest.approx(2e-3 + 3 * 4e-4)


def _dvol_config(initial_interval):
    cfg = SamplingConfig()
    cfg.display_vars = ["@TIME", "VMU1"]
    cfg.measurement_setup.ranges = {"VMU1": {"mode": "AUTO"}}
    cfg.constants = {}
    cfg.initial_interval = initial_interval
    return cfg


def test_timing_warning_counts_dvol_as_two_units():
    # MED integration (20 ms) + 1 ms wait. At 40 ms interval one ordinary unit
    # (~21 ms) raises no warning, but a dvol VMU integrates twice (~41 ms) and
    # crosses the "close to interval" threshold.
    single = make_valid_config(initial_interval=0.04)
    _, warnings_single = validate(single)
    assert warnings_single == []

    cfg = _dvol_config(0.04)
    channels = [vmu(1, mode="DVOLT")]
    errors, warnings = validate(cfg, channels, ["VMU1"])
    assert errors == []
    assert len(warnings) == 1
    assert "close to the Initial Interval" in warnings[0]


def test_dvol_counts_as_single_display_variable():
    # dvol VMU1 + @TIME = two selected variables → satisfies the ≥2 rule,
    # even though it consumes two measurement units for timing.
    cfg = _dvol_config(1.0)  # slow interval → isolate the display-var rule
    channels = [vmu(1, mode="DVOLT")]
    errors, _ = validate(cfg, channels, ["VMU1"])
    assert not any(e.startswith("Select at least") for e in errors)


def test_dvol_alone_fails_min_display_vars():
    cfg = _dvol_config(1.0)
    cfg.display_vars = ["VMU1"]  # a dvol pair is a single selectable variable
    channels = [vmu(1, mode="DVOLT")]
    errors, _ = validate(cfg, channels, ["VMU1"])
    assert any(
        e.startswith("Select at least 2 display variables") for e in errors
    )
