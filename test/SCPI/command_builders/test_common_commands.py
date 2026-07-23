import pytest

from wizard_4155_4156.SCPI.command_builders import (
    CommonCommandBuilder,
)


@pytest.fixture
def builder():
    return CommonCommandBuilder()


@pytest.mark.parametrize(
    ("method", "expected", "is_query"),
    [
        ("identify", "*IDN?", True),
        ("reset", ":PAGE:CHAN:DEF", False),
        ("clear", "*CLS", False),
        ("get_auto_calibration", ":CAL:AUTO?", True),
        ("get_operation_complete", "*OPC?", True),
    ],
)
def test_common_commands(builder, method, expected, is_query):
    getattr(builder, method)()
    assert builder.is_command_query is is_query
    assert builder.build() == expected


@pytest.mark.parametrize("state", ["ON", "OFF"])
def test_set_auto_calibration(builder, state):
    builder.set_auto_calibration(state)
    assert builder.is_command_query is False
    assert builder.build() == f":CAL:AUTO {state}"


def test_set_auto_calibration_invalid(builder):
    with pytest.raises(ValueError, match="Invalid parameter"):
        builder.set_auto_calibration("MAYBE")
