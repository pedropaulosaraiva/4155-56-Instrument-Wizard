from dataclasses import dataclass
from typing import Callable, Type

from wizard_4155_4156.SCPI.command_builders import (
    SCPICommandBuilder,
)


@dataclass
class CommandPair:
    set_command: str | None
    get_command: str | None
    is_binary_query: bool = False
    result_key: str | None = None


class BaseDirector:
    @staticmethod
    def _build_pair(
        builder_class: Type[SCPICommandBuilder],
        setter: Callable | None = None,
        set_args: tuple = (),
        getter: Callable | None = None,
        get_args: tuple = (),
        is_binary_query: bool = False,
        result_key: str | None = None,
    ) -> CommandPair:
        set_str = None
        if setter is not None:
            set_builder = builder_class()
            setter(set_builder, *set_args)
            set_str = set_builder.build()

        get_str = None
        if getter is not None:
            get_builder = builder_class()
            getter(get_builder, *get_args)
            get_str = get_builder.build()

        return CommandPair(
            set_command=set_str,
            get_command=get_str,
            is_binary_query=is_binary_query,
            result_key=result_key,
        )
