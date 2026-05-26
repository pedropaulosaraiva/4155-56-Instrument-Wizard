from re import fullmatch
from typing import Any, ClassVar, Optional, get_args


class SCPICommandBuilder:
    _BASE_COMMAND: ClassVar[str] = ''

    def __init__(self):
        self._building_command: str = ''
        self._is_command_ready: bool = False
        self._is_command_query: bool = False

        self.__reset()

    def __reset(self):
        self._building_command = self._BASE_COMMAND
        self._is_command_ready = False
        self._is_command_query = False

    def __verify_base(
        self, new_segment: str, required_base: Optional[str] = None
    ) -> None:
        base_to_check = (
            self._BASE_COMMAND if required_base is None else required_base
        )

        if not (self._building_command == base_to_check or
            fullmatch(base_to_check, self._building_command)):
            raise ValueError(
                'Building command wrongly constructed.\n'
                f'  Command = {self._building_command}\n'
                f'  Expected Base = {base_to_check}\n'
                f'  Wrong segment = {new_segment}'
            )

    def _add_command_segment(
        self, new_segment: str, required_base: Optional[str] = None
    ):
        self.__verify_base(new_segment, required_base)
        self._building_command += new_segment

    @staticmethod
    def _verify_parameter(value: Any, literal_type: Any) -> None:
        valid_values = get_args(literal_type)
        if value not in valid_values:
            raise ValueError(
                f'Invalid parameter: {value}' +
                f'  Valid parameters: \n {valid_values}'
            )

    @property
    def is_command_query(self) -> bool:
        return self._is_command_query

    def build(self) -> str:
        if self._is_command_ready:
            command = self._building_command
            self.__reset()
            return command
        else:
            raise ValueError(
                'Building command is not completed' +
                f'  Command = {self._building_command}'
            )
