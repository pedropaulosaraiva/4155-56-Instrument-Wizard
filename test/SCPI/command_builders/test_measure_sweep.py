import pytest

from wizard_4155_4156.SCPI.command_builders import (
    MeasureSweepCommandBuilder,
)


@pytest.fixture
def builder():
    return MeasureSweepCommandBuilder()


@pytest.mark.parametrize(
    ("method", "args", "expected", "is_query"),
    [
        (
            "set_smu_compliance",
            ("SMU1", 10.0),
            ":PAGE:MEAS:SWE:CONS:SMU1:COMP 10.0",
            False,
        ),
        (
            "get_smu_compliance",
            ("SMU1",),
            ":PAGE:MEAS:SWE:CONS:SMU1:COMP?",
            True,
        ),
        (
            "set_smu_source",
            ("SMU2", 5.0),
            ":PAGE:MEAS:SWE:CONS:SMU2:SOUR 5.0",
            False,
        ),
        ("get_smu_source", ("SMU2",), ":PAGE:MEAS:SWE:CONS:SMU2:SOUR?", True),
        (
            "set_vsu_source",
            ("VSU1", 10.0),
            ":PAGE:MEAS:SWE:CONS:VSU1:SOUR 10.0",
            False,
        ),
        ("get_vsu_source", ("VSU1",), ":PAGE:MEAS:SWE:CONS:VSU1:SOUR?", True),
        ("set_delay", (1.0,), ":PAGE:MEAS:SWE:DEL 1.0", False),
        ("get_delay", (), ":PAGE:MEAS:SWE:DEL?", True),
        ("set_hold_time", (2.0,), ":PAGE:MEAS:SWE:HTIM 2.0", False),
        ("get_hold_time", (), ":PAGE:MEAS:SWE:HTIM?", True),
        ("go_to_menu", (), ":PAGE:MEAS:SWE", False),
        ("set_pulse_base", (0.5,), ":PAGE:MEAS:SWE:PULS:BASE 0.5", False),
        ("get_pulse_base", (), ":PAGE:MEAS:SWE:PULS:BASE?", True),
        ("set_pulse_period", (0.1,), ":PAGE:MEAS:SWE:PULS:PER 0.1", False),
        ("get_pulse_period", (), ":PAGE:MEAS:SWE:PULS:PER?", True),
        ("set_pulse_width", (0.01,), ":PAGE:MEAS:SWE:PULS:WIDT 0.01", False),
        ("get_pulse_width", (), ":PAGE:MEAS:SWE:PULS:WIDT?", True),
        (
            "set_sweep_stop",
            ("COMPLIANCE",),
            ":PAGE:MEAS:SWE:SST COMPLIANCE",
            False,
        ),
        ("get_sweep_stop", (), ":PAGE:MEAS:SWE:SST?", True),
        (
            "set_var1_compliance",
            (10.0,),
            ":PAGE:MEAS:SWE:VAR1:COMP 10.0",
            False,
        ),
        ("get_var1_compliance", (), ":PAGE:MEAS:SWE:VAR1:COMP?", True),
        (
            "set_var1_mode",
            ("DOUBLE",),
            ":PAGE:MEAS:SWE:VAR1:MODE DOUBLE",
            False,
        ),
        ("get_var1_mode", (), ":PAGE:MEAS:SWE:VAR1:MODE?", True),
        (
            "set_var1_pcompliance",
            (5.0,),
            ":PAGE:MEAS:SWE:VAR1:PCOM 5.0",
            False,
        ),
        ("get_var1_pcompliance", (), ":PAGE:MEAS:SWE:VAR1:PCOM?", True),
        (
            "set_var1_pcompliance_state",
            ("ON",),
            ":PAGE:MEAS:SWE:VAR1:PCOM:STAT ON",
            False,
        ),
        (
            "get_var1_pcompliance_state",
            (),
            ":PAGE:MEAS:SWE:VAR1:PCOM:STAT?",
            True,
        ),
        (
            "set_var1_spacing",
            ("LINEAR",),
            ":PAGE:MEAS:SWE:VAR1:SPAC LINEAR",
            False,
        ),
        ("get_var1_spacing", (), ":PAGE:MEAS:SWE:VAR1:SPAC?", True),
        ("set_var1_start", (0.0,), ":PAGE:MEAS:SWE:VAR1:STAR 0.0", False),
        ("get_var1_start", (), ":PAGE:MEAS:SWE:VAR1:STAR?", True),
        ("set_var1_step", (0.1,), ":PAGE:MEAS:SWE:VAR1:STEP 0.1", False),
        ("get_var1_step", (), ":PAGE:MEAS:SWE:VAR1:STEP?", True),
        ("set_var1_stop", (5.0,), ":PAGE:MEAS:SWE:VAR1:STOP 5.0", False),
        ("get_var1_stop", (), ":PAGE:MEAS:SWE:VAR1:STOP?", True),
        (
            "set_var2_compliance",
            (10.0,),
            ":PAGE:MEAS:SWE:VAR2:COMP 10.0",
            False,
        ),
        ("get_var2_compliance", (), ":PAGE:MEAS:SWE:VAR2:COMP?", True),
        (
            "set_var2_pcompliance",
            (5.0,),
            ":PAGE:MEAS:SWE:VAR2:PCOM 5.0",
            False,
        ),
        ("get_var2_pcompliance", (), ":PAGE:MEAS:SWE:VAR2:PCOM?", True),
        (
            "set_var2_pcompliance_state",
            ("ON",),
            ":PAGE:MEAS:SWE:VAR2:PCOM:STAT ON",
            False,
        ),
        (
            "get_var2_pcompliance_state",
            (),
            ":PAGE:MEAS:SWE:VAR2:PCOM:STAT?",
            True,
        ),
        ("set_var2_points", (10,), ":PAGE:MEAS:SWE:VAR2:POIN 10", False),
        ("get_var2_points", (), ":PAGE:MEAS:SWE:VAR2:POIN?", True),
        ("set_var2_start", (0.0,), ":PAGE:MEAS:SWE:VAR2:STAR 0.0", False),
        ("get_var2_start", (), ":PAGE:MEAS:SWE:VAR2:STAR?", True),
        ("set_var2_step", (0.1,), ":PAGE:MEAS:SWE:VAR2:STEP 0.1", False),
        ("get_var2_step", (), ":PAGE:MEAS:SWE:VAR2:STEP?", True),
        (
            "set_vard_compliance",
            (10.0,),
            ":PAGE:MEAS:SWE:VARD:COMP 10.0",
            False,
        ),
        ("get_vard_compliance", (), ":PAGE:MEAS:SWE:VARD:COMP?", True),
        ("set_vard_offset", (0.5,), ":PAGE:MEAS:SWE:VARD:OFFS 0.5", False),
        ("get_vard_offset", (), ":PAGE:MEAS:SWE:VARD:OFFS?", True),
        (
            "set_vard_pcompliance",
            (5.0,),
            ":PAGE:MEAS:SWE:VARD:PCOM 5.0",
            False,
        ),
        ("get_vard_pcompliance", (), ":PAGE:MEAS:SWE:VARD:PCOM?", True),
        (
            "set_vard_pcompliance_state",
            ("ON",),
            ":PAGE:MEAS:SWE:VARD:PCOM:STAT ON",
            False,
        ),
        (
            "get_vard_pcompliance_state",
            (),
            ":PAGE:MEAS:SWE:VARD:PCOM:STAT?",
            True,
        ),
        ("set_vard_ratio", (1.5,), ":PAGE:MEAS:SWE:VARD:RAT 1.5", False),
        ("get_vard_ratio", (), ":PAGE:MEAS:SWE:VARD:RAT?", True),
    ],
)
def test_sweep_commands(builder, method, args, expected, is_query):
    getattr(builder, method)(*args)
    assert builder.is_command_query is is_query
    assert builder.build() == expected


