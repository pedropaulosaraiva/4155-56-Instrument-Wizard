import pytest

from wizard_4155_4156.SCPI.measurement_run_director import (
    MeasurementRunDirector,
)

FORMAT_REAL_LENGTH = 64
STATE_ON = "ON"
FORMAT_ASC = "ASC"
FORMAT_REAL = "REAL"
BORDER_NORM = "NORM"
VAR_1 = "V1"
VAR_2 = "I1"


@pytest.fixture
def run_director():
    return MeasurementRunDirector()


def test_run_measurement_empty_config(run_director):
    cmd_sing, cmd_stat, cmd_opc = run_director.run_measurement({})

    assert cmd_sing.set_command == ":PAGE:SCON:SING"
    assert cmd_stat.get_command == ":PAGE:SCON:STAT?"
    assert cmd_opc.get_command == "*OPC?"


def test_run_measurement_with_standby(run_director):
    cmd_stan, cmd_sing, cmd_stat, cmd_opc = run_director.run_measurement({
        "standby": STATE_ON
    })

    assert cmd_stan.set_command == f":PAGE:SCON:STAN {STATE_ON}"
    assert cmd_stan.get_command == ":PAGE:SCON:STAN?"
    assert cmd_sing.set_command == ":PAGE:SCON:SING"


def test_take_data_empty_config(run_director):
    seq = run_director.take_data({})
    assert not seq


def test_take_data_partial_format(run_director):
    (cmd_format,) = run_director.take_data({"format": FORMAT_ASC})

    assert cmd_format.set_command == f":FORM {FORMAT_ASC}"
    assert cmd_format.get_command == ":FORM?"


def test_take_data_full_config(run_director):
    config = {
        "format": FORMAT_REAL,
        "length": FORMAT_REAL_LENGTH,
        "border": BORDER_NORM,
        "variables": [VAR_1, VAR_2],
    }
    cmd_form, cmd_bord, cmd_v1, cmd_v2 = run_director.take_data(config)

    assert cmd_form.set_command == f":FORM {FORMAT_REAL},{FORMAT_REAL_LENGTH}"
    assert cmd_bord.set_command == f":FORM:BORD {BORDER_NORM}"
    assert cmd_v1.get_command == f":DATA? '{VAR_1}'"
    assert cmd_v2.get_command == f":DATA? '{VAR_2}'"
