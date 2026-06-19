"""
Tests for the cross-validation rules added to models/sweep_config.py:
Rule 1 (display variables), Rules 2/3 (compliance bounds vs source output
range and instrument model) and Rule 4 (FIX/LIM range vs compliance).
Verified against the Agilent 4155C/4156C User's Guide.
"""

import pytest

from wizard_4155_4156.models.sweep_config import (
    COMP_V_ILOCK_MAX,
    RANGE_VALUES_SMU_VOLTAGE,
    SweepConfig,
    SweepConstraints,
    SweepUnitFlags,
    current_compliance_bounds,
    measured_variable,
    smallest_range_at_least,
    voltage_compliance_bounds,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def smu(idx, mode="V", function="VAR1"):
    return {
        "id": f"SMU{idx}",
        "unit_type": "SMU",
        "function": function,
        "mode": mode,
        "v_name": f"V{idx}",
        "i_name": f"I{idx}",
        "standby": False,
    }


def vsu(idx, function="CONST"):
    return {
        "id": f"VSU{idx}",
        "unit_type": "VSU",
        "function": function,
        "mode": "V",
        "v_name": f"VSU{idx}",
        "i_name": "",
        "standby": False,
    }


def make_config(**overrides):
    """SMU1 forcing V as VAR1; safe defaults for everything else."""
    cfg = SweepConfig()
    cfg.display_vars = ["V1", "I1"]
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


CHANNELS_1SMU_V = [smu(1, mode="V", function="VAR1")]


def validate(
    cfg,
    *,
    flags=None,
    channels=None,
    instrument_model="4156C",
    interlock_open=False,
):
    return SweepConstraints.validate_config(
        cfg,
        flags or SweepUnitFlags(has_var1=True, var1_is_voltage=True),
        active_channels=channels if channels is not None else CHANNELS_1SMU_V,
        interlock_open=interlock_open,
        instrument_model=instrument_model,
    )


# ── Module-level helpers ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.5, 2.0),
        (2.0, 2.0),
        (30.0, 40.0),
        (50.0, 100.0),
        (100.0, 100.0),
        (150.0, None),  # above the largest range
    ],
)
def test_smallest_range_at_least(value, expected):
    assert smallest_range_at_least(value, RANGE_VALUES_SMU_VOLTAGE) == expected


@pytest.mark.parametrize(
    ("model", "v_mag", "expected_max"),
    [
        ("4156C", 1.0, 0.1),  # 2 V range → 100 mA
        ("4156C", 30.0, 0.05),  # 40 V range → 50 mA
        ("4156C", 50.0, 0.02),  # 100 V range → 20 mA
        ("4155C", 1.0, 0.1),
    ],
)
def test_current_compliance_max(model, v_mag, expected_max):
    _lo, hi = current_compliance_bounds(model, v_mag)
    assert hi == pytest.approx(expected_max)


def test_current_compliance_min_is_model_dependent():
    assert current_compliance_bounds("4156C", 1.0)[0] == pytest.approx(1e-13)
    assert current_compliance_bounds("4155C", 1.0)[0] == pytest.approx(1e-12)


@pytest.mark.parametrize(
    ("i_mag", "expected_max"),
    [
        (0.01, 100.0),  # ≤ 20 mA → 100 V
        (0.02, 100.0),
        (0.03, 40.0),  # ≤ 50 mA → 40 V
        (0.05, 40.0),
        (0.08, 20.0),  # ≤ 100 mA → 20 V
    ],
)
def test_voltage_compliance_max(i_mag, expected_max):
    _lo, hi = voltage_compliance_bounds(i_mag)
    assert hi == pytest.approx(expected_max)


def test_voltage_compliance_interlock_caps_at_40v():
    assert (
        voltage_compliance_bounds(0.01, interlock_open=True)[1]
        == COMP_V_ILOCK_MAX
    )


def test_measured_variable():
    assert measured_variable(smu(1, mode="V")) == "I1"
    assert measured_variable(smu(1, mode="I")) == "V1"
    assert measured_variable(smu(1, mode="IPULSE")) == "V1"
    assert measured_variable(vsu(1)) is None


# ── Rule 1: display variables ────────────────────────────────────────────────


def test_display_vars_valid_baseline():
    errors = validate(make_config())
    assert not any("display variable" in e.lower() for e in errors)


def test_display_vars_requires_two():
    cfg = make_config(display_vars=["I1"])
    errors = validate(cfg)
    assert any("at least 2 display variables" in e for e in errors)


def test_display_vars_requires_a_measurement_variable():
    # Two source-only (non-measurable) names selected, no SMU current.
    channels = [smu(1, mode="V", function="VAR1"), vsu(1)]
    cfg = make_config(display_vars=["V1", "VSU1"])
    errors = validate(cfg, channels=channels)
    assert any("at least one measurement variable" in e for e in errors)


# ── Rule 3: current compliance vs voltage output range ───────────────────────


@pytest.mark.parametrize(
    ("stop", "compliance", "ok"),
    [
        (50.0, 0.02, True),  # 100 V range → ≤ 20 mA
        (50.0, 0.021, False),
        (30.0, 0.05, True),  # 40 V range → ≤ 50 mA
        (30.0, 0.051, False),
    ],
)
def test_current_compliance_rule(stop, compliance, ok):
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, stop, 0.1
    cfg.var1.compliance = compliance
    errors = validate(cfg)
    comp_errs = [e for e in errors if e.startswith("VAR1 Compliance")]
    assert bool(comp_errs) != ok


