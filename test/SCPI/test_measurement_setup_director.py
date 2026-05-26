import pytest

from wizard_4155_4156.SCPI.measurement_setup_director import (
    MeasurementSetupDirector,
)

SHORT_TIME_VAL = 1e-4
LONG_CYCLES_VAL = 10
WAIT_TIME_VAL = 1.0
RANGE_VAL = 1.0

DELAY_TIME = 0.1
HOLD_TIME = 0.5
SWEEP_START = 0.0
SWEEP_STOP = 1.0
SWEEP_STEP = 0.1
COMPLIANCE = 0.01
PCOMPLIANCE = 1.0
SWEEP_POINTS = 10
VARD_OFFSET = 0.0
VARD_RATIO = 1.0
PULSE_BASE = 0.0
PULSE_PERIOD = 0.01
PULSE_WIDTH = 0.001
CONST_SMU_SOURCE = 5.0
CONST_VSU_SOURCE = 2.0

SAMP_HOLD_TIME = 1.0
SAMP_INITIAL_INTERVAL = 0.1
SAMP_PERIOD = 10.0
SAMP_POINTS = 100
SCON_COUNT = 5
SCON_DELAY = 0.1
SCON_THRESH = 2.0
CONST_SAMP_SMU_SOURCE = 1.0
CONST_SAMP_VSU_SOURCE = 1.0


@pytest.fixture
def setup_director():
    return MeasurementSetupDirector()


def test_reset_instrument(setup_director):
    cmd_rst, cmd_cls, cmd_disp_del = setup_director.reset_instrument()

    assert cmd_rst.set_command == "*RST"
    assert cmd_cls.set_command == "*CLS"
    assert cmd_disp_del.set_command == ":PAGE:DISP:LIST:DEL:ALL"


def test_setup_channels(setup_director):
    config = {
        "SMU1": {"disable": True},
        "SMU2": {
            "v_name": "V2", "i_name": "I2", "function": "VAR1",
            "smu_mode": "V", "standby": "ON"
        },
        "VMU1": {"vu_mode": "V"}
    }

    expected_set_commands = [
        ":PAGE:CHAN:SMU1:DIS",
        ":PAGE:CHAN:SMU2:VNAME 'V2'",
        ":PAGE:CHAN:SMU2:INAME 'I2'",
        ":PAGE:CHAN:SMU2:FUNC VAR1",
        ":PAGE:CHAN:SMU2:MODE V",
        ":PAGE:CHAN:SMU2:STAN ON",
        ":PAGE:CHAN:VMU1:MODE V"
    ]

    seq = setup_director._setup_channels(config)
    assert len(seq) == len(expected_set_commands)

    for actual_pair, expected_cmd in zip(seq, expected_set_commands):
        assert actual_pair.set_command == expected_cmd


def test_setup_general_measurement(setup_director):
    config = {
        "integration_mode": "LONG",
        "short_time": SHORT_TIME_VAL,
        "long_time_cycles": LONG_CYCLES_VAL,
        "wait_time": WAIT_TIME_VAL,
        "ranges": {"SMU1": {"mode": "FIX", "value": RANGE_VAL}}
    }

    cmd_itim, cmd_shor, cmd_long, cmd_wait, cmd_rang_mode, cmd_rang = (
        setup_director._setup_general_measurement(config)
    )

    assert cmd_itim.set_command == ":PAGE:MEAS:MSET:ITIM  LONG"

    assert (
        cmd_shor.set_command ==
        f":PAGE:MEAS:MSET:ITIM:SHOR  {SHORT_TIME_VAL:e}"
    )
    assert (
        cmd_long.set_command == f":PAGE:MEAS:MSET:ITIM:LONG {LONG_CYCLES_VAL}"
    )
    assert cmd_wait.set_command == f":PAGE:MEAS:MSET:WTIM  {WAIT_TIME_VAL:.1f}"
    assert cmd_rang_mode.set_command == ":PAGE:MEAS:MSET:SMU1:RANG:MODE FIX"
    assert cmd_rang.set_command == f":PAGE:MEAS:MSET:SMU1:RANG {RANGE_VAL}"


