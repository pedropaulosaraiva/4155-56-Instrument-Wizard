from typing import ClassVar, Final

from wizard_4155_4156.SCPI.literals_definition import (
    BoolType,
    FunctionType,
    MeasurementUnitType,
    ModeType,
    SMUModeType,
    SMUnitType,
    SourceUnitType,
    UnitType,
    VoltageUnitType,
    VSUnitType,
    VUModeType,
)

from .base_builder import SCPICommandBuilder


class ChannelsCommandBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ":PAGE:CHAN"
    _CHANNEL_BASE: Final[str] = r":PAGE:CHAN:(SMU[1-4]|VMU[1-2]|VSU[1-2])"
    _SOURCE_CHANNEL_BASE: Final[str] = r":PAGE:CHAN:(SMU[1-4]|VSU[1-2])"
    _SMU_CHANNEL_BASE: Final[str] = r":PAGE:CHAN:SMU[1-4]"
    _VU_CHANNEL_BASE: Final[str] = r":PAGE:CHAN:(VMU[1-2]|VSU[1-2])"

    def __init__(self):
        super().__init__()

    def set_all_disable(self):
        self._add_command_segment(":ALL:DIS")
        self._is_command_ready = True

    def set_all_default(self):
        self._add_command_segment(":DEF")
        self._is_command_ready = True

    def set_mode(self, mode: ModeType):
        self._verify_parameter(mode, ModeType)
        self._add_command_segment(":MODE " + mode)
        self._is_command_ready = True

    def get_mode(self):
        self._add_command_segment(":MODE?")
        self._is_command_ready = True
        self._is_command_query = True

    def _unit(self, unit_type: UnitType):
        self._verify_parameter(unit_type, UnitType)
        self._add_command_segment(":" + unit_type)

    def set_disable(self, unit_type: UnitType):
        self._unit(unit_type)
        self._add_command_segment(":DIS", self._CHANNEL_BASE)
        self._is_command_ready = True

    def set_i_name(self, unit_type: SMUnitType, i_name: str):
        self._unit(unit_type)
        self._add_command_segment(f":INAME '{i_name}'", self._SMU_CHANNEL_BASE)
        self._is_command_ready = True

    def get_i_name(self, unit_type: SMUnitType):
        self._unit(unit_type)
        self._add_command_segment(":INAME?", self._SMU_CHANNEL_BASE)
        self._is_command_ready = True
        self._is_command_query = True

    def set_v_name(self, unit_type: UnitType, v_name: str):
        self._unit(unit_type)
        self._add_command_segment(f":VNAME '{v_name}'", self._CHANNEL_BASE)
        self._is_command_ready = True

    def get_v_name(self, unit_type: UnitType):
        self._unit(unit_type)
        self._add_command_segment(":VNAME?", self._CHANNEL_BASE)
        self._is_command_ready = True
        self._is_command_query = True

    def set_function(
        self, unit_type: SourceUnitType, function_type: FunctionType
    ):
        self._unit(unit_type)
        self._verify_parameter(function_type, FunctionType)
        self._add_command_segment(
            ":FUNC " + function_type, self._SOURCE_CHANNEL_BASE
        )
        self._is_command_ready = True

    def get_function(self, unit_type: SourceUnitType):
        self._unit(unit_type)
        self._add_command_segment(":FUNC?", self._SOURCE_CHANNEL_BASE)
        self._is_command_ready = True
        self._is_command_query = True

    def set_smu_mode(self, unit_type: SMUnitType, smu_mode: SMUModeType):
        self._unit(unit_type)
        self._verify_parameter(smu_mode, SMUModeType)
        self._add_command_segment(":MODE " + smu_mode, self._SMU_CHANNEL_BASE)
        self._is_command_ready = True

    def get_smu_mode(self, unit_type: SMUnitType):
        self._unit(unit_type)
        self._add_command_segment(":MODE?", self._SMU_CHANNEL_BASE)
        self._is_command_ready = True
        self._is_command_query = True

    def set_vu_mode(self, unit_type: VSUnitType, vu_mode: VUModeType):
        self._unit(unit_type)
        self._verify_parameter(vu_mode, VUModeType)
        self._add_command_segment(":MODE " + vu_mode, self._VU_CHANNEL_BASE)
        self._is_command_ready = True

    def get_vu_mode(self, unit_type: VoltageUnitType):
        self._unit(unit_type)
        self._add_command_segment(":MODE?", self._VU_CHANNEL_BASE)
        self._is_command_ready = True
        self._is_command_query = True

    def set_standby_mode(
        self, unit_type: MeasurementUnitType, state: BoolType
    ):
        self._unit(unit_type)
        self._verify_parameter(state, BoolType)
        self._add_command_segment(":STAN " + state, self._CHANNEL_BASE)
        self._is_command_ready = True

    def get_standby_mode(self, unit_type: MeasurementUnitType):
        self._unit(unit_type)
        self._add_command_segment(":STAN?", self._CHANNEL_BASE)
        self._is_command_ready = True
        self._is_command_query = True