@pytest.mark.parametrize(
    ("method", "args", "match"),
    [
        (
            "set_smu_compliance",
            ("SMU1", -201.0),
            "SMU Compliance must be between",
        ),
        (
            "set_smu_compliance",
            ("SMU1", 201.0),
            "SMU Compliance must be between",
        ),
        ("set_var1_step", (-401.0,), "VAR1 Step must be between"),
        ("set_var1_step", (401.0,), "VAR1 Step must be between"),
        (
            "set_var1_pcompliance",
            (1e-4,),
            "VAR1 Power Compliance must be between",
        ),
        (
            "set_var1_pcompliance",
            (21.0,),
            "VAR1 Power Compliance must be between",
        ),
        ("set_vsu_source", ("VSU1", -21.0), "VSU source must be between"),
        ("set_vsu_source", ("VSU1", 21.0), "VSU source must be between"),
        ("set_delay", (-0.1,), "Delay must be"),
        ("set_delay", (70.0,), "Delay must be"),
        ("set_hold_time", (-0.1,), "Hold time must be"),
        ("set_hold_time", (700.0,), "Hold time must be"),
        ("set_pulse_period", (1e-3,), "Pulse period must be"),
        ("set_pulse_period", (2.0,), "Pulse period must be"),
        ("set_pulse_width", (1e-4,), "Pulse width must be"),
        ("set_pulse_width", (0.2,), "Pulse width must be"),
        ("set_var2_points", (0,), "VAR2 points must be"),
        ("set_var2_points", (129,), "VAR2 points must be"),
    ],
)
def test_sweep_exceptions(builder, method, args, match):
    with pytest.raises(ValueError, match=match):
        getattr(builder, method)(*args)
