from typing import ClassVar, Final

from wizard_4155_4156.SCPI.literals_definition import (
    BoolType,
    PeriodSpecialType,
    SamplingModeType,
    SConEventType,
    SMUnitType,
    VoltageUnitType,
)

from .base_builder import SCPICommandBuilder


class MeasureSamplingCommandBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ":PAGE:MEAS:SAMP"

    MIN_SMU_VAL: Final[float] = -200.0
    MAX_SMU_VAL: Final[float] = 200.0
    MIN_VSU_VAL: Final[float] = -20.0
    MAX_VSU_VAL: Final[float] = 20.0
    MIN_HOLD_TIME: Final[float] = -3e-2
    MAX_HOLD_TIME: Final[float] = 655.35
    MIN_IINT: Final[float] = 60e-6
    MAX_IINT: Final[float] = 65.535
    MIN_PERIOD: Final[float] = 60e-6
    MAX_PERIOD: Final[float] = 1e11
    MIN_POINTS: Final[int] = 1
    MAX_POINTS: Final[int] = 10001
    MIN_ECOUNT: Final[int] = 1
    MAX_ECOUNT: Final[int] = 200
    MIN_EDELAY: Final[float] = 0.0

    def __init__(self):
        super().__init__()

    def _verify_smu_val(self, val: float, param_name: str):
        if not (self.MIN_SMU_VAL <= val <= self.MAX_SMU_VAL):
            raise ValueError(
                f"{param_name} must be between {self.MIN_SMU_VAL} "
                f"and {self.MAX_SMU_VAL} "
                f"(Range depends on SMU V/I type). Input: {val}"
            )

    def set_smu_compliance(self, unit_type: SMUnitType, compliance: float):
        self._verify_parameter(unit_type, SMUnitType)
        self._verify_smu_val(compliance, "SMU Compliance")
        self._add_command_segment(f":CONS:{unit_type}:COMP {compliance}")
        self._is_command_ready = True

    def get_smu_compliance(self, unit_type: SMUnitType):
        self._verify_parameter(unit_type, SMUnitType)
        self._add_command_segment(f":CONS:{unit_type}:COMP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_smu_source(self, unit_type: SMUnitType, source: float):
        self._verify_parameter(unit_type, SMUnitType)
        self._verify_smu_val(source, "SMU Source")
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

    def set_filter(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":FILT {state}")
        self._is_command_ready = True

    def get_filter(self):
        self._add_command_segment(":FILT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_hold_time(self, hold_time: float):
        if not (self.MIN_HOLD_TIME <= hold_time <= self.MAX_HOLD_TIME):
            raise ValueError(
                f"Hold time must be {self.MIN_HOLD_TIME} <= t "
                f"<= {self.MAX_HOLD_TIME}s. Input: {hold_time}"
            )
        self._add_command_segment(f":HTIM {hold_time}")
        self._is_command_ready = True

    def get_hold_time(self):
        self._add_command_segment(":HTIM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_initial_interval(self, interval: float):
        if not (self.MIN_IINT <= interval <= self.MAX_IINT):
            raise ValueError(
                f"Initial interval must be {self.MIN_IINT} <= t "
                f"<= {self.MAX_IINT}s. Input: {interval}"
            )
        self._add_command_segment(f":IINT {interval}")
        self._is_command_ready = True

    def get_initial_interval(self):
        self._add_command_segment(":IINT?")
        self._is_command_ready = True
        self._is_command_query = True

    def go_to_menu(self):
        self._add_command_segment("")
        self._is_command_ready = True

    def set_mode(self, mode: SamplingModeType):
        self._verify_parameter(mode, SamplingModeType)
        self._add_command_segment(f":MODE {mode}")
        self._is_command_ready = True

    def get_mode(self):
        self._add_command_segment(":MODE?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_period(self, period: float | PeriodSpecialType):
        if isinstance(period, str):
            self._verify_parameter(period, PeriodSpecialType)
            self._add_command_segment(f":PER {period}")
        else:
            if not (self.MIN_PERIOD <= period <= self.MAX_PERIOD):
                raise ValueError(
                    "The total sampling time (period) is defined in terms of "
                    "seconds as follows: \n"
                    f"   {self.MIN_PERIOD} <= period <= {self.MAX_PERIOD}\n"
                    f"   Inputed value: {period}"
                )
            self._add_command_segment(f":PER {period}")

        self._is_command_ready = True

    def get_period(self):
        self._add_command_segment(":PER?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_period_auto(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":PER:AUTO {state}")
        self._is_command_ready = True

    def get_period_auto(self):
        self._add_command_segment(":PER:AUTO?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_points(self, points: int):
        if not (self.MIN_POINTS <= points <= self.MAX_POINTS):
            raise ValueError(
                f"Points must be {self.MIN_POINTS} <= points "
                f"<= {self.MAX_POINTS}. Input: {points}"
            )
        self._add_command_segment(f":POIN {points}")
        self._is_command_ready = True

    def get_points(self):
        self._add_command_segment(":POIN?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_scon_event_count(self, count: int):
        if not (self.MIN_ECOUNT <= count <= self.MAX_ECOUNT):
            raise ValueError(
                f"Event count must be {self.MIN_ECOUNT} <= count "
                f"<= {self.MAX_ECOUNT}. Input: {count}"
            )
        self._add_command_segment(f":SCON:ECO {count}")
        self._is_command_ready = True

    def get_scon_event_count(self):
        self._add_command_segment(":SCON:ECO?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_scon_enable_delay(self, delay: float):
        if delay < self.MIN_EDELAY:
            raise ValueError(
                f"Enable delay must be >= {self.MIN_EDELAY}s. Input: {delay}"
            )
        self._add_command_segment(f":SCON:EDEL {delay}")
        self._is_command_ready = True

    def get_scon_enable_delay(self):
        self._add_command_segment(":SCON:EDEL?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_scon_event(self, event: SConEventType):
        self._verify_parameter(event, SConEventType)
        self._add_command_segment(f":SCON:EVENT {event}")
        self._is_command_ready = True

    def get_scon_event(self):
        self._add_command_segment(":SCON:EVENT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_scon_name(self, var_name: str):
        self._add_command_segment(f":SCON:NAME '{var_name}'")
        self._is_command_ready = True

    def get_scon_name(self):
        self._add_command_segment(":SCON:NAME?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_scon_state(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":SCON {state}")
        self._is_command_ready = True

    def get_scon_state(self):
        self._add_command_segment(":SCON?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_scon_threshold(self, threshold: float):
        self._add_command_segment(f":SCON:THR {threshold}")
        self._is_command_ready = True

    def get_scon_threshold(self):
        self._add_command_segment(":SCON:THR?")
        self._is_command_ready = True
        self._is_command_query = True
