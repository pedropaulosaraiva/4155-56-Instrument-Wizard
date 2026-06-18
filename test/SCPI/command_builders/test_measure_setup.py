import pytest

from wizard_4155_4156.SCPI.command_builders import (
    MeasurementsSetupCommandBuilder,
)


@pytest.fixture
def builder():
    return MeasurementsSetupCommandBuilder()


@pytest.mark.parametrize(
    ("method", "args", "expected", "is_query"),
    [
        (
            "set_integration_mode",
            ("SHORT",),
            ":PAGE:MEAS:MSET:ITIM  SHORT",
            False,
        ),
        ("get_integration_mode", (), ":PAGE:MEAS:MSET:ITIM?", True),
        ("set_long_time", (10,), ":PAGE:MEAS:MSET:ITIM:LONG 10", False),
        ("get_long_time", (), ":PAGE:MEAS:MSET:ITIM:LONG?", True),
        (
            "set_short_time",
            (1e-3,),
            f":PAGE:MEAS:MSET:ITIM:SHOR  {1e-3:e}",
            False,
        ),
        ("get_short_time", (), ":PAGE:MEAS:MSET:ITIM:SHOR?", True),
        ("set_wait_time", (5.0,), f":PAGE:MEAS:MSET:WTIM  {5.0:.1f}", False),
        ("get_wait_time", (), ":PAGE:MEAS:MSET:WTIM?", True),
        ("set_range", ("SMU1", 10.0), ":PAGE:MEAS:MSET:SMU1:RANG 10.0", False),
        ("get_range", ("SMU1",), ":PAGE:MEAS:MSET:SMU1:RANG?", True),
        (
            "set_range_mode",
            ("SMU1", "AUTO"),
            ":PAGE:MEAS:MSET:SMU1:RANG:MODE AUTO",
            False,
        ),
        ("get_range_mode", ("SMU1",), ":PAGE:MEAS:MSET:SMU1:RANG:MODE?", True),
    ],
)
def test_msetup_commands(builder, method, args, expected, is_query):
    getattr(builder, method)(*args)
    assert builder.is_command_query is is_query
    assert builder.build() == expected


@pytest.mark.parametrize(
    ("method", "args", "match"),
    [
        (
            "set_long_time",
            (1,),
            "Long integration time is defined in terms of",
        ),
        (
            "set_long_time",
            (101,),
            "Long integration time is defined in terms of",
        ),
        (
            "set_short_time",
            (7e-5,),
            "Short integration time is defined in terms of",
        ),
        (
            "set_short_time",
            (2e-3,),
            "Short integration time is defined in terms of",
        ),
        ("set_wait_time", (-0.1,), "The wait time is defined in terms of"),
        ("set_wait_time", (10.1,), "The wait time is defined in terms of"),
    ],
)
def test_msetup_exceptions(builder, method, args, match):
    with pytest.raises(ValueError, match=match):
        getattr(builder, method)(*args)
