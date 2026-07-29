"""
Tests for models/qscv_config.py — pure-Python hardware rules for the QSCV
(Quasi-static C-V) measurement mode (verified against the Agilent 4155C/4156C
User's Guide Vol.2 ch.4 and the MeasureQscvCommandBuilder limits).
"""

import pytest

from wizard_4155_4156.models.qscv_config import (
    QSCV_RANGES_4155,
    QSCV_RANGES_4156,
    QscvConfig,
    QscvConstraints,
    cap_integration_bounds,
    leak_integration_bounds,
    ranges_for_model,
    resolution_label_for,
    valid_qscv_name,
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


# SMU2 is the voltage sweep source (VAR1); SMU1 measures capacitance.
CHANNELS = [smu(2, mode="V", function="VAR1")]
ENABLED = ["SMU2"]


def make_valid_config(**overrides):
    cfg = QscvConfig()
    cfg.cap_integration_time = 0.1
    cfg.leak_integration_time = 0.1
    cfg.meas_range = 1e-9
    cfg.cap_name = "C"
    cfg.leak_name = "IL"
    cfg.display_vars = ["C", "IL"]
    cfg.var1.start = 0.0
    cfg.var1.stop = 1.0
    cfg.var1.step = 0.1
    cfg.var1.cstep = 0.05  # ≤ |step|
    cfg.var1.compliance = 0.01
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


def validate(
    cfg,
    *,
    instrument_model="4156C",
    line_frequency_hz=50,
    channels=None,
    enabled=None,
    interlock_open=False,
):
    return QscvConstraints.validate_config(
        cfg,
        active_channels=channels if channels is not None else CHANNELS,
        instrument_model=instrument_model,
        line_frequency_hz=line_frequency_hz,
        enabled_smu_ids=enabled if enabled is not None else ENABLED,
        interlock_open=interlock_open,
    )


# ── Module-level helpers ────────────────────────────────────────────────


def test_cap_integration_bounds_per_frequency():
    assert cap_integration_bounds(50) == pytest.approx((0.04, 400.0))
    assert cap_integration_bounds(60) == pytest.approx((2 / 60, 20000 / 60))


def test_leak_integration_bounds_per_frequency():
    assert leak_integration_bounds(50) == pytest.approx((0.02, 2.0))
    assert leak_integration_bounds(60) == pytest.approx((1 / 60, 100 / 60))


EXPECTED_4155_RANGE_COUNT = 2
EXPECTED_4156_RANGE_COUNT = 4


def test_ranges_for_model():
    assert ranges_for_model("4155C") == QSCV_RANGES_4155
    assert ranges_for_model("4156C") == QSCV_RANGES_4156
    assert len(QSCV_RANGES_4155) == EXPECTED_4155_RANGE_COUNT
    assert len(QSCV_RANGES_4156) == EXPECTED_4156_RANGE_COUNT


@pytest.mark.parametrize(
    ("value", "resolution"),
    [
        (10e-12, "10 fA"),
        (100e-12, "10 fA"),
        (1e-9, "100 fA"),
        (10e-9, "1 pA"),
    ],
)
def test_resolution_label(value, resolution):
    assert resolution_label_for("4156C", value) == resolution


@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("C", True),
        ("Cap1", True),
        ("ABCDEF", True),
        ("ABCDEFG", False),  # 7 chars
        ("1abc", False),  # starts with digit
        ("", False),
        ("a_b", False),  # underscore not allowed
    ],
)
def test_valid_qscv_name(name, ok):
    assert valid_qscv_name(name) is ok


@pytest.mark.parametrize(
    ("start", "stop", "step", "expected"),
    [
        (0.0, 1.0, 0.1, 9),  # floor(10) - 1
        (0.0, 1.0, 1.0, 1),  # floor(1) - 1 = 0 → auto-set to 1
        (0.0, 0.05, 0.1, -1),  # span smaller than one step (invalid)
        (0.0, 1.0, 0.0, None),  # step zero
    ],
)
def test_no_of_step(start, stop, step, expected):
    assert QscvConstraints.no_of_step(start, stop, step) == expected


# ── validate_config: baseline ────────────────────────────────────────────────


def test_valid_config_no_errors():
    assert validate(make_valid_config()) == []


# ── Integration times (line-frequency aware) ──────────────────────────


@pytest.mark.parametrize(
    ("freq", "cap", "ok"),
    [
        (50, 0.04, True),
        (50, 0.039, False),
        (50, 400.0, True),
        (50, 401.0, False),
        (60, 2 / 60, True),
        (60, 0.03, False),  # below 60 Hz minimum
        (60, 340.0, False),  # above 60 Hz maximum (333.33)
    ],
)
def test_cap_integration_validation(freq, cap, ok):
    # Referenced Mode off: the raw PLC window applies only to free entry.
    cfg = make_valid_config(cap_integration_time=cap, referenced_mode=False)
    errors = validate(cfg, line_frequency_hz=freq)
    cap_errs = [
        e for e in errors if e.startswith("Capacitance Integration Time")
    ]
    assert bool(cap_errs) != ok


