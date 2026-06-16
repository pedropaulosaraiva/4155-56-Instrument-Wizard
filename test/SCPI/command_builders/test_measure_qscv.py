import pytest

from wizard_4155_4156.SCPI.command_builders import (
    MeasureQscvCommandBuilder,
)


@pytest.fixture
def builder():
    return MeasureQscvCommandBuilder()


@pytest.mark.parametrize(
    ("method", "args", "expected", "is_query"),
    [
        # CINTeg
        (
            "set_cap_integration_time",
            (0.4,),
            ":PAGE:MEAS:QSCV:CINT 0.4",
            False,
        ),
        ("get_cap_integration_time", (), ":PAGE:MEAS:QSCV:CINT?", True),
        # CNAMe
        ("set_cap_name", ("CDATA",), ":PAGE:MEAS:QSCV:CNAME 'CDATA'", False),
        ("get_cap_name", (), ":PAGE:MEAS:QSCV:CNAME?", True),
        # CONStant:SMU<n>:COMPliance
        (
            "set_smu_compliance",
            ("SMU1", 0.1),
            ":PAGE:MEAS:QSCV:CONS:SMU1:COMP 0.1",
            False,
        ),
        (
            "get_smu_compliance",
            ("SMU1",),
            ":PAGE:MEAS:QSCV:CONS:SMU1:COMP?",
            True,
        ),
        # CONStant:SMU<n>[:SOURce]
        (
            "set_smu_source",
            ("SMU1", 10.0),
            ":PAGE:MEAS:QSCV:CONS:SMU1 10.0",
            False,
        ),
        ("get_smu_source", ("SMU1",), ":PAGE:MEAS:QSCV:CONS:SMU1?", True),
        # CONStant:VSU<n>[:SOURce]
        (
            "set_vsu_source",
            ("VSU1", 10.0),
            ":PAGE:MEAS:QSCV:CONS:VSU1 10.0",
            False,
        ),
        ("get_vsu_source", ("VSU1",), ":PAGE:MEAS:QSCV:CONS:VSU1?", True),
        # DELay
        ("set_delay", (1.5,), ":PAGE:MEAS:QSCV:DEL 1.5", False),
        ("get_delay", (), ":PAGE:MEAS:QSCV:DEL?", True),
        # HTIMe
        ("set_hold_time", (1.5,), ":PAGE:MEAS:QSCV:HTIM 1.5", False),
        ("get_hold_time", (), ":PAGE:MEAS:QSCV:HTIM?", True),
        # IINTeg
        (
            "set_leak_integration_time",
            (0.04,),
            ":PAGE:MEAS:QSCV:IINT 0.04",
            False,
        ),
        ("get_leak_integration_time", (), ":PAGE:MEAS:QSCV:IINT?", True),
        # LCANcel
        ("set_leak_cancel", ("ON",), ":PAGE:MEAS:QSCV:LCAN ON", False),
        ("get_leak_cancel", (), ":PAGE:MEAS:QSCV:LCAN?", True),
        # LNAMe
        ("set_leak_name", ("ILEAK",), ":PAGE:MEAS:QSCV:LNAME 'ILEAK'", False),
        ("get_leak_name", (), ":PAGE:MEAS:QSCV:LNAME?", True),
        # [:MENU]
        ("go_to_menu", (), ":PAGE:MEAS:QSCV", False),
        # RANGe
        ("set_range", (1e-9,), ":PAGE:MEAS:QSCV:RANG 1e-09", False),
        ("get_range", (), ":PAGE:MEAS:QSCV:RANG?", True),
        # SSTop
        (
            "set_sweep_stop",
            ("ABNORMAL",),
            ":PAGE:MEAS:QSCV:SST ABNORMAL",
            False,
        ),
        ("get_sweep_stop", (), ":PAGE:MEAS:QSCV:SST?", True),
        # UNIT
        ("set_unit", ("DEFAULT",), ":PAGE:MEAS:QSCV:UNIT DEFAULT", False),
        ("set_unit", ("SMU2",), ":PAGE:MEAS:QSCV:UNIT SMU2", False),
        ("get_unit", (), ":PAGE:MEAS:QSCV:UNIT?", True),
        # VAR1:COMPliance
        (
            "set_var1_compliance",
            (0.1,),
            ":PAGE:MEAS:QSCV:VAR1:COMP 0.1",
            False,
        ),
        ("get_var1_compliance", (), ":PAGE:MEAS:QSCV:VAR1:COMP?", True),
        # VAR1:CSTEp
        ("set_var1_cstep", (0.1,), ":PAGE:MEAS:QSCV:VAR1:CSTE 0.1", False),
        ("get_var1_cstep", (), ":PAGE:MEAS:QSCV:VAR1:CSTE?", True),
        # VAR1:MODE
        (
            "set_var1_mode",
            ("SINGLE",),
            ":PAGE:MEAS:QSCV:VAR1:MODE SINGLE",
            False,
        ),
        ("get_var1_mode", (), ":PAGE:MEAS:QSCV:VAR1:MODE?", True),
        # VAR1:STARt
        ("set_var1_start", (0.0,), ":PAGE:MEAS:QSCV:VAR1:STAR 0.0", False),
        ("get_var1_start", (), ":PAGE:MEAS:QSCV:VAR1:STAR?", True),
        # VAR1:STEP
        ("set_var1_step", (0.1,), ":PAGE:MEAS:QSCV:VAR1:STEP 0.1", False),
        ("get_var1_step", (), ":PAGE:MEAS:QSCV:VAR1:STEP?", True),
        # VAR1:STOP
        ("set_var1_stop", (10.0,), ":PAGE:MEAS:QSCV:VAR1:STOP 10.0", False),
        ("get_var1_stop", (), ":PAGE:MEAS:QSCV:VAR1:STOP?", True),
        # ZCANcel
        ("set_zero_cancel", ("ON",), ":PAGE:MEAS:QSCV:ZCAN ON", False),
        ("get_zero_cancel", (), ":PAGE:MEAS:QSCV:ZCAN?", True),
        # ZVAL? (query only)
        ("get_zero_value", (), ":PAGE:MEAS:QSCV:ZVAL?", True),
    ],
)
def test_command_build(builder, method, args, expected, is_query):
    getattr(builder, method)(*args)
    assert builder.is_command_query is is_query
    assert builder.build() == expected


