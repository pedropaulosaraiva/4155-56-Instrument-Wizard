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

QSCV_CINT = 0.1
QSCV_IINT = 0.1
QSCV_DELAY = 0.1
QSCV_HOLD = 0.5
QSCV_RANGE = 1e-9
QSCV_START = 0.0
QSCV_STOP = 1.0
QSCV_STEP = 0.1
QSCV_CSTEP = 0.1
QSCV_COMP = 0.1
CONST_QSCV_SMU_SOURCE = 5.0
CONST_QSCV_VSU_SOURCE = 2.0


@pytest.fixture
def setup_director():
    return MeasurementSetupDirector()


def test_reset_instrument(setup_director):
    cmd_rst, cmd_cls, cmd_cal = setup_director.reset_instrument()

    assert cmd_rst.set_command == "*RST"
    assert cmd_cls.set_command == "*CLS"
    # Auto-calibration must be disabled *after* *RST (which re-enables it).
    assert cmd_cal.set_command == ":CAL:AUTO OFF"
    assert cmd_cal.get_command == ":CAL:AUTO?"
    # The graph axes / display list are NOT cleared here — that is post_setup.


def test_build_full_setup(setup_director):
    config = {
        "mode": "SAMP",
        "sampling_setup": {"points": SAMP_POINTS},
        "display_vars": ["V1", "I1"],
    }

    reset_cmds = setup_director.reset_instrument()
    setup_cmds = setup_director.setup_measurement(config)
    post_cmds = setup_director.post_setup(config)
    full = setup_director.build_full_setup(config)

    # reset -> config -> post_setup, in that order.
    assert full == reset_cmds + setup_cmds + post_cmds
    assert any(pair.set_command == ":CAL:AUTO OFF" for pair in full)
    # post_setup finalizes the display, so the very last command sets the list.
    assert full[-1].set_command == ":PAGE:DISP:LIST 'V1','I1'"


def test_post_setup(setup_director):
    config = {"display_vars": ["V1", "I1"]}

    (
        cmd_grap_x,
        cmd_grap_y1,
        cmd_grap_y2,
        cmd_list_del,
        cmd_list_set,
    ) = setup_director.post_setup(config)

    # Graph axes reset, then list reset, then list set (in that order).
    assert cmd_grap_x.set_command == ":PAGE:DISP:GRAP:X:DEL"
    assert cmd_grap_y1.set_command == ":PAGE:DISP:GRAP:Y1:DEL"
    assert cmd_grap_y2.set_command == ":PAGE:DISP:GRAP:Y2:DEL"
    assert cmd_list_del.set_command == ":PAGE:DISP:LIST:DEL:ALL"
    assert cmd_list_set.set_command == ":PAGE:DISP:LIST 'V1','I1'"


def test_post_setup_without_display_vars(setup_director):
    # No display vars -> graph + list are cleared but the list is not re-set.
    cmds = setup_director.post_setup({})

    assert [pair.set_command for pair in cmds] == [
        ":PAGE:DISP:GRAP:X:DEL",
        ":PAGE:DISP:GRAP:Y1:DEL",
        ":PAGE:DISP:GRAP:Y2:DEL",
        ":PAGE:DISP:LIST:DEL:ALL",
    ]