@pytest.mark.parametrize(
    ("freq", "leak", "ok"),
    [
        (50, 0.02, True),
        (50, 0.019, False),
        (50, 2.0, True),
        (60, 1 / 60, True),
        (60, 1.7, False),  # above 60 Hz maximum (1.6667)
    ],
)
def test_leak_integration_validation(freq, leak, ok):
    # Referenced Mode off: it would force the leak time equal to the cap time.
    cfg = make_valid_config(leak_integration_time=leak, referenced_mode=False)
    errors = validate(cfg, line_frequency_hz=freq)
    leak_errs = [e for e in errors if e.startswith("Leak Integration Time")]
    assert bool(leak_errs) != ok


# ── Timing ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("delay", "ok"),
    [(0.0, True), (65.535, True), (-0.1, False), (66.0, False)],
)
def test_delay_validation(delay, ok):
    errors = validate(make_valid_config(delay=delay))
    assert bool([e for e in errors if e.startswith("Delay")]) != ok


@pytest.mark.parametrize(
    ("hold", "ok"),
    [(0.0, True), (655.35, True), (-0.1, False), (700.0, False)],
)
def test_hold_validation(hold, ok):
    errors = validate(make_valid_config(hold_time=hold))
    assert bool([e for e in errors if e.startswith("Hold Time")]) != ok


# ── Names ──────────────────────────────────────────────────────────────────


def test_cap_name_required():
    errors = validate(make_valid_config(cap_name=""))
    assert any(e.startswith("Capacitance Name") for e in errors)


def test_leak_comp_requires_name():
    cfg = make_valid_config(leak_compensation=True, leak_name="")
    errors = validate(cfg)
    assert any("Leak compensation is ON" in e for e in errors)


def test_leak_name_optional_when_comp_off():
    cfg = make_valid_config(leak_compensation=False, leak_name="")
    errors = validate(cfg)
    assert not any("Leak" in e and "Name" in e for e in errors)


def test_leak_name_invalid_when_present():
    cfg = make_valid_config(leak_compensation=False, leak_name="1bad")
    errors = validate(cfg)
    assert any(e.startswith("Leakage Current Name") for e in errors)


# ── Measurement range (instrument-gated) ─────────────────────────────────────


@pytest.mark.parametrize(
    ("model", "value", "ok"),
    [
        ("4156C", 10e-12, True),
        ("4156C", 1e-9, True),
        ("4155C", 1e-9, True),
        ("4155C", 10e-12, False),  # 10 pA not available on 4155C
        ("4155C", 100e-12, False),
    ],
)
def test_range_gating(model, value, ok):
    cfg = make_valid_config(meas_range=value)
    errors = validate(cfg, instrument_model=model)
    assert bool([e for e in errors if e.startswith("Measurement Range")]) != ok


# ── Measuring unit ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("unit", "ok"),
    [("DEFAULT", True), ("SMU2", True), ("SMU3", False)],
)
def test_measuring_unit(unit, ok):
    cfg = make_valid_config(measuring_unit=unit)
    errors = validate(cfg)
    assert bool([e for e in errors if e.startswith("Measurement Unit")]) != ok


# ── VAR1 sweep / cstep / NO. OF STEP ─────────────────────────────────────────


def test_var1_step_zero():
    cfg = make_valid_config()
    cfg.var1.step = 0.0
    assert any(e == "VAR1 Step: cannot be zero" for e in validate(cfg))


def test_var1_direction_positive_step():
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 1.0, 0.0, 0.1
    assert any("Stop must be greater than Start" in e for e in validate(cfg))


def test_var1_start_out_of_range():
    cfg = make_valid_config()
    cfg.var1.start = 150.0  # > ±100 V
    assert any(e.startswith("VAR1 Start") for e in validate(cfg))


def test_var1_compliance_out_of_range():
    cfg = make_valid_config()
    cfg.var1.compliance = 0.5  # > 0.1 A
    assert any(e.startswith("VAR1 Compliance") for e in validate(cfg))


def test_cstep_must_be_positive():
    cfg = make_valid_config()
    cfg.var1.cstep = 0.0
    assert any("Capacitance Meas Voltage" in e for e in validate(cfg))


def test_cstep_max():
    cfg = make_valid_config()
    cfg.var1.cstep = 11.0
    assert any("Capacitance Meas Voltage" in e for e in validate(cfg))


def test_cstep_must_be_le_step():
    # cvoltage is a small perturbation window — it must fit within the step.
    cfg = make_valid_config()
    cfg.var1.step = 0.1
    cfg.var1.cstep = 0.5  # > |step|
    assert any("must be ≤ |Step|" in e for e in validate(cfg))