def test_setup_sweep_full(setup_director):
    config = {
        "delay": DELAY_TIME, "hold_time": HOLD_TIME,
        "sweep_stop": "COMPLIANCE",
        "var1": {
            "mode": "SINGLE", "spacing": "LINEAR",
            "start": SWEEP_START, "stop": SWEEP_STOP,
            "step": SWEEP_STEP, "compliance": COMPLIANCE,
            "pcompliance": PCOMPLIANCE,
            "pcompliance_state": "ON"
        },
        "var2": {
            "start": SWEEP_START, "step": SWEEP_STEP, "points": SWEEP_POINTS,
            "compliance": COMPLIANCE,
            "pcompliance": PCOMPLIANCE, "pcompliance_state": "ON"
        },
        "vard": {
            "offset": VARD_OFFSET, "ratio": VARD_RATIO,
            "compliance": COMPLIANCE,
            "pcompliance": PCOMPLIANCE, "pcompliance_state": "ON"
        },
        "pulse": {
            "base": PULSE_BASE, "period": PULSE_PERIOD, "width": PULSE_WIDTH
        },
        "constants": {
            "SMU3": {"source": CONST_SMU_SOURCE, "compliance": COMPLIANCE},
            "VSU1": {"source": CONST_VSU_SOURCE}
        }
    }

    expected_set_commands = [
        f":PAGE:MEAS:SWE:DEL {DELAY_TIME}",
        f":PAGE:MEAS:SWE:HTIM {HOLD_TIME}",
        ":PAGE:MEAS:SWE:SST COMPLIANCE",
        ":PAGE:MEAS:SWE:VAR1:MODE SINGLE",
        ":PAGE:MEAS:SWE:VAR1:SPAC LINEAR",
        f":PAGE:MEAS:SWE:VAR1:STAR {SWEEP_START}",
        f":PAGE:MEAS:SWE:VAR1:STOP {SWEEP_STOP}",
        f":PAGE:MEAS:SWE:VAR1:STEP {SWEEP_STEP}",
        f":PAGE:MEAS:SWE:VAR1:COMP {COMPLIANCE}",
        f":PAGE:MEAS:SWE:VAR1:PCOM {PCOMPLIANCE}",
        ":PAGE:MEAS:SWE:VAR1:PCOM:STAT ON",
        f":PAGE:MEAS:SWE:VAR2:STAR {SWEEP_START}",
        f":PAGE:MEAS:SWE:VAR2:STEP {SWEEP_STEP}",
        f":PAGE:MEAS:SWE:VAR2:POIN {SWEEP_POINTS}",
        f":PAGE:MEAS:SWE:VAR2:COMP {COMPLIANCE}",
        f":PAGE:MEAS:SWE:VAR2:PCOM {PCOMPLIANCE}",
        ":PAGE:MEAS:SWE:VAR2:PCOM:STAT ON",
        f":PAGE:MEAS:SWE:VARD:OFFS {VARD_OFFSET}",
        f":PAGE:MEAS:SWE:VARD:RAT {VARD_RATIO}",
        f":PAGE:MEAS:SWE:VARD:COMP {COMPLIANCE}",
        f":PAGE:MEAS:SWE:VARD:PCOM {PCOMPLIANCE}",
        ":PAGE:MEAS:SWE:VARD:PCOM:STAT ON",
        f":PAGE:MEAS:SWE:PULS:BASE {PULSE_BASE}",
        f":PAGE:MEAS:SWE:PULS:PER {PULSE_PERIOD}",
        f":PAGE:MEAS:SWE:PULS:WIDT {PULSE_WIDTH}",
        f":PAGE:MEAS:SWE:CONS:SMU3:SOUR {CONST_SMU_SOURCE}",
        f":PAGE:MEAS:SWE:CONS:SMU3:COMP {COMPLIANCE}",
        f":PAGE:MEAS:SWE:CONS:VSU1:SOUR {CONST_VSU_SOURCE}",
    ]

    seq = setup_director._setup_sweep(config)
    assert len(seq) == len(expected_set_commands)

    for actual_pair, expected_cmd in zip(seq, expected_set_commands):
        assert actual_pair.set_command == expected_cmd


