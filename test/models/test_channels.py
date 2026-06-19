"""
Tests for models/channels.py — pure-Python 4155/56 channel rules.

Covers the ChannelsConstraints rule-set (mode/function tables and the seven
validate_config rules), the ChannelsConfig first-page defaults, and the
to_measure_dict SCPI serialization. No Qt — the model is unit-testable
without a graphical context.
"""

import pytest

from wizard_4155_4156.models.channels import (
    ChannelsConfig,
    ChannelsConstraints,
    InstrumentModel,
    MeasurementMode,
    SMUMode,
    UnitFunction,
)

# ── ChannelsConstraints: mode / function tables ──────────────────────────────


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (InstrumentModel.HP4155B, ["SWEEP", "SAMPLING"]),
        (InstrumentModel.HP4156B, ["SWEEP", "SAMPLING"]),
        (InstrumentModel.HP4155C, ["SWEEP", "SAMPLING", "QSCV"]),
        (InstrumentModel.HP4156C, ["SWEEP", "SAMPLING", "QSCV"]),
    ],
)
def test_allowed_modes(model, expected):
    modes = ChannelsConstraints.allowed_modes(model)
    assert [m.value for m in modes] == expected


@pytest.mark.parametrize(
    ("mode", "usable"),
    [
        (MeasurementMode.SWEEP, True),
        (MeasurementMode.SAMPLING, True),
        (MeasurementMode.QSCV, False),
    ],
)
def test_vmu_usable_in_mode(mode, usable):
    assert ChannelsConstraints.vmu_usable_in_mode(mode) is usable


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (MeasurementMode.SWEEP, ["CONST", "VAR1", "VAR2", "VAR1'"]),
        (MeasurementMode.SAMPLING, ["CONST"]),
        (MeasurementMode.QSCV, ["CONST", "VAR1"]),
    ],
)
def test_smu_functions(mode, expected):
    fns = ChannelsConstraints.smu_functions(mode)
    assert [f.value for f in fns] == expected


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (MeasurementMode.SWEEP, ["CONST", "VAR1", "VAR2", "VAR1'"]),
        (MeasurementMode.SAMPLING, ["CONST"]),
        (MeasurementMode.QSCV, ["CONST"]),
    ],
)
def test_vsu_functions(mode, expected):
    fns = ChannelsConstraints.vsu_functions(mode)
    assert [f.value for f in fns] == expected


@pytest.mark.parametrize(
    ("mode", "locked"),
    [
        (SMUMode.V, False),
        (SMUMode.I, False),
        (SMUMode.VPULSE, False),
        (SMUMode.IPULSE, False),
        (SMUMode.COMM, True),
    ],
)
def test_smu_function_locked(mode, locked):
    assert ChannelsConstraints.smu_function_locked(mode) is locked


def test_clamp_function_keeps_allowed():
    allowed = ChannelsConstraints.smu_functions(MeasurementMode.SWEEP)
    result = ChannelsConstraints.clamp_function(UnitFunction.VAR2, allowed)
    assert result == UnitFunction.VAR2


def test_clamp_function_falls_back_to_const():
    allowed = ChannelsConstraints.smu_functions(MeasurementMode.SAMPLING)
    result = ChannelsConstraints.clamp_function(UnitFunction.VAR1, allowed)
    assert result == UnitFunction.CONST


def test_clamp_mode_keeps_allowed():
    allowed = ChannelsConstraints.allowed_modes(InstrumentModel.HP4156C)
    result = ChannelsConstraints.clamp_mode(MeasurementMode.QSCV, allowed)
    assert result == MeasurementMode.QSCV


def test_clamp_mode_falls_back_to_sweep():
    allowed = ChannelsConstraints.allowed_modes(InstrumentModel.HP4155B)
    result = ChannelsConstraints.clamp_mode(MeasurementMode.QSCV, allowed)
    assert result == MeasurementMode.SWEEP


# ── validate_config (4155/56 rules 1.1.1 – 1.1.7) ────────────────────────────


def test_default_config_is_valid():
    assert ChannelsConstraints.validate_config(ChannelsConfig()) == []


def test_duplicate_variable_name():
    cfg = ChannelsConfig()
    cfg.smu[2].voltage_name = cfg.smu[1].voltage_name
    errors = ChannelsConstraints.validate_config(cfg)
    assert any("same voltage/current" in e for e in errors)


def test_duplicate_name_is_case_insensitive():
    cfg = ChannelsConfig()
    cfg.smu[2].voltage_name = cfg.smu[1].voltage_name.lower()
    errors = ChannelsConstraints.validate_config(cfg)
    assert any("same voltage/current" in e for e in errors)


def test_blank_names_are_not_duplicates():
    cfg = ChannelsConfig()
    cfg.smu[2].voltage_name = ""
    cfg.smu[3].voltage_name = ""
    errors = ChannelsConstraints.validate_config(cfg)
    assert not any("same voltage/current" in e for e in errors)


def test_all_units_disabled():
    cfg = ChannelsConfig()
    for smu in cfg.smu.values():
        smu.enabled = False
    for vsu in cfg.vsu.values():
        vsu.enabled = False
    errors = ChannelsConstraints.validate_config(cfg)
    assert "All units are disabled" in errors


def test_two_primary_sweep_units():
    cfg = ChannelsConfig()
    cfg.smu[4].function = UnitFunction.VAR1  # SMU2 is already VAR1
    errors = ChannelsConstraints.validate_config(cfg)
    assert "Two units or more are selected as primary sweep" in errors


def test_two_subordinate_sweep_units():
    cfg = ChannelsConfig()
    cfg.smu[4].function = UnitFunction.VAR2  # SMU3 is already VAR2
    errors = ChannelsConstraints.validate_config(cfg)
    assert "Two units or more are selected as subordinate sweep" in errors


