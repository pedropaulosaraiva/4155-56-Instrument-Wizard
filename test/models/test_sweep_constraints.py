"""
Tests for the cross-validation rules added to models/sweep_config.py:
Rule 1 (display variables), Rules 2/3 (compliance bounds vs source output
range and instrument model) and Rule 4 (FIX/LIM range vs compliance).
Verified against the Agilent 4155C/4156C User's Guide.
"""

import pytest

from wizard_4155_4156.models.config_loader import sweep_config_from_setup
from wizard_4155_4156.models.sweep_config import (
    COMP_V_ILOCK_MAX,
    RANGE_VALUES_SMU_VOLTAGE,
    IntegrationMode,
    SweepConfig,
    SweepConstraints,
    SweepUnitFlags,
    VAR1Mode,
    current_compliance_bounds,
    measured_variable,
    output_range_resolution,
    pulsed_channel,
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


def validate_full(
    cfg,
    *,
    flags=None,
    channels=None,
    instrument_model="4156C",
    interlock_open=False,
):
    """Full ``(errors, warnings)`` tuple from the model validation."""
    return SweepConstraints.validate_config(
        cfg,
        flags or SweepUnitFlags(has_var1=True, var1_is_voltage=True),
        active_channels=channels if channels is not None else CHANNELS_1SMU_V,
        interlock_open=interlock_open,
        instrument_model=instrument_model,
    )


def validate(cfg, **kwargs):
    """Blocking errors only (most rules under test are errors)."""
    errors, _warnings = validate_full(cfg, **kwargs)
    return errors


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
        (0.0, 0.1, 3, True),  # last = 0 + (3-1)*0.1 = 0.2 V
        (50.0, 1.0, 128, False),  # last = 50 + 127*1 = 177 V > 100 V
        (-50.0, -1.0, 128, False),  # last = -50 - 127*1 = -177 V < -100 V
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
    # last value = 30 + (20-1) × 1 = 49 V (above the 40 V interlock cap)
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
    # last value = 0 + (128-1) × 0.01 = 1.27 A (above the ±0.1 A limit)
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


# ── Total measurement indexes / points (15 200 limit) ────────────────────────


def test_total_indexes():
    points = 11  # var1 0 → 1 V, step 0.1
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 1.0, 0.1
    assert SweepConstraints.total_indexes(cfg, has_var2=False) == points
    cfg.var1.mode = VAR1Mode.DOUBLE
    assert SweepConstraints.total_indexes(cfg, has_var2=False) == 2 * points
    cfg.var1.mode = VAR1Mode.SINGLE
    cfg.var2.n_of_steps = 3
    assert SweepConstraints.total_indexes(cfg, has_var2=True) == points * 3


def _full_flags():
    return SweepUnitFlags(
        has_var1=True,
        has_var2=True,
        var1_is_voltage=True,
        var2_is_voltage=True,
    )


def test_total_points_over_limit_blocks():
    # 1001 pts × 2 (double) × 8 steps = 16 016 indexes × 1 measurable var.
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 100.0, 0.1
    cfg.var1.mode = VAR1Mode.DOUBLE
    cfg.var2.n_of_steps = 8
    errors = validate(cfg, flags=_full_flags())
    assert any(e.startswith("Total points") for e in errors)


def test_total_points_under_limit_ok():
    # 1001 × 2 × 7 = 14 014 ≤ 15 200.
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 100.0, 0.1
    cfg.var1.mode = VAR1Mode.DOUBLE
    cfg.var2.n_of_steps = 7
    errors = validate(cfg, flags=_full_flags())
    assert not any(e.startswith("Total points") for e in errors)


# ── Pulse source: channel detection ──────────────────────────────────────────


def pulse_channels(mode="VPULSE", function="CONST"):
    """VAR1 on a plain V-mode SMU1 plus a pulsed SMU2."""
    return [
        smu(1, mode="V", function="VAR1"),
        smu(2, mode=mode, function=function),
    ]


def test_pulsed_channel_detection():
    assert pulsed_channel(CHANNELS_1SMU_V) is None
    assert pulsed_channel(pulse_channels())["id"] == "SMU2"
    two_pulsed = [
        smu(1, mode="VPULSE", function="VAR1"),
        smu(2, mode="IPULSE", function="CONST"),
    ]
    assert pulsed_channel(two_pulsed) is None  # defensive: max one


# ── Pulse source: period / width / base criticals ────────────────────────────


@pytest.mark.parametrize(
    ("period", "width", "err_prefix"),
    [
        (4e-3, 1e-3, "Pulse Period"),  # below 5 ms
        (1.5, 1e-3, "Pulse Period"),  # above 1 s
        (0.5, 4e-4, "Pulse Width"),  # below 0.5 ms
        (0.5, 0.11, "Pulse Width"),  # above 100 ms
        (5e-3, 2e-3, "Pulse Period must"),  # period < width + 4 ms
    ],
)
def test_pulse_timing_criticals(period, width, err_prefix):
    cfg = make_config()
    cfg.pulse.period, cfg.pulse.width = period, width
    errors = validate(cfg, channels=pulse_channels())
    assert any(e.startswith(err_prefix) for e in errors)


def test_pulse_defaults_are_valid():
    errors = validate(make_config(), channels=pulse_channels())
    assert not any(e.startswith("Pulse") for e in errors)


def test_pulse_rules_skipped_without_pulsed_channel():
    cfg = make_config()
    cfg.pulse.period = 0.0  # invalid, but no pulse source is configured
    errors, warnings = validate_full(cfg)
    assert not any(e.startswith("Pulse") for e in errors)
    assert warnings == []


def test_pulse_base_range_voltage_interlock():
    cfg = make_config()
    cfg.pulse.base = 50.0  # fine at ±100 V, invalid at ±40 V (interlock)
    errors = validate(cfg, channels=pulse_channels("VPULSE"))
    assert not any(e.startswith("Pulse Base") for e in errors)
    errors = validate(
        cfg, channels=pulse_channels("VPULSE"), interlock_open=True
    )
    assert any(e.startswith("Pulse Base") for e in errors)


def test_pulse_base_range_current():
    cfg = make_config()
    cfg.pulse.base = 0.2  # above the ±0.1 A SMU current limit
    errors = validate(cfg, channels=pulse_channels("IPULSE"))
    assert any(e.startswith("Pulse Base") for e in errors)


# ── Pulse base participates in compliance gating ─────────────────────────────


def test_pulse_base_gates_var1_compliance():
    # VAR1 sweeps only 0–1 V, but a 50 V base on the pulsed VAR1 unit puts
    # the output in the 100 V range, capping current compliance at 20 mA.
    channels = [smu(1, mode="VPULSE", function="VAR1")]
    cfg = make_config()
    cfg.var1.compliance = 0.05
    assert not any(
        e.startswith("VAR1 Compliance")
        for e in validate(cfg, channels=channels)
    )
    cfg.pulse.base = 50.0
    assert any(
        e.startswith("VAR1 Compliance")
        for e in validate(cfg, channels=channels)
    )


def test_pulse_base_gates_constant_compliance():
    channels = pulse_channels("VPULSE", function="CONST")
    cfg = make_config()
    cfg.constants = {"SMU2": {"source": 0.0, "compliance": 0.05}}
    assert not any(
        e.startswith("SMU2 Constant Compliance")
        for e in validate(cfg, channels=channels)
    )
    cfg.pulse.base = 50.0  # 100 V range → constant compliance ≤ 20 mA
    assert any(
        e.startswith("SMU2 Constant Compliance")
        for e in validate(cfg, channels=channels)
    )


# ── Pulse suppresses power compliance and delay ──────────────────────────────


def test_pulse_suppresses_var1_power_compliance():
    channels = [smu(1, mode="VPULSE", function="VAR1")]
    cfg = make_config()
    cfg.var1.power_compliance_enabled = True
    cfg.var1.power_compliance = 100.0  # out of range — but ignored
    errors = validate(cfg, channels=channels)
    assert not any("Power Compliance" in e for e in errors)
    # ...and it no longer triggers the sweep-stop requirement either.
    assert not any(e.startswith("Sweep stop") for e in errors)
    # Sanity: the same config without pulse raises both.
    errors = validate(cfg)
    assert any(e.startswith("VAR1 Power Compliance") for e in errors)
    assert any(e.startswith("Sweep stop") for e in errors)


def test_pulse_suppresses_vard_power_compliance():
    channels = [
        smu(1, mode="V", function="VAR1"),
        smu(2, mode="VPULSE", function="VAR1'"),
    ]
    flags = SweepUnitFlags(
        has_var1=True, has_vard=True, var1_is_voltage=True
    )
    cfg = make_config()
    cfg.vard.power_compliance_enabled = True
    cfg.vard.power_compliance = 100.0
    errors = validate(cfg, flags=flags, channels=channels)
    assert not any(e.startswith("VARD Power Compliance") for e in errors)
    assert not any(e.startswith("Sweep stop") for e in errors)


def test_pulse_skips_delay_validation():
    cfg = make_config(delay=100.0)  # above the 65.535 s maximum
    assert any(e.startswith("Delay") for e in validate(cfg))
    assert not any(
        e.startswith("Delay")
        for e in validate(cfg, channels=pulse_channels())
    )


# ── Pulse-timing feasibility warning (non-blocking) ──────────────────────────


def _fast_pulse_config():
    """Meets all three pulse-width conditions: 1 measured channel (only I1
    is displayed as a measurement variable), SHORT integration, FIX range."""
    cfg = make_config()
    cfg.measurement_setup.integration_mode = IntegrationMode.SHORT
    cfg.measurement_setup.ranges = {"SMU1": {"mode": "FIX", "value": 0.01}}
    return cfg


def test_pulse_warning_absent_when_fast_conditions_met():
    _errors, warnings = validate_full(
        _fast_pulse_config(), channels=pulse_channels()
    )
    assert warnings == []


@pytest.mark.parametrize("spoiler", ["vars", "integration", "range"])
def test_pulse_warning_when_conditions_not_met(spoiler):
    cfg = _fast_pulse_config()
    if spoiler == "vars":
        cfg.display_vars = ["V1", "I1", "I2"]  # 2 measured channels
    elif spoiler == "integration":
        cfg.measurement_setup.integration_mode = IntegrationMode.MED
    else:
        cfg.measurement_setup.ranges = {
            "SMU1": {"mode": "LIM", "value": 0.01}
        }
    _errors, warnings = validate_full(cfg, channels=pulse_channels())
    assert any("pulse width" in w.lower() for w in warnings)


# ── Step size vs output-range resolution ─────────────────────────────────────


@pytest.mark.parametrize(
    ("is_voltage", "is_vsu", "model", "mag", "expected"),
    [
        (True, False, "4156C", 30.0, (40.0, 2e-3)),
        (True, False, "4155C", 1.0, (2.0, 100e-6)),
        (True, False, "4156C", 150.0, (100.0, 5e-3)),  # clamps to largest
        (False, False, "4156C", 50e-12, (100e-12, 10e-15)),
        (False, False, "4155C", 50e-12, (1e-9, 100e-15)),  # no pA ranges
        (True, True, "4155C", 5.0, (20.0, 1e-3)),  # VSU single range
    ],
)
def test_output_range_resolution(is_voltage, is_vsu, model, mag, expected):
    assert output_range_resolution(is_voltage, is_vsu, model, mag) == expected


@pytest.mark.parametrize(
    ("start", "stop", "step", "ok"),
    [
        (39.9, 40.0, 0.001, False),  # 40 V range → 2 mV resolution
        (39.9, 40.0, 0.002, True),
        (1.45, 1.5, 1e-4, True),  # 2 V range → 100 µV
        (1.45, 1.5, 5e-5, False),
    ],
)
def test_var1_step_resolution_voltage(start, stop, step, ok):
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = start, stop, step
    errors = validate(cfg)
    res_errs = [e for e in errors if "output resolution" in e]
    assert bool(res_errs) != ok


def test_var1_step_resolution_current_model_dependent():
    # A 50 pA sweep with 50 fA steps: the 4156 (HRSMU) 100 pA range resolves
    # 10 fA, while the 4155 (MPSMU) bottoms out at the 1 nA range (100 fA).
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 50e-12, 5e-14
    flags = SweepUnitFlags(has_var1=True, var1_is_voltage=False)
    channels = [smu(1, mode="I", function="VAR1")]
    assert not any(
        "output resolution" in e
        for e in validate(
            cfg, flags=flags, channels=channels, instrument_model="4156C"
        )
    )
    assert any(
        "output resolution" in e
        for e in validate(
            cfg, flags=flags, channels=channels, instrument_model="4155C"
        )
    )


def test_var1_step_resolution_vsu():
    cfg = make_config()
    flags = SweepUnitFlags(
        has_var1=True, var1_is_voltage=True, var1_is_vsu=True
    )
    channels = [vsu(1, function="VAR1")]
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 19.9, 20.0, 5e-4
    errors = validate(cfg, flags=flags, channels=channels)
    assert any("output resolution" in e for e in errors)
    cfg.var1.step = 1e-3
    errors = validate(cfg, flags=flags, channels=channels)
    assert not any("output resolution" in e for e in errors)


def test_var2_step_resolution_uses_last_value():
    # Last value = 39 + 99 × 1 mV ≈ 39.1 V → 40 V range → 2 mV resolution.
    cfg = make_config()
    cfg.var2.start, cfg.var2.step, cfg.var2.n_of_steps = 39.0, 0.001, 100
    channels = [smu(1, mode="V", function="VAR2")]
    errors = validate(cfg, flags=var2_flags(True), channels=channels)
    assert any(
        e.startswith("VAR2 Step") and "output resolution" in e
        for e in errors
    )


def test_vard_effective_step_resolution():
    # Effective step = 0.1 × 0.01 = 1 mV; outputs span ~39–39.01 V → 40 V
    # range (2 mV resolution) → critical.  ratio == 0 is exempt.
    cfg = make_config()
    cfg.vard.ratio, cfg.vard.offset = 0.01, 39.0
    flags = SweepUnitFlags(
        has_var1=True, has_vard=True, var1_is_voltage=True
    )
    channels = [
        smu(1, mode="V", function="VAR1"),
        smu(2, mode="V", function="VAR1'"),
    ]
    errors = validate(cfg, flags=flags, channels=channels)
    assert any(e.startswith("VARD Effective Step") for e in errors)
    cfg.vard.ratio = 0.0
    errors = validate(cfg, flags=flags, channels=channels)
    assert not any(e.startswith("VARD Effective Step") for e in errors)


@pytest.mark.parametrize(
    ("start", "stop", "step", "bad_label"),
    [
        (0.001, 40.0, 20.0, "VAR1 Start"),  # 40 V range → 2 mV resolution
        (40.0, 0.001, -20.0, "VAR1 Stop"),
    ],
)
def test_var1_value_below_resolution(start, stop, step, bad_label):
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = start, stop, step
    errors = validate(cfg)
    assert any(
        e.startswith(bad_label) and "output resolution" in e for e in errors
    )


def test_zero_values_are_always_representable():
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 40.0, 20.0
    assert not any("output resolution" in e for e in validate(cfg))


def test_var2_start_below_resolution():
    cfg = make_config()
    cfg.var2.start, cfg.var2.step, cfg.var2.n_of_steps = 0.001, 20.0, 3
    channels = [smu(1, mode="V", function="VAR2")]
    errors = validate(cfg, flags=var2_flags(True), channels=channels)
    assert any(
        e.startswith("VAR2 Start") and "output resolution" in e
        for e in errors
    )


def test_pulse_base_below_resolution_on_var1_unit():
    channels = [smu(1, mode="VPULSE", function="VAR1")]
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 39.9, 40.0, 0.002
    cfg.pulse.base = 0.001  # below the 40 V range's 2 mV resolution
    errors = validate(cfg, channels=channels)
    assert any(
        e.startswith("Pulse Base") and "output resolution" in e
        for e in errors
    )
    cfg.pulse.base = 0.0  # zero base is always representable
    errors = validate(cfg, channels=channels)
    assert not any(e.startswith("Pulse Base") for e in errors)


def test_pulse_base_below_resolution_on_const_unit():
    channels = pulse_channels("VPULSE", function="CONST")
    cfg = make_config()
    cfg.constants = {"SMU2": {"source": 40.0, "compliance": 0.01}}
    cfg.pulse.base = 0.001  # 40 V range from the constant source
    errors = validate(cfg, channels=channels)
    assert any(
        e.startswith("Pulse Base") and "output resolution" in e
        for e in errors
    )


def test_pulse_base_extends_resolution_range():
    # A 0–0.1 V sweep with 200 µV steps sits in the 2 V range (100 µV), but
    # a 39 V pulse base pushes the output range to 40 V (2 mV resolution).
    channels = [smu(1, mode="VPULSE", function="VAR1")]
    cfg = make_config()
    cfg.var1.start, cfg.var1.stop, cfg.var1.step = 0.0, 0.1, 2e-4
    assert not any(
        "output resolution" in e for e in validate(cfg, channels=channels)
    )
    cfg.pulse.base = 39.0
    assert any(
        "output resolution" in e for e in validate(cfg, channels=channels)
    )


# ── Config-loader round-trip ─────────────────────────────────────────────────


def test_sweep_config_from_setup_restores_pulse():
    setup = {
        "sweep_setup": {
            "pulse": {"period": 0.05, "width": 0.002, "base": 1.5},
        },
    }
    cfg = sweep_config_from_setup(setup)
    assert cfg.pulse.period == pytest.approx(0.05)
    assert cfg.pulse.width == pytest.approx(0.002)
    assert cfg.pulse.base == pytest.approx(1.5)


def test_sweep_config_from_setup_defaults_without_pulse():
    cfg = sweep_config_from_setup({"sweep_setup": {}})
    assert cfg.pulse.period == pytest.approx(10e-3)
    assert cfg.pulse.width == pytest.approx(1e-3)
    assert cfg.pulse.base == 0.0
