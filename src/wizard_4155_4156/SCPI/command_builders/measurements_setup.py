from typing import ClassVar, Final

from wizard_4155_4156.SCPI.literals_definition import (
    IntegrationType,
    MeasurementUnitType,
    RangeType,
)

from .base_builder import SCPICommandBuilder


class MeasurementsSetupCommandBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ":PAGE:MEAS:MSET"

    _MSETUP_BASE: Final[str] = r":PAGE:MEAS:MSET:(SMU[1-4]|VMU[1-2])"

    MIN_INTEGRATION_TIME_SHORT: Final[float] = 8e-5
    MAX_INTEGRATION_TIME_SHORT: Final[float] = 1.92e-3
    MIN_INTEGRATION_CYCLES_LONG: Final[int] = 2
    MAX_INTEGRATION_CYCLES_LONG: Final[int] = 100
    MIN_WAIT_MULTIPLIER: Final[float] = 0.0
    MAX_WAIT_MULTIPLIER: Final[float] = 10.0

    def __init__(self):
        super().__init__()

    def set_integration_mode(self, mode: IntegrationType):
        self._verify_parameter(mode, IntegrationType)
        self._add_command_segment(":ITIM  " + mode)
        self._is_command_ready = True

    def get_integration_mode(self):
        self._add_command_segment(":ITIM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_long_time(self, number_power_cycles: int):
        if (
            self.MIN_INTEGRATION_CYCLES_LONG
            <= number_power_cycles
            <= self.MAX_INTEGRATION_CYCLES_LONG
        ):
            self._add_command_segment(f":ITIM:LONG {number_power_cycles}")
            self._is_command_ready = True
        else:
            raise ValueError(
                "Long integration time is defined in terms of the "
                "number of power line cycles as follows: "
                f"   {self.MIN_INTEGRATION_CYCLES_LONG} <= nplcycles "
                f"<= {self.MAX_INTEGRATION_CYCLES_LONG}"
                f"   Inputed value: {number_power_cycles}"
            )

    def get_long_time(self):
        self._add_command_segment(":ITIM:LONG?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_short_time(self, time: float):
        if (
            self.MIN_INTEGRATION_TIME_SHORT
            <= time
            <= self.MAX_INTEGRATION_TIME_SHORT
        ):
            self._add_command_segment(f":ITIM:SHOR  {time:e}")
            self._is_command_ready = True
        else:
            raise ValueError(
                "Short integration time is defined in terms of the "
                "aperture, which means time, as follows: "
                f"   {self.MIN_INTEGRATION_TIME_SHORT}<= aperture "
                f"<= {self.MAX_INTEGRATION_TIME_SHORT}"
                f"   Inputed value: {time:e}"
            )

    def get_short_time(self):
        self._add_command_segment(":ITIM:SHOR?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_wait_time(self, wait_time: float):
        if self.MIN_WAIT_MULTIPLIER <= wait_time <= self.MAX_WAIT_MULTIPLIER:
            self._add_command_segment(f":WTIM  {wait_time:.1f}")
            self._is_command_ready = True
        else:
            raise ValueError(
                "The wait time is defined in terms of the "
                "multiplier, which defines the actual wait time, "
                "as follows: "
                f"   {self.MIN_WAIT_MULTIPLIER}<= multiplier "
                f"<= {self.MAX_WAIT_MULTIPLIER}"
                f"   Inputed value: {wait_time:.1f}"
            )

    def get_wait_time(self):
        self._add_command_segment(":WTIM?")
        self._is_command_ready = True
        self._is_command_query = True

    def _unit(self, unit_type: MeasurementUnitType):
        self._verify_parameter(unit_type, MeasurementUnitType)
        self._add_command_segment(":" + unit_type)

    def set_range(self, unit_type: MeasurementUnitType, range_val: float):
        self._unit(unit_type)
        self._add_command_segment(f":RANG {range_val}", self._MSETUP_BASE)
        self._is_command_ready = True

    def get_range(self, unit_type: MeasurementUnitType):
        self._unit(unit_type)
        self._add_command_segment(":RANG?", self._MSETUP_BASE)
        self._is_command_ready = True
        self._is_command_query = True

    def set_range_mode(self, unit_type: MeasurementUnitType, mode: RangeType):
        self._unit(unit_type)
        self._verify_parameter(mode, RangeType)
        self._add_command_segment(f":RANG:MODE {mode}", self._MSETUP_BASE)
        self._is_command_ready = True

    def get_range_mode(self, unit_type: MeasurementUnitType):
        self._unit(unit_type)
        self._add_command_segment(":RANG:MODE?", self._MSETUP_BASE)
        self._is_command_ready = True
        self._is_command_query = True