def test_setup_channels(setup_director):
    config = {
        "SMU1": {"disable": True},
        "SMU2": {
            "v_name": "V2",
            "i_name": "I2",
            "function": "VAR1",
            "smu_mode": "V",
            "standby": "ON",
        },
        "VMU1": {"vmu_mode": "V"},
    }

    expected_set_commands = [
        ":PAGE:CHAN:SMU1:DIS",
        ":PAGE:CHAN:SMU2:VNAME 'V2'",
        ":PAGE:CHAN:SMU2:INAME 'I2'",
        ":PAGE:CHAN:SMU2:FUNC VAR1",
        ":PAGE:CHAN:SMU2:MODE V",
        ":PAGE:CHAN:SMU2:STAN ON",
        ":PAGE:CHAN:VMU1:MODE V",
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
        "ranges": {"SMU1": {"mode": "FIX", "value": RANGE_VAL}},
    }

    cmd_itim, cmd_shor, cmd_long, cmd_wait, cmd_rang_mode, cmd_rang = (
        setup_director._setup_general_measurement(config)
    )

    assert cmd_itim.set_command == ":PAGE:MEAS:MSET:ITIM  LONG"

    assert (
        cmd_shor.set_command
        == f":PAGE:MEAS:MSET:ITIM:SHOR  {SHORT_TIME_VAL:e}"
    )
    assert (
        cmd_long.set_command == f":PAGE:MEAS:MSET:ITIM:LONG {LONG_CYCLES_VAL}"
    )
    assert cmd_wait.set_command == f":PAGE:MEAS:MSET:WTIM  {WAIT_TIME_VAL:.1f}"
    assert cmd_rang_mode.set_command == ":PAGE:MEAS:MSET:SMU1:RANG:MODE FIX"
    assert cmd_rang.set_command == f":PAGE:MEAS:MSET:SMU1:RANG {RANGE_VAL}"