def test_two_vard_units():
    cfg = ChannelsConfig()
    cfg.smu[4].function = UnitFunction.VAR1_PRIME  # VSU1 is already VARD
    errors = ChannelsConstraints.validate_config(cfg)
    assert "Two units or more are selected as VARD" in errors


def test_sweep_requires_primary_sweep_unit():
    cfg = ChannelsConfig()
    cfg.smu[2].function = UnitFunction.CONST  # remove the only VAR1
    errors = ChannelsConstraints.validate_config(cfg)
    assert any(
        e.startswith("At least one unit must be selected") for e in errors
    )


def test_sampling_does_not_require_primary_sweep():
    cfg = ChannelsConfig()
    cfg.measurement_mode = MeasurementMode.SAMPLING
    cfg.smu[2].function = UnitFunction.CONST
    cfg.smu[3].function = UnitFunction.CONST
    cfg.vsu[1].function = UnitFunction.CONST
    errors = ChannelsConstraints.validate_config(cfg)
    assert not any(
        e.startswith("At least one unit must be selected") for e in errors
    )


@pytest.mark.parametrize(
    ("var1_mode", "mismatch"),
    [
        (SMUMode.V, False),  # VARD (VSU1) is always V → match
        (SMUMode.I, True),
        (SMUMode.COMM, True),
    ],
)
def test_var1_vard_type_match(var1_mode, mismatch):
    cfg = ChannelsConfig()
    cfg.smu[2].mode = var1_mode  # SMU2 is VAR1; VSU1 is VARD
    errors = ChannelsConstraints.validate_config(cfg)
    msg = "Primary sweep and VARD must have the same V/I mode type"
    assert (msg in errors) is mismatch


# ── ChannelsConfig defaults (first-page layout) ──────────────────────────────


def test_default_model_and_mode():
    cfg = ChannelsConfig()
    assert cfg.instrument_model == InstrumentModel.HP4156B
    assert cfg.measurement_mode == MeasurementMode.SWEEP


def test_default_global_flags():
    cfg = ChannelsConfig()
    assert cfg.common_to_ground is True
    assert cfg.interlock_open is True


@pytest.mark.parametrize(
    ("index", "mode", "function"),
    [
        (1, SMUMode.COMM, UnitFunction.CONST),
        (2, SMUMode.V, UnitFunction.VAR1),
        (3, SMUMode.I, UnitFunction.VAR2),
        (4, SMUMode.V, UnitFunction.CONST),
    ],
)
def test_default_smu_layout(index, mode, function):
    smu = ChannelsConfig().smu[index]
    assert smu.enabled is True
    assert smu.mode == mode
    assert smu.function == function
    assert smu.voltage_name == f"V{index}"
    assert smu.current_name == f"I{index}"


def test_default_vmus_disabled():
    cfg = ChannelsConfig()
    assert all(not vmu.enabled for vmu in cfg.vmu.values())


@pytest.mark.parametrize(
    ("index", "function"),
    [(1, UnitFunction.VAR1_PRIME), (2, UnitFunction.CONST)],
)
def test_default_vsu_layout(index, function):
    vsu = ChannelsConfig().vsu[index]
    assert vsu.enabled is True
    assert vsu.function == function
    assert vsu.voltage_name == f"VSU{index}"


# ── to_measure_dict (SCPI serialization) ─────────────────────────────────────


def test_to_measure_dict_default_structure():
    out = ChannelsConfig().to_measure_dict()
    assert out["mode"] == "SWEEP"
    channels = out["channels"]
    assert channels["SMU1"] == {
        "v_name": "V1",
        "i_name": "I1",
        "function": "CONS",
        "smu_mode": "COMM",
    }
    assert channels["VSU1"]["function"] == "VARD"


def test_to_measure_dict_disabled_unit():
    cfg = ChannelsConfig()
    cfg.smu[4].enabled = False
    channels = cfg.to_measure_dict()["channels"]
    assert channels["SMU4"] == {"disable": 1}


def test_to_measure_dict_vmu_disabled_by_default():
    channels = ChannelsConfig().to_measure_dict()["channels"]
    assert channels["VMU1"] == {"disable": 1}


def test_to_measure_dict_vmu_active_when_enabled_and_usable():
    cfg = ChannelsConfig()
    cfg.vmu[1].enabled = True
    channels = cfg.to_measure_dict()["channels"]
    assert channels["VMU1"] == {"v_name": "VMU1", "vmu_mode": "V"}


def test_to_measure_dict_vmu_disabled_in_qscv():
    cfg = ChannelsConfig()
    cfg.instrument_model = InstrumentModel.HP4156C
    cfg.measurement_mode = MeasurementMode.QSCV
    cfg.vmu[1].enabled = True
    channels = cfg.to_measure_dict()["channels"]
    assert channels["VMU1"] == {"disable": 1}


@pytest.mark.parametrize(
    ("smu_mode", "expected"),
    [
        (SMUMode.V, "V"),
        (SMUMode.I, "I"),
        (SMUMode.VPULSE, "VPUL"),
        (SMUMode.IPULSE, "IPUL"),
        (SMUMode.COMM, "COMM"),
    ],
)
def test_to_measure_dict_smu_mode_mapping(smu_mode, expected):
    cfg = ChannelsConfig()
    cfg.smu[2].mode = smu_mode
    channels = cfg.to_measure_dict()["channels"]
    assert channels["SMU2"]["smu_mode"] == expected


def test_to_measure_dict_mode_mapping_sampling():
    cfg = ChannelsConfig()
    cfg.measurement_mode = MeasurementMode.SAMPLING
    assert cfg.to_measure_dict()["mode"] == "SAMP"
