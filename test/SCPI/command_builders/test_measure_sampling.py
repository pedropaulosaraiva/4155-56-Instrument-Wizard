import pytest

from wizard_4155_4156.SCPI.command_builders import (
    MeasureSamplingCommandBuilder,
)


@pytest.fixture
def builder():
    return MeasureSamplingCommandBuilder()


@pytest.mark.parametrize(
    ("method", "args", "expected", "is_query"),
    [
        (
            "set_smu_compliance",
            ("SMU1", 10.0),
            ":PAGE:MEAS:SAMP:CONS:SMU1:COMP 10.0",
            False,
        ),
        (
            "get_smu_compliance",
            ("SMU1",),
            ":PAGE:MEAS:SAMP:CONS:SMU1:COMP?",
            True,
        ),
        (
            "set_smu_source",
            ("SMU2", -5.0),
            ":PAGE:MEAS:SAMP:CONS:SMU2:SOUR -5.0",
            False,
        ),
        ("get_smu_source", ("SMU2",), ":PAGE:MEAS:SAMP:CONS:SMU2:SOUR?", True),
        (
            "set_vsu_source",
            ("VSU1", 15.0),
            ":PAGE:MEAS:SAMP:CONS:VSU1:SOUR 15.0",
            False,
        ),
        ("get_vsu_source", ("VSU1",), ":PAGE:MEAS:SAMP:CONS:VSU1:SOUR?", True),
        ("set_filter", ("ON",), ":PAGE:MEAS:SAMP:FILT ON", False),
        ("get_filter", (), ":PAGE:MEAS:SAMP:FILT?", True),
        ("set_hold_time", (5.0,), ":PAGE:MEAS:SAMP:HTIM 5.0", False),
        ("get_hold_time", (), ":PAGE:MEAS:SAMP:HTIM?", True),
        ("set_initial_interval", (1.0,), ":PAGE:MEAS:SAMP:IINT 1.0", False),
        ("get_initial_interval", (), ":PAGE:MEAS:SAMP:IINT?", True),
        ("go_to_menu", (), ":PAGE:MEAS:SAMP", False),
        ("set_mode", ("LINEAR",), ":PAGE:MEAS:SAMP:MODE LINEAR", False),
        ("get_mode", (), ":PAGE:MEAS:SAMP:MODE?", True),
        ("set_period", (0.01,), ":PAGE:MEAS:SAMP:PER 0.01", False),
        ("set_period", ("MINIMUM",), ":PAGE:MEAS:SAMP:PER MINIMUM", False),
        ("get_period", (), ":PAGE:MEAS:SAMP:PER?", True),
        ("set_period_auto", ("OFF",), ":PAGE:MEAS:SAMP:PER:AUTO OFF", False),
        ("get_period_auto", (), ":PAGE:MEAS:SAMP:PER:AUTO?", True),
        ("set_points", (100,), ":PAGE:MEAS:SAMP:POIN 100", False),
        ("get_points", (), ":PAGE:MEAS:SAMP:POIN?", True),
        ("set_scon_event_count", (10,), ":PAGE:MEAS:SAMP:SCON:ECO 10", False),
        ("get_scon_event_count", (), ":PAGE:MEAS:SAMP:SCON:ECO?", True),
        (
            "set_scon_enable_delay",
            (0.5,),
            ":PAGE:MEAS:SAMP:SCON:EDEL 0.5",
            False,
        ),
        ("get_scon_enable_delay", (), ":PAGE:MEAS:SAMP:SCON:EDEL?", True),
        (
            "set_scon_event",
            ("HIGH",),
            ":PAGE:MEAS:SAMP:SCON:EVENT HIGH",
            False,
        ),
        ("get_scon_event", (), ":PAGE:MEAS:SAMP:SCON:EVENT?", True),
        (
            "set_scon_name",
            ("VAR2",),
            ":PAGE:MEAS:SAMP:SCON:NAME 'VAR2'",
            False,
        ),
        ("get_scon_name", (), ":PAGE:MEAS:SAMP:SCON:NAME?", True),
        ("set_scon_state", ("ON",), ":PAGE:MEAS:SAMP:SCON ON", False),
        ("get_scon_state", (), ":PAGE:MEAS:SAMP:SCON?", True),
        ("set_scon_threshold", (1.2,), ":PAGE:MEAS:SAMP:SCON:THR 1.2", False),
        ("get_scon_threshold", (), ":PAGE:MEAS:SAMP:SCON:THR?", True),
    ],
)
def test_sampling_commands(builder, method, args, expected, is_query):
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
        ("set_vsu_source", ("VSU1", -21.0), "VSU source must be between"),
        ("set_vsu_source", ("VSU1", 21.0), "VSU source must be between"),
        ("set_hold_time", (-0.04,), "Hold time must be"),
        ("set_hold_time", (700.0,), "Hold time must be"),
        ("set_initial_interval", (50e-6,), "Initial interval must be"),
        ("set_initial_interval", (70.0,), "Initial interval must be"),
        ("set_period", (50e-6,), "The total sampling time"),
        ("set_period", (2e11,), "The total sampling time"),
        ("set_points", (0,), "Points must be"),
        ("set_points", (10002,), "Points must be"),
        ("set_scon_event_count", (0,), "Event count must be"),
        ("set_scon_event_count", (201,), "Event count must be"),
        ("set_scon_enable_delay", (-1.0,), "Enable delay must be >="),
    ],
)
def test_sampling_exceptions(builder, method, args, match):
    with pytest.raises(ValueError, match=match):
        getattr(builder, method)(*args)
