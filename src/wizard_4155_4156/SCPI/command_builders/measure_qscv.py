from re import fullmatch
from typing import ClassVar, Final

from wizard_4155_4156.SCPI.literals_definition import (
    BoolType,
    QscvUnitType,
    SMUnitType,
    SweepStopModeType,
    Var1ModeType,
    VSUnitType,
)

from .base_builder import SCPICommandBuilder


class MeasureQscvCommandBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ":PAGE:MEAS:QSCV"

    # Integration times depend on line frequency (50/60 Hz). Without a
    # line-frequency context the builder validates against the permissive
    # union envelope of both frequencies.
    MIN_CINT: Final[float] = 0.033333  # 60 Hz lower bound (50 Hz is 0.04)
    MAX_CINT: Final[float] = 400.0  # 50 Hz upper bound (60 Hz is 333.33)
    MIN_IINT: Final[float] = 0.016667  # 60 Hz lower bound (50 Hz is 0.02)
    MAX_IINT: Final[float] = 2.0  # 50 Hz upper bound (60 Hz is 1.6667)

    MIN_DELAY: Final[float] = 0.0
    MAX_DELAY: Final[float] = 65.535
    MIN_HTIME: Final[float] = 0.0
    MAX_HTIME: Final[float] = 655.35

    MIN_SMU_VAL: Final[float] = -200.0
    MAX_SMU_VAL: Final[float] = 200.0
    MIN_VSU_VAL: Final[float] = -20.0
    MAX_VSU_VAL: Final[float] = 20.0

    MIN_VAR1_VAL: Final[float] = -200.0
    MAX_VAR1_VAL: Final[float] = 200.0
    MIN_VAR1_STEP: Final[float] = -400.0
    MAX_VAR1_STEP: Final[float] = 400.0
    MIN_VAR1_COMP: Final[float] = -1.0
    MAX_VAR1_COMP: Final[float] = 1.0
    MAX_CSTEP: Final[float] = 10.0

    # Measurement range values: 4156C accepts all four, 4155C only the two
    # larger ranges. The builder validates against the union of both.
    ALLOWED_RANGES: Final[frozenset[float]] = frozenset(
        {10e-12, 100e-12, 1e-9, 10e-9}
    )

    def __init__(self):
        super().__init__()

    def _verify_smu_val(self, val: float, param_name: str):
        if not (self.MIN_SMU_VAL <= val <= self.MAX_SMU_VAL):
            raise ValueError(
                f"{param_name} must be between {self.MIN_SMU_VAL} "
                f"and {self.MAX_SMU_VAL} "
                f"(Range depends on SMU V/I type). Input: {val}"
            )

    def _verify_var1_val(self, val: float, param_name: str):
        if not (self.MIN_VAR1_VAL <= val <= self.MAX_VAR1_VAL):
            raise ValueError(
                f"{param_name} must be between {self.MIN_VAR1_VAL} and "
                f"{self.MAX_VAR1_VAL} (Range depends on VAR1 unit type). "
                f"Input: {val}"
            )

    def _verify_var1_comp(self, val: float):
        if not (self.MIN_VAR1_COMP <= val <= self.MAX_VAR1_COMP):
            raise ValueError(
                f"VAR1 compliance must be between {self.MIN_VAR1_COMP} and "
                f"{self.MAX_VAR1_COMP} A (Range depends on VAR1 unit type). "
                f"Input: {val}"
            )

    @staticmethod
    def _verify_name(name: str):
        if not fullmatch(r"[A-Za-z][A-Za-z0-9]{0,5}", name):
            raise ValueError(
                "Name must be up to 6 alphanumeric characters and the first "
                f"character must be a letter. Input: {name!r}"
            )

    def set_cap_integration_time(self, integ_time: float):
        if not (self.MIN_CINT <= integ_time <= self.MAX_CINT):
            raise ValueError(
                "Capacitance integration time must be "
                f"{self.MIN_CINT} <= t <= {self.MAX_CINT}s "
                "(union of 50/60 Hz line frequency ranges). "
                f"Input: {integ_time}"
            )
        self._add_command_segment(f":CINT {integ_time}")
        self._is_command_ready = True

    def get_cap_integration_time(self):
        self._add_command_segment(":CINT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_cap_name(self, name: str):
        self._verify_name(name)
        self._add_command_segment(f":CNAME '{name}'")
        self._is_command_ready = True

    def get_cap_name(self):
        self._add_command_segment(":CNAME?")
        self._is_command_ready = True
        self._is_command_query = True

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
        self._add_command_segment(f":CONS:{unit_type} {source}")
        self._is_command_ready = True

    def get_smu_source(self, unit_type: SMUnitType):
        self._verify_parameter(unit_type, SMUnitType)
        self._add_command_segment(f":CONS:{unit_type}?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_vsu_source(self, unit_type: VSUnitType, source: float):
        self._verify_parameter(unit_type, VSUnitType)
        if not (self.MIN_VSU_VAL <= source <= self.MAX_VSU_VAL):
            raise ValueError(
                f"VSU source must be between {self.MIN_VSU_VAL}V "
                f"and {self.MAX_VSU_VAL}V. Input: {source}"
            )
        self._add_command_segment(f":CONS:{unit_type} {source}")
        self._is_command_ready = True

    def get_vsu_source(self, unit_type: VSUnitType):
        self._verify_parameter(unit_type, VSUnitType)
        self._add_command_segment(f":CONS:{unit_type}?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_delay(self, delay: float):
        if not (self.MIN_DELAY <= delay <= self.MAX_DELAY):
            raise ValueError(
                f"Delay must be {self.MIN_DELAY} <= t <= "
                f"{self.MAX_DELAY}s. Input: {delay}"
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
                f"Hold time must be {self.MIN_HTIME} <= t <= "
                f"{self.MAX_HTIME}s. Input: {hold_time}"
            )
        self._add_command_segment(f":HTIM {hold_time}")
        self._is_command_ready = True

    def get_hold_time(self):
        self._add_command_segment(":HTIM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_leak_integration_time(self, integ_time: float):
        if not (self.MIN_IINT <= integ_time <= self.MAX_IINT):
            raise ValueError(
                "Leakage current integration time must be "
                f"{self.MIN_IINT} <= t <= {self.MAX_IINT}s "
                "(union of 50/60 Hz line frequency ranges). "
                f"Input: {integ_time}"
            )
        self._add_command_segment(f":IINT {integ_time}")
        self._is_command_ready = True

    def get_leak_integration_time(self):
        self._add_command_segment(":IINT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_leak_cancel(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":LCAN {state}")
        self._is_command_ready = True

    def get_leak_cancel(self):
        self._add_command_segment(":LCAN?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_leak_name(self, name: str):
        self._verify_name(name)
        self._add_command_segment(f":LNAME '{name}'")
        self._is_command_ready = True

    def get_leak_name(self):
        self._add_command_segment(":LNAME?")
        self._is_command_ready = True
        self._is_command_query = True

    def go_to_menu(self):
        self._add_command_segment("")
        self._is_command_ready = True

    def set_range(self, meas_range: float):
        if meas_range not in self.ALLOWED_RANGES:
            raise ValueError(
                "Measurement range must be one of "
                f"{sorted(self.ALLOWED_RANGES)} "
                "(4156C: all; 4155C/MPSMU/HPSMU: 1E-9 or 10E-9). "
                f"Input: {meas_range}"
            )
        self._add_command_segment(f":RANG {meas_range}")
        self._is_command_ready = True

    def get_range(self):
        self._add_command_segment(":RANG?")
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

    def set_unit(self, unit_type: QscvUnitType):
        self._verify_parameter(unit_type, QscvUnitType)
        self._add_command_segment(f":UNIT {unit_type}")
        self._is_command_ready = True

    def get_unit(self):
        self._add_command_segment(":UNIT?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_compliance(self, compliance: float):
        self._verify_var1_comp(compliance)
        self._add_command_segment(f":VAR1:COMP {compliance}")
        self._is_command_ready = True

    def get_var1_compliance(self):
        self._add_command_segment(":VAR1:COMP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_cstep(self, cstep: float):
        if not (0 < cstep <= self.MAX_CSTEP):
            raise ValueError(
                "Capacitance measurement voltage (cstep) must be "
                f"0 < cstep <= {self.MAX_CSTEP}V. Input: {cstep}"
            )
        self._add_command_segment(f":VAR1:CSTE {cstep}")
        self._is_command_ready = True

    def get_var1_cstep(self):
        self._add_command_segment(":VAR1:CSTE?")
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

    def set_var1_start(self, start: float):
        self._verify_var1_val(start, "VAR1 Start")
        self._add_command_segment(f":VAR1:STAR {start}")
        self._is_command_ready = True

    def get_var1_start(self):
        self._add_command_segment(":VAR1:STAR?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_step(self, step: float):
        if not (self.MIN_VAR1_STEP <= step <= self.MAX_VAR1_STEP):
            raise ValueError(
                f"VAR1 step must be between {self.MIN_VAR1_STEP} and "
                f"{self.MAX_VAR1_STEP} (Range depends on VAR1 unit type). "
                f"Input: {step}"
            )
        self._add_command_segment(f":VAR1:STEP {step}")
        self._is_command_ready = True

    def get_var1_step(self):
        self._add_command_segment(":VAR1:STEP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_var1_stop(self, stop: float):
        self._verify_var1_val(stop, "VAR1 Stop")
        self._add_command_segment(f":VAR1:STOP {stop}")
        self._is_command_ready = True

    def get_var1_stop(self):
        self._add_command_segment(":VAR1:STOP?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_zero_cancel(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":ZCAN {state}")
        self._is_command_ready = True

    def get_zero_cancel(self):
        self._add_command_segment(":ZCAN?")
        self._is_command_ready = True
        self._is_command_query = True

    def get_zero_value(self):
        self._add_command_segment(":ZVAL?")
        self._is_command_ready = True
        self._is_command_query = True