@pytest.mark.parametrize(
    ("method", "args", "match"),
    [
        ("set_cap_name", ("1BAD",), "Name must be"),  # first char not letter
        ("set_cap_name", ("TOOLONG",), "Name must be"),  # over 6 characters
        ("set_leak_name", ("a b",), "Name must be"),  # non-alphanumeric
        ("set_cap_integration_time", (0.01,), "integration time"),  # < min
        ("set_cap_integration_time", (500.0,), "integration time"),  # > max
        ("set_leak_integration_time", (5.0,), "integration time"),  # > max
        ("set_range", (5e-9,), "Measurement range"),  # not allowed value
        ("set_smu_compliance", ("SMU1", 250.0), "Compliance"),  # +/-200
        ("set_vsu_source", ("VSU1", 25.0), "VSU source"),  # +/-20
        ("set_var1_compliance", (2.0,), "VAR1 compliance"),  # +/-1 A
        ("set_var1_cstep", (20.0,), "cstep"),  # above 10 V
        ("set_var1_step", (500.0,), "VAR1 step"),  # +/-400
        ("set_unit", ("SMU9",), "Invalid parameter"),  # invalid literal
        ("set_sweep_stop", ("INVALID",), "Invalid parameter"),  # invalid
    ],
)
def test_invalid_parameters_raise(builder, method, args, match):
    with pytest.raises(ValueError, match=match):
        getattr(builder, method)(*args)