def test_setup_sweep_full(setup_director):
    config = {
        "delay": DELAY_TIME,
        "hold_time": HOLD_TIME,
        "sweep_stop": "COMPLIANCE",
        "var1": {
            "mode": "SINGLE",
            "spacing": "LINEAR",
            "start": SWEEP_START,
            "stop": SWEEP_STOP,
            "step": SWEEP_STEP,
            "compliance": COMPLIANCE,
            "pcompliance": PCOMPLIANCE,
            "pcompliance_state": "ON",
        },
        "var2": {
            "start": SWEEP_START,
            "step": SWEEP_STEP,
            "n_of_steps": SWEEP_POINTS,
            "compliance": COMPLIANCE,
            "pcompliance": PCOMPLIANCE,
            "pcompliance_state": "ON",
        },
        "vard": {
            "offset": VARD_OFFSET,
            "ratio": VARD_RATIO,
            "compliance": COMPLIANCE,
            "pcompliance": PCOMPLIANCE,
            "pcompliance_state": "ON",
        },
        "pulse": {
            "base": PULSE_BASE,
            "period": PULSE_PERIOD,
            "width": PULSE_WIDTH,
        },
        "constants": {
            "SMU3": {"source": CONST_SMU_SOURCE, "compliance": COMPLIANCE},
            "VSU1": {"source": CONST_VSU_SOURCE},
        },
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
        "mode": "LINEAR",
        "hold_time": SAMP_HOLD_TIME,
        "initial_interval": SAMP_INITIAL_INTERVAL,
        "period": SAMP_PERIOD,
        "period_auto": "ON",
        "points": SAMP_POINTS,
        "filter": "ON",
        "scon": {
            "event_count": SCON_COUNT,
            "enable_delay": SCON_DELAY,
            "event": "HIGH",
            "name": "VAR1",
            "state": "ON",
            "threshold": SCON_THRESH,
        },
        "constants": {
            "SMU1": {
                "source": CONST_SAMP_SMU_SOURCE,
                "compliance": COMPLIANCE,
            },
            "VSU1": {"source": CONST_SAMP_VSU_SOURCE},
        },
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


def test_setup_qscv_full(setup_director):
    config = {
        "cap_integration_time": QSCV_CINT,
        "leak_integration_time": QSCV_IINT,
        "delay": QSCV_DELAY,
        "hold_time": QSCV_HOLD,
        "cap_name": "CAP",
        "leak_name": "LEAK",
        "range": QSCV_RANGE,
        "sweep_stop": "OFF",
        "unit": "SMU1",
        "leak_cancel": "ON",
        "zero_cancel": "OFF",
        "var1": {
            "mode": "SINGLE",
            "start": QSCV_START,
            "stop": QSCV_STOP,
            "step": QSCV_STEP,
            "cstep": QSCV_CSTEP,
            "compliance": QSCV_COMP,
        },
        "constants": {
            "SMU3": {
                "source": CONST_QSCV_SMU_SOURCE,
                "compliance": QSCV_COMP,
            },
            "VSU1": {"source": CONST_QSCV_VSU_SOURCE},
        },
    }

    expected_set_commands = [
        f":PAGE:MEAS:QSCV:CINT {QSCV_CINT}",
        f":PAGE:MEAS:QSCV:IINT {QSCV_IINT}",
        f":PAGE:MEAS:QSCV:DEL {QSCV_DELAY}",
        f":PAGE:MEAS:QSCV:HTIM {QSCV_HOLD}",
        ":PAGE:MEAS:QSCV:CNAME 'CAP'",
        ":PAGE:MEAS:QSCV:LNAME 'LEAK'",
        f":PAGE:MEAS:QSCV:RANG {QSCV_RANGE}",
        ":PAGE:MEAS:QSCV:SST OFF",
        ":PAGE:MEAS:QSCV:UNIT SMU1",
        ":PAGE:MEAS:QSCV:LCAN ON",
        ":PAGE:MEAS:QSCV:ZCAN OFF",
        ":PAGE:MEAS:QSCV:VAR1:MODE SINGLE",
        f":PAGE:MEAS:QSCV:VAR1:STAR {QSCV_START}",
        f":PAGE:MEAS:QSCV:VAR1:STOP {QSCV_STOP}",
        f":PAGE:MEAS:QSCV:VAR1:STEP {QSCV_STEP}",
        f":PAGE:MEAS:QSCV:VAR1:CSTE {QSCV_CSTEP}",
        f":PAGE:MEAS:QSCV:VAR1:COMP {QSCV_COMP}",
        f":PAGE:MEAS:QSCV:CONS:SMU3 {CONST_QSCV_SMU_SOURCE}",
        f":PAGE:MEAS:QSCV:CONS:SMU3:COMP {QSCV_COMP}",
        f":PAGE:MEAS:QSCV:CONS:VSU1 {CONST_QSCV_VSU_SOURCE}",
    ]

    seq = setup_director._setup_qscv(config)
    assert len(seq) == len(expected_set_commands)

    for actual_pair, expected_cmd in zip(seq, expected_set_commands):
        assert actual_pair.set_command == expected_cmd


def test_setup_measurement_orchestrator(setup_director):
    config_sweep = {
        "mode": "SWEEP",
        "channels": {"SMU1": {"disable": True}},
        "measurement_setup": {"integration_mode": "SHORT"},
        "sweep_setup": {"delay": DELAY_TIME},
        "display_vars": ["V1", "I1"],
    }
    # The display list is set by post_setup, not setup_measurement.
    cmd_mode, cmd_chan, cmd_meas, cmd_swe = setup_director.setup_measurement(
        config_sweep
    )

    assert cmd_mode.set_command == ":PAGE:CHAN:MODE SWEEP"
    assert cmd_chan.set_command == ":PAGE:CHAN:SMU1:DIS"
    assert cmd_meas.set_command == ":PAGE:MEAS:MSET:ITIM  SHORT"
    assert cmd_swe.set_command == f":PAGE:MEAS:SWE:DEL {DELAY_TIME}"

    config_samp = {"mode": "SAMP", "sampling_setup": {"points": SAMP_POINTS}}
    cmd_mode, cmd_samp = setup_director.setup_measurement(config_samp)

    assert cmd_mode.set_command == ":PAGE:CHAN:MODE SAMP"
    assert cmd_samp.set_command == f":PAGE:MEAS:SAMP:POIN {SAMP_POINTS}"

    config_qscv = {"mode": "QSCV", "qscv_setup": {"delay": QSCV_DELAY}}
    cmd_mode, cmd_qscv = setup_director.setup_measurement(config_qscv)

    assert cmd_mode.set_command == ":PAGE:CHAN:MODE QSCV"
    assert cmd_qscv.set_command == f":PAGE:MEAS:QSCV:DEL {QSCV_DELAY}"

    seq_empty = setup_director.setup_measurement({})
    assert not seq_empty
