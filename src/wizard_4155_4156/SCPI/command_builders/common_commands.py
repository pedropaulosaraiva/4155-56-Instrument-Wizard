
from .base_builder import SCPICommandBuilder


class CommonCommandBuilder(SCPICommandBuilder):
    def __init__(self):
        super().__init__()

    def identify(self):
        self._add_command_segment('*IDN?')
        self._is_command_ready = True
        self._is_command_query = True

    def reset(self):
        self._add_command_segment('*RST')
        self._is_command_ready = True

    def clear(self):
        self._add_command_segment('*CLS')
        self._is_command_ready = True

    def get_operation_complete(self):
        self._add_command_segment('*OPC?')
        self._is_command_ready = True
        self._is_command_query = True
