from typing import ClassVar, Final

from wizard_4155_4156.SCPI.literals_definition import (
    BoolType,
    SMUnitType,
    SweepStopModeType,
    Var1ModeType,
    Var1SpacingType,
    VoltageUnitType,
)

from .base_builder import SCPICommandBuilder


class MeasureSweepCommandBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ":PAGE:MEAS:SWE"

    MIN_VAR_VAL: Final[float] = -200.0
    MAX_VAR_VAL: Final[float] = 200.0
    MIN_VAR_STEP: Final[float] = -400.0
    MAX_VAR_STEP: Final[float] = 400.0
    MIN_VSU_VAL: Final[float] = -20.0
    MAX_VSU_VAL: Final[float] = 20.0
    MIN_DELAY: Final[float] = 0.0
    MAX_DELAY: Final[float] = 65.535
    MIN_HTIME: Final[float] = 0.0
    MAX_HTIME: Final[float] = 655.35
    MIN_PULSE_PER: Final[float] = 5e-3
    MAX_PULSE_PER: Final[float] = 1.0
    MIN_PULSE_WID: Final[float] = 5e-4
    MAX_PULSE_WID: Final[float] = 1e-1
    MIN_PCOMP: Final[float] = 1e-3
    MAX_PCOMP: Final[float] = 2.0
    MIN_VAR2_PTS: Final[int] = 1
    MAX_VAR2_PTS: Final[int] = 128

    def __init__(self):
        super().__init__()

    def _verify_var_val(self, val: float, param_name: str):
        if not (self.MIN_VAR_VAL <= val <= self.MAX_VAR_VAL):
            raise ValueError(
                f"{param_name} must be between {self.MIN_VAR_VAL} and"
                f"{self.MAX_VAR_VAL} (Range depends on unit and V/I type). "
                f"Input: {val}"
            )

    def _verify_var_step(self, val: float, param_name: str):
        if not (self.MIN_VAR_STEP <= val <= self.MAX_VAR_STEP):
            raise ValueError(
                f"{param_name} must be between {self.MIN_VAR_STEP} "
                f"and {self.MAX_VAR_STEP} . Input: {val}"
            )

    def _verify_pcomp(self, val: float, param_name: str):
        if not (self.MIN_PCOMP <= val <= self.MAX_PCOMP):
            raise ValueError(
                f"{param_name} must be between {self.MIN_PCOMP} "
                f"and {self.MAX_PCOMP} . Input: {val}"
            )

    def set_smu_compliance(self, unit_type: SMUnitType, compliance: float):
        self._verify_parameter(unit_type, SMUnitType)
        self._verify_var_val(compliance, "SMU Compliance")
        self._add_command_segment(f":CONS:{unit_type}:COMP {compliance}")
        self._is_command_ready = True

    def get_smu_compliance(self, unit_type: SMUnitType):
        self._verify_parameter(unit_type, SMUnitType)
        self._add_command_segment(f":CONS:{unit_type}:COMP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_smu_source(self, unit_type: SMUnitType, source: float):
        self._verify_parameter(unit_type, SMUnitType)
        self._verify_var_val(source, "SMU Source")
        self._add_command_segment(f":CONS:{unit_type}:SOUR {source}")
        self._is_command_ready = True

    def get_smu_source(self, unit_type: SMUnitType):
        self._verify_parameter(unit_type, SMUnitType)
        self._add_command_segment(f":CONS:{unit_type}:SOUR?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vsu_source(self, unit_type: VoltageUnitType, source: float):
        self._verify_parameter(unit_type, VoltageUnitType)
        if not (self.MIN_VSU_VAL <= source <= self.MAX_VSU_VAL):
            raise ValueError(
                f"VSU source must be between {self.MIN_VSU_VAL}V "
                f"and {self.MAX_VSU_VAL}V. Input: {source}"
            )
        self._add_command_segment(f":CONS:{unit_type}:SOUR {source}")
        self._is_command_ready = True

    def get_vsu_source(self, unit_type: VoltageUnitType):
        self._verify_parameter(unit_type, VoltageUnitType)
        self._add_command_segment(f":CONS:{unit_type}:SOUR?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_delay(self, delay: float):
        if not (self.MIN_DELAY <= delay <= self.MAX_DELAY):
            raise ValueError(
                f"Delay must be {self.MIN_DELAY} <= t <="
                f" {self.MAX_DELAY}s. Input: {delay}"
            )
        self._add_command_segment(f":DEL {delay}")
        self._is_command_ready = True

    def get_delay(self):
        self._add_command_segment(":DEL?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_hold_time(self, hold_time: float):
        if not (self.MIN_HTIME <= hold_time <= self.MAX_HTIME):
            raise ValueError(
                f"Hold time must be {self.MIN_HTIME} <= t "
                f"<= {self.MAX_HTIME}s. Input: {hold_time}"
            )
        self._add_command_segment(f":HTIM {hold_time}")
        self._is_command_ready = True

    def get_hold_time(self):
        self._add_command_segment(":HTIM?")
        self._is_command_ready = True
        self._is_command_query = True

    def go_to_menu(self):
        self._add_command_segment("")
        self._is_command_ready = True

    def set_pulse_base(self, base: float):
        self._verify_var_val(base, "Pulse Base")
        self._add_command_segment(f":PULS:BASE {base}")
        self._is_command_ready = True

    def get_pulse_base(self):
        self._add_command_segment(":PULS:BASE?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_pulse_period(self, period: float):
        if not (self.MIN_PULSE_PER <= period <= self.MAX_PULSE_PER):
            raise ValueError(
                f"Pulse period must be {self.MIN_PULSE_PER} <= t"
                f" <= {self.MAX_PULSE_PER}s. Input: {period}"
            )
        self._add_command_segment(f":PULS:PER {period}")
        self._is_command_ready = True

    def get_pulse_period(self):
        self._add_command_segment(":PULS:PER?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_pulse_width(self, width: float):
        if not (self.MIN_PULSE_WID <= width <= self.MAX_PULSE_WID):
            raise ValueError(
                f"Pulse width must be {self.MIN_PULSE_WID} <= t"
                f" <= {self.MAX_PULSE_WID}s. Input: {width}"
            )
        self._add_command_segment(f":PULS:WIDT {width}")
        self._is_command_ready = True

    def get_pulse_width(self):
        self._add_command_segment(":PULS:WIDT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_sweep_stop(self, mode: SweepStopModeType):
        self._verify_parameter(mode, SweepStopModeType)
        self._add_command_segment(f":SST {mode}")
        self._is_command_ready = True

    def get_sweep_stop(self):
        self._add_command_segment(":SST?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_compliance(self, compliance: float):
        self._verify_var_val(compliance, "VAR1 Compliance")
        self._add_command_segment(f":VAR1:COMP {compliance}")
        self._is_command_ready = True

    def get_var1_compliance(self):
        self._add_command_segment(":VAR1:COMP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_mode(self, mode: Var1ModeType):
        self._verify_parameter(mode, Var1ModeType)
        self._add_command_segment(f":VAR1:MODE {mode}")
        self._is_command_ready = True

    def get_var1_mode(self):
        self._add_command_segment(":VAR1:MODE?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_pcompliance(self, pcompliance: float):
        self._verify_pcomp(pcompliance, "VAR1 Power Compliance")
        self._add_command_segment(f":VAR1:PCOM {pcompliance}")
        self._is_command_ready = True

    def get_var1_pcompliance(self):
        self._add_command_segment(":VAR1:PCOM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_pcompliance_state(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":VAR1:PCOM:STAT {state}")
        self._is_command_ready = True

    def get_var1_pcompliance_state(self):
        self._add_command_segment(":VAR1:PCOM:STAT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_spacing(self, spacing: Var1SpacingType):
        self._verify_parameter(spacing, Var1SpacingType)
        self._add_command_segment(f":VAR1:SPAC {spacing}")
        self._is_command_ready = True

    def get_var1_spacing(self):
        self._add_command_segment(":VAR1:SPAC?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_start(self, start: float):
        self._verify_var_val(start, "VAR1 Start")
        self._add_command_segment(f":VAR1:STAR {start}")
        self._is_command_ready = True

    def get_var1_start(self):
        self._add_command_segment(":VAR1:STAR?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_step(self, step: float):
        self._verify_var_step(step, "VAR1 Step")
        self._add_command_segment(f":VAR1:STEP {step}")
        self._is_command_ready = True

    def get_var1_step(self):
        self._add_command_segment(":VAR1:STEP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_stop(self, stop: float):
        self._verify_var_val(stop, "VAR1 Stop")
        self._add_command_segment(f":VAR1:STOP {stop}")
        self._is_command_ready = True

    def get_var1_stop(self):
        self._add_command_segment(":VAR1:STOP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var2_compliance(self, compliance: float):
        self._verify_var_val(compliance, "VAR2 Compliance")
        self._add_command_segment(f":VAR2:COMP {compliance}")
        self._is_command_ready = True

    def get_var2_compliance(self):
        self._add_command_segment(":VAR2:COMP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var2_pcompliance(self, pcompliance: float):
        self._verify_pcomp(pcompliance, "VAR2 Power Compliance")
        self._add_command_segment(f":VAR2:PCOM {pcompliance}")
        self._is_command_ready = True

    def get_var2_pcompliance(self):
        self._add_command_segment(":VAR2:PCOM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var2_pcompliance_state(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":VAR2:PCOM:STAT {state}")
        self._is_command_ready = True

    def get_var2_pcompliance_state(self):
        self._add_command_segment(":VAR2:PCOM:STAT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var2_points(self, points: int):
        if not (self.MIN_VAR2_PTS <= points <= self.MAX_VAR2_PTS):
            raise ValueError(
                f"VAR2 points must be {self.MIN_VAR2_PTS} <= pts"
                f" <= {self.MAX_VAR2_PTS}. Input: {points}"
            )
        self._add_command_segment(f":VAR2:POIN {points}")
        self._is_command_ready = True

    def get_var2_points(self):
        self._add_command_segment(":VAR2:POIN?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var2_start(self, start: float):
        self._verify_var_val(start, "VAR2 Start")
        self._add_command_segment(f":VAR2:STAR {start}")
        self._is_command_ready = True

    def get_var2_start(self):
        self._add_command_segment(":VAR2:STAR?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var2_step(self, step: float):
        self._verify_var_step(step, "VAR2 Step")
        self._add_command_segment(f":VAR2:STEP {step}")
        self._is_command_ready = True

    def get_var2_step(self):
        self._add_command_segment(":VAR2:STEP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vard_compliance(self, compliance: float):
        self._verify_var_val(compliance, "VARD Compliance")
        self._add_command_segment(f":VARD:COMP {compliance}")
        self._is_command_ready = True

    def get_vard_compliance(self):
        self._add_command_segment(":VARD:COMP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vard_offset(self, offset: float):
        self._verify_var_step(offset, "VARD Offset")
        self._add_command_segment(f":VARD:OFFS {offset}")
        self._is_command_ready = True

    def get_vard_offset(self):
        self._add_command_segment(":VARD:OFFS?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vard_pcompliance(self, pcompliance: float):
        self._verify_pcomp(pcompliance, "VARD Power Compliance")
        self._add_command_segment(f":VARD:PCOM {pcompliance}")
        self._is_command_ready = True

    def get_vard_pcompliance(self):
        self._add_command_segment(":VARD:PCOM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vard_pcompliance_state(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":VARD:PCOM:STAT {state}")
        self._is_command_ready = True

    def get_vard_pcompliance_state(self):
        self._add_command_segment(":VARD:PCOM:STAT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vard_ratio(self, ratio: float):
        self._add_command_segment(f":VARD:RAT {ratio}")
        self._is_command_ready = True

    def get_vard_ratio(self):
        self._add_command_segment(":VARD:RAT?")
        self._is_command_ready = True
        self._is_command_query = True