def test_no_of_step_span_smaller_than_step():
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 0.05, 0.1
    assert any("NO. OF STEP" in e for e in validate(cfg))


def test_no_of_step_too_many():
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 100.0, 0.05  # 1999
    cfg.var1.cstep = 0.02  # ≤ |step|
    assert any("NO. OF STEP" in e for e in validate(cfg))


def test_no_of_step_auto_one_is_valid():
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 1.0, 1.0  # count 0 → 1
    cfg.var1.cstep = 1.0
    assert not any("NO. OF STEP" in e for e in validate(cfg))


# ── Output-range resolution ──────────────────────────────────────────────────
# The output range is the lowest one covering max(|start|, |stop|):
#   2 V range → 100 µV resolution, 40 V range → 2 mV resolution.
# Start/Stop need ⩾ resolution (0 exempt); Step and cstep need ⩾ 2 ×.


def res_errors(cfg, **kwargs):
    return [e for e in validate(cfg, **kwargs) if "output resolution" in e]


def test_valid_config_has_no_resolution_error():
    assert res_errors(make_valid_config()) == []


@pytest.mark.parametrize(
    ("start", "stop", "step", "cstep", "ok"),
    [
        (0.0, 1.0, 1e-4, 5e-5, False),  # 2 V range → needs 200 µV
        (0.0, 1.0, 2e-4, 2e-4, True),
        (0.0, 39.9, 0.003, 0.002, False),  # 40 V range → needs 4 mV
        (0.0, 39.9, 0.004, 0.004, True),
    ],
)
def test_step_and_cstep_need_twice_resolution(start, stop, step, cstep, ok):
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop = start, stop
    cfg.var1.step, cfg.var1.cstep = step, cstep
    assert bool(res_errors(cfg)) != ok


def test_cstep_flagged_independently_of_step():
    cfg = make_valid_config()
    cfg.var1.cstep = 1e-4  # < 2 × 100 µV, step (0.1) is fine
    errors = res_errors(cfg)
    assert len(errors) == 1
    assert errors[0].startswith("Capacitance Meas Voltage")


def test_start_below_resolution_of_the_selected_range():
    # 1 mV start with a 40 V stop → 40 V range, whose 2 mV cannot output it.
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 1e-3, 40.0, 0.1
    assert any(e.startswith("VAR1 Start") for e in res_errors(cfg))


def test_zero_start_is_always_representable():
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 40.0, 0.1
    assert res_errors(cfg) == []


def test_resolution_is_skipped_when_var1_already_invalid():
    # A zero step must produce exactly one VAR1 Step error, not two.
    cfg = make_valid_config()
    cfg.var1.step = 0.0
    errors = validate(cfg)
    assert [e for e in errors if e.startswith("VAR1 Step")] == [
        "VAR1 Step: cannot be zero"
    ]


def test_resolution_error_does_not_suppress_no_of_step():
    # Step below 2 × resolution *and* a span too small for one step: both
    # rules must report, since resolution runs after the NO. OF STEP block.
    cfg = make_valid_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 5e-5, 1e-4
    cfg.var1.cstep = 1e-5
    errors = validate(cfg)
    assert any("NO. OF STEP" in e for e in errors)
    assert any("output resolution" in e for e in errors)


# ── Interlock open tightens the voltage source range ──────────────────


def test_interlock_open_caps_voltage():
    cfg = make_valid_config()
    cfg.var1.stop = 60.0  # within ±100 but above ±40 interlock cap
    assert validate(cfg) == []
    assert any(
        e.startswith("VAR1 Stop") for e in validate(cfg, interlock_open=True)
    )


# ── Constants & display vars ─────────────────────────────────────────────────


def test_constant_source_out_of_range():
    channels = [smu(2, mode="V", function="VAR1"), smu(1, mode="V")]
    cfg = make_valid_config()
    cfg.constants = {"SMU1": {"source": 150.0, "compliance": 0.01}}
    errors = validate(cfg, channels=channels, enabled=["SMU1", "SMU2"])
    assert any("Constant Source" in e for e in errors)


def test_too_many_display_vars():
    cfg = make_valid_config(display_vars=[f"X{i}" for i in range(9)])
    assert any("Too many display variables" in e for e in validate(cfg))


def test_display_vars_requires_two_on_qscv():
    cfg = make_valid_config(display_vars=["C"])
    assert any("at least 2 display variables" in e for e in validate(cfg))


def test_display_vars_requires_c_or_il():
    # Only non-measurable (source) variables selected → Rule 1 fails;
    # for QSCV the measurement variables are C/IL only.
    cfg = make_valid_config(display_vars=["V2", "VSU1"])
    assert any("at least one measurement variable" in e for e in validate(cfg))
