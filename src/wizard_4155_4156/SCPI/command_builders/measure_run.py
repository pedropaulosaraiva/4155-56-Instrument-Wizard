from typing import ClassVar, Final

from wizard_4155_4156.SCPI.literals_definition import (
    AxisType,
    BoolType,
    BorderType,
    FormatDataType,
)

from .base_builder import SCPICommandBuilder


class MeasureRunCommandBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ""

    MIN_LIST_VARS: Final[int] = 1
    MAX_LIST_VARS: Final[int] = 8

    def __init__(self):
        super().__init__()

    def set_display_list_select(self, *var_names: str):
        if len(var_names) > self.MAX_LIST_VARS:
            raise ValueError(
                f"Cannot define more than {self.MAX_LIST_VARS} data vars in "
                f"lists. Input length: {len(var_names)}"
            )
        elif len(var_names) < self.MIN_LIST_VARS:
            raise ValueError(
                f"Cannot define less than {self.MIN_LIST_VARS} data vars in "
                f"lists. Input length: {len(var_names)}"
            )

        formatted_vars = ",".join(f"'{var}'" for var in var_names)
        self._add_command_segment(f":PAGE:DISP:LIST {formatted_vars}")
        self._is_command_ready = True

    def get_display_list_select(self):
        self._add_command_segment(":PAGE:DISP:LIST?")
        self._is_command_ready = True
        self._is_command_query = True

    def execute_single_measurement(self):
        self._add_command_segment(":PAGE:SCON:SING")
        self._is_command_ready = True

    def set_standby(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":PAGE:SCON:STAN {state}")
        self._is_command_ready = True

    def get_standby(self):
        self._add_command_segment(":PAGE:SCON:STAN?")
        self._is_command_ready = True
        self._is_command_query = True

    def get_state(self):
        self._add_command_segment(":PAGE:SCON:STAT?")
        self._is_command_ready = True
        self._is_command_query = True

    def stop_operation(self):
        self._add_command_segment(":PAGE:SCON:STOP")
        self._is_command_ready = True

    def get_trace_data(self, data_variable_name: str):
        self._add_command_segment(f":DATA? '{data_variable_name}'")
        self._is_command_ready = True
        self._is_command_query = True

    def delete_all_display_list(self):
        self._add_command_segment(":PAGE:DISP:LIST:DEL:ALL")
        self._is_command_ready = True

    def delete_graphics_axis(self, axis: AxisType):
        self._verify_parameter(axis, AxisType)
        self._add_command_segment(f":PAGE:DISP:GRAP:{axis}:DEL")
        self._is_command_ready = True

    def set_format_data(self, data_format: FormatDataType, length: int = 64):
        command = f":FORM {data_format}"

        if data_format in {"REAL"} and length is not None:
            if length not in {32, 64}:
                raise ValueError(
                    "Valid lengths for REAL format are 32 and 64 bits."
                    f"Input: {length}"
                )
            command += f",{length}"

        self._add_command_segment(command)
        self._is_command_ready = True

    def get_format_data(self):
        self._add_command_segment(":FORM?")
        self._is_command_ready = True
        self._is_command_query = True

    def set_format_border(self, border: BorderType):
        self._add_command_segment(f":FORM:BORD {border}")
        self._is_command_ready = True

    def get_format_border(self):
        self._add_command_segment(":FORM:BORD?")
        self._is_command_ready = True
        self._is_command_query = True