def test_current_compliance_min_rejected_on_4155():
    cfg = make_config()
    cfg.var1.compliance = 5e-13  # below the MPSMU 1 pA floor
    assert any(
        e.startswith("VAR1 Compliance")
        for e in validate(cfg, instrument_model="4155C")
    )
    assert not any(
        e.startswith("VAR1 Compliance")
        for e in validate(cfg, instrument_model="4156C")
    )


# ── Rule 2: voltage compliance vs current output range ───────────────────────


@pytest.mark.parametrize(
    ("stop", "compliance", "ok"),
    [
        (0.01, 100.0, True),  # |I| ≤ 20 mA → ≤ 100 V
        (0.03, 40.0, True),  # |I| ≤ 50 mA → ≤ 40 V
        (0.03, 41.0, False),
        (0.08, 20.0, True),  # |I| ≤ 100 mA → ≤ 20 V
        (0.08, 21.0, False),
    ],
)
def test_voltage_compliance_rule(stop, compliance, ok):
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, stop, 0.001
    cfg.var1.compliance = compliance
    flags = SweepUnitFlags(has_var1=True, var1_is_voltage=False)
    channels = [smu(1, mode="I", function="VAR1")]
    errors = validate(cfg, flags=flags, channels=channels)
    comp_errs = [e for e in errors if e.startswith("VAR1 Compliance")]
    assert bool(comp_errs) != ok


# ── VAR2 last value vs channel source range ──────────────────────────────────


def var2_flags(is_voltage=True):
    return SweepUnitFlags(has_var2=True, var2_is_voltage=is_voltage)


@pytest.mark.parametrize(
    ("start", "step", "n_of_steps", "ok"),
    [
        (0.0, 0.1, 3, True),  # last = 0.3 V
        (50.0, 1.0, 128, False),  # last = 178 V > 100 V
        (-50.0, -1.0, 128, False),  # last = -178 V < -100 V
    ],
)
def test_var2_last_value_voltage(start, step, n_of_steps, ok):
    cfg = make_config()
    cfg.var2.start, cfg.var2.step = start, step
    cfg.var2.n_of_steps = n_of_steps
    channels = [smu(1, mode="V", function="VAR2")]
    errors = validate(cfg, flags=var2_flags(True), channels=channels)
    last_errs = [e for e in errors if e.startswith("VAR2 Last Value")]
    assert bool(last_errs) != ok


def test_var2_last_value_interlock_open_caps_at_40v():
    cfg = make_config()
    # last value = 30 + 20 × 1 = 50 V (above the 40 V interlock cap)
    cfg.var2.start, cfg.var2.step, cfg.var2.n_of_steps = 30.0, 1.0, 20
    channels = [smu(1, mode="V", function="VAR2")]
    assert not any(
        e.startswith("VAR2 Last Value")
        for e in validate(cfg, flags=var2_flags(True), channels=channels)
    )
    assert any(
        e.startswith("VAR2 Last Value")
        for e in validate(
            cfg,
            flags=var2_flags(True),
            channels=channels,
            interlock_open=True,
        )
    )


def test_var2_last_value_current_mode():
    cfg = make_config()
    # last value = 0 + 128 × 0.01 = 1.28 A (above the ±0.1 A limit)
    cfg.var2.start, cfg.var2.step, cfg.var2.n_of_steps = 0.0, 0.01, 128
    cfg.var2.compliance = 1.0  # in-range V compliance, isolate the test
    channels = [smu(1, mode="I", function="VAR2")]
    errors = validate(cfg, flags=var2_flags(False), channels=channels)
    assert any(e.startswith("VAR2 Last Value") for e in errors)


# ── Rule 4: FIX/LIM measurement range vs compliance ──────────────────────────


@pytest.mark.parametrize(
    ("range_value", "ok"),
    [
        (0.001, True),  # 1 mA ≤ covering(5 mA)=10 mA
        (0.01, True),  # exactly the covering range
        (0.1, False),  # 100 mA > covering(5 mA)
    ],
)
def test_range_vs_compliance_voltage_mode(range_value, ok):
    cfg = make_config()
    cfg.var1.compliance = 0.005  # 5 mA → covering current range = 10 mA
    cfg.measurement_setup.ranges = {
        "SMU1": {"mode": "FIX", "value": range_value}
    }
    errors = validate(cfg)
    range_errs = [e for e in errors if e.startswith("SMU1 Range")]
    assert bool(range_errs) != ok


def test_range_vs_compliance_comm_allows_any_range():
    channels = [
        smu(1, mode="V", function="VAR1"),
        smu(2, mode="COMM", function="CONST"),
    ]
    cfg = make_config()
    cfg.measurement_setup.ranges = {"SMU2": {"mode": "FIX", "value": 0.1}}
    errors = validate(cfg, channels=channels)
    assert not any(e.startswith("SMU2 Range") for e in errors)


def test_range_auto_is_not_constrained():
    cfg = make_config()
    cfg.var1.compliance = 0.005
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "AUTO"}}
    assert not any(e.startswith("SMU1 Range") for e in validate(cfg))
