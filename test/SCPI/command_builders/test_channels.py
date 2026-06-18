import pytest

from wizard_4155_4156.SCPI.command_builders import (
    ChannelsCommandBuilder,
)


@pytest.fixture
def builder():
    return ChannelsCommandBuilder()


@pytest.mark.parametrize(
    ("method", "args", "expected", "is_query"),
    [
        ("set_all_disable", (), ":PAGE:CHAN:ALL:DIS", False),
        ("set_all_default", (), ":PAGE:CHAN:DEF", False),
        ("set_mode", ("SWEEP",), ":PAGE:CHAN:MODE SWEEP", False),
        ("get_mode", (), ":PAGE:CHAN:MODE?", True),
        ("set_disable", ("SMU1",), ":PAGE:CHAN:SMU1:DIS", False),
        (
            "set_i_name",
            ("SMU1", "ITEST"),
            ":PAGE:CHAN:SMU1:INAME 'ITEST'",
            False,
        ),
        ("get_i_name", ("SMU1",), ":PAGE:CHAN:SMU1:INAME?", True),
        (
            "set_v_name",
            ("VMU1", "VTEST"),
            ":PAGE:CHAN:VMU1:VNAME 'VTEST'",
            False,
        ),
        ("get_v_name", ("VMU1",), ":PAGE:CHAN:VMU1:VNAME?", True),
        ("set_function", ("SMU2", "VAR1"), ":PAGE:CHAN:SMU2:FUNC VAR1", False),
        ("get_function", ("VSU1",), ":PAGE:CHAN:VSU1:FUNC?", True),
        ("set_smu_mode", ("SMU3", "COMM"), ":PAGE:CHAN:SMU3:MODE COMM", False),
        ("get_smu_mode", ("SMU4",), ":PAGE:CHAN:SMU4:MODE?", True),
        ("set_vmu_mode", ("VMU2", "DVOL"), ":PAGE:CHAN:VMU2:MODE DVOL", False),
        ("get_vmu_mode", ("VMU1",), ":PAGE:CHAN:VMU1:MODE?", True),
        ("set_standby_mode", ("SMU1", "ON"), ":PAGE:CHAN:SMU1:STAN ON", False),
        ("get_standby_mode", ("VMU1",), ":PAGE:CHAN:VMU1:STAN?", True),
    ],
)
def test_channels_commands(builder, method, args, expected, is_query):
    getattr(builder, method)(*args)
    assert builder.is_command_query is is_query
    assert builder.build() == expected


def test_channels_invalid_mode(builder):
    with pytest.raises(ValueError, match="Invalid parameter"):
        builder.set_mode("INVALID_LITERAL")
