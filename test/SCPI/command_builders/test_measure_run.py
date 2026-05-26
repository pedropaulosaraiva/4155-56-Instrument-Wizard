import pytest

from wizard_4155_4156.SCPI.command_builders import (
    MeasureRunCommandBuilder,
)


@pytest.fixture
def builder():
    return MeasureRunCommandBuilder()


@pytest.mark.parametrize(
    ("method", "args", "expected", "is_query"),
    [
        (
            "set_display_list_select",
            ("VAR1",),
            ":PAGE:DISP:LIST 'VAR1'",
            False,
        ),
        (
            "set_display_list_select",
            ("VAR1", "VAR2"),
            ":PAGE:DISP:LIST 'VAR1','VAR2'",
            False,
        ),
        ("get_display_list_select", (), ":PAGE:DISP:LIST?", True),
        ("execute_single_measurement", (), ":PAGE:SCON:SING", False),
        ("set_standby", ("ON",), ":PAGE:SCON:STAN ON", False),
        ("get_standby", (), ":PAGE:SCON:STAN?", True),
        ("get_state", (), ":PAGE:SCON:STAT?", True),
        ("stop_operation", (), ":PAGE:SCON:STOP", False),
        ("get_trace_data", ("VAR1",), ":DATA? 'VAR1'", True),
        ("delete_all_display_list", (), ":PAGE:DISP:LIST:DEL:ALL", False),
        ("delete_graphics_axis", ("X",), ":PAGE:DISP:GRAP:X:DEL", False),
        ("set_format_data", ("ASC",), ":FORM ASC", False),
        ("set_format_data", ("REAL",), ":FORM REAL,64", False),
        ("set_format_data", ("REAL", 32), ":FORM REAL,32", False),
        ("get_format_data", (), ":FORM?", True),
        ("set_format_border", ("NORM",), ":FORM:BORD NORM", False),
        ("get_format_border", (), ":FORM:BORD?", True),
    ],
)
def test_mrun_commands(builder, method, args, expected, is_query):
    getattr(builder, method)(*args)
    assert builder.is_command_query is is_query
    assert builder.build() == expected


def test_mrun_display_list_max(builder):
    with pytest.raises(ValueError, match="Cannot define more than 8"):
        builder.set_display_list_select(*[f"v{i}" for i in range(9)])


def test_mrun_display_list_min(builder):
    with pytest.raises(ValueError, match="Cannot define less than 1"):
        builder.set_display_list_select()


def test_mrun_format_data_invalid_length(builder):
    with pytest.raises(ValueError, match="Valid lengths for REAL format are"):
        builder.set_format_data("REAL", 16)