def test_setup_sampling_full(setup_director):
    config = {
        "mode": "LINEAR", "hold_time": SAMP_HOLD_TIME,
        "initial_interval": SAMP_INITIAL_INTERVAL,
        "period": SAMP_PERIOD, "period_auto": "ON",
        "points": SAMP_POINTS, "filter": "ON",
        "scon": {
            "event_count": SCON_COUNT,
            "enable_delay": SCON_DELAY, "event": "HIGH",
            "name": "VAR1", "state": "ON", "threshold": SCON_THRESH
        },
        "constants": {
            "SMU1": {"source": CONST_SAMP_SMU_SOURCE,
                    "compliance": COMPLIANCE},
            "VSU1": {"source": CONST_SAMP_VSU_SOURCE}
        }
    }

    expected_set_commands = [
        ":PAGE:MEAS:SAMP:MODE LINEAR",
        f":PAGE:MEAS:SAMP:HTIM {SAMP_HOLD_TIME}",
        f":PAGE:MEAS:SAMP:IINT {SAMP_INITIAL_INTERVAL}",
        f":PAGE:MEAS:SAMP:PER {SAMP_PERIOD}",
        ":PAGE:MEAS:SAMP:PER:AUTO ON",
        f":PAGE:MEAS:SAMP:POIN {SAMP_POINTS}",
        ":PAGE:MEAS:SAMP:FILT ON",
        f":PAGE:MEAS:SAMP:SCON:ECO {SCON_COUNT}",
        f":PAGE:MEAS:SAMP:SCON:EDEL {SCON_DELAY}",
        ":PAGE:MEAS:SAMP:SCON:EVENT HIGH",
        ":PAGE:MEAS:SAMP:SCON:NAME 'VAR1'",
        ":PAGE:MEAS:SAMP:SCON ON",
        f":PAGE:MEAS:SAMP:SCON:THR {SCON_THRESH}",
        f":PAGE:MEAS:SAMP:CONS:SMU1:SOUR {CONST_SAMP_SMU_SOURCE}",
        f":PAGE:MEAS:SAMP:CONS:SMU1:COMP {COMPLIANCE}",
        f":PAGE:MEAS:SAMP:CONS:VSU1:SOUR {CONST_SAMP_VSU_SOURCE}",
    ]

    seq = setup_director._setup_sampling(config)
    assert len(seq) == len(expected_set_commands)

    for actual_pair, expected_cmd in zip(seq, expected_set_commands):
        assert actual_pair.set_command == expected_cmd


def test_setup_measurement_orchestrator(setup_director):
    config_sweep = {
        "mode": "SWEEP",
        "channels": {"SMU1": {"disable": True}},
        "measurement_setup": {"integration_mode": "SHOR"},
        "sweep_setup": {"delay": DELAY_TIME},
        "display_vars": ["V1", "I1"]
    }
    cmd_mode, cmd_chan, cmd_meas, cmd_swe, cmd_disp = (
        setup_director.setup_measurement(config_sweep)
    )

    assert cmd_mode.set_command == ":PAGE:CHAN:MODE SWEEP"
    assert cmd_chan.set_command == ":PAGE:CHAN:SMU1:DIS"
    assert cmd_meas.set_command == ":PAGE:MEAS:MSET:ITIM  SHOR"
    assert cmd_swe.set_command == f":PAGE:MEAS:SWE:DEL {DELAY_TIME}"
    assert cmd_disp.set_command == ":PAGE:DISP:LIST 'V1','I1'"

    config_samp = {
        "mode": "SAMP",
        "sampling_setup": {"points": SAMP_POINTS}
    }
    cmd_mode, cmd_samp = setup_director.setup_measurement(config_samp)

    assert cmd_mode.set_command == ":PAGE:CHAN:MODE SAMP"
    assert cmd_samp.set_command == f":PAGE:MEAS:SAMP:POIN {SAMP_POINTS}"

    seq_empty = setup_director.setup_measurement({})
    assert not seq_empty
