from wizard_4155_4156.SCPI.command_builders import SCPICommandBuilder
from wizard_4155_4156.SCPI.literals_definition import BoolType


class CommonCommandBuilder(SCPICommandBuilder):
    def __init__(self):
        super().__init__()

    def identify(self):
        self._add_command_segment("*IDN?")
        self._is_command_ready = True
        self._is_command_query = True

    def reset(self):
        # Soft reset: restores the default page/channel configuration instead
        # of performing a full instrument reset (*RST).
        self._add_command_segment(":PAGE:CHAN:DEF")
        self._is_command_ready = True

    def clear(self):
        self._add_command_segment("*CLS")
        self._is_command_ready = True

    def set_auto_calibration(self, state: BoolType):
        self._verify_parameter(state, BoolType)
        self._add_command_segment(f":CAL:AUTO {state}")
        self._is_command_ready = True

    def get_auto_calibration(self):
        self._add_command_segment(":CAL:AUTO?")
        self._is_command_ready = True
        self._is_command_query = True

    def get_operation_complete(self):
        self._add_command_segment("*OPC?")
        self._is_command_ready = True
        self._is_command_query = True
