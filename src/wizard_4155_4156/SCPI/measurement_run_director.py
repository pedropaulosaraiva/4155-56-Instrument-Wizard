from typing import Any

from wizard_4155_4156.SCPI.base_director import BaseDirector, CommandPair
from wizard_4155_4156.SCPI.command_builders import (
    CommonCommandBuilder,
    MeasureRunCommandBuilder,
)


class MeasurementRunDirector(BaseDirector):
    def run_measurement(self, config: dict[str, Any]) -> list[CommandPair]:
        scpi_sequence: list[CommandPair] = []
        builder = MeasureRunCommandBuilder
        common_builder = CommonCommandBuilder

        if "standby" in config:
            scpi_sequence.append(
                self._build_pair(
                    builder,
                    builder.set_standby,
                    (config["standby"],),
                    builder.get_standby,
                    (),
                )
            )

        scpi_sequence.append(
            self._build_pair(builder, builder.execute_single_measurement, ())
        )

        scpi_sequence.append(
            self._build_pair(builder, None, (), builder.get_state, ())
        )

        scpi_sequence.append(
            self._build_pair(
                common_builder,
                None,
                (),
                common_builder.get_operation_complete,
                (),
            )
        )

        return scpi_sequence

    def take_data(self, config: dict[str, Any]) -> list[CommandPair]:
        scpi_sequence: list[CommandPair] = []
        builder = MeasureRunCommandBuilder

        if "format" in config:
            format_args = (
                (config["format"], config["length"])
                if "length" in config
                else (config["format"],)
            )
            scpi_sequence.append(
                self._build_pair(
                    builder,
                    builder.set_format_data,
                    format_args,
                    builder.get_format_data,
                    (),
                )
            )

        if "border" in config:
            scpi_sequence.append(
                self._build_pair(
                    builder,
                    builder.set_format_border,
                    (config["border"],),
                    builder.get_format_border,
                    (),
                )
            )

        variables = config.get("variables", [])
        for var in variables:
            scpi_sequence.append(
                self._build_pair(
                    builder, None, (), builder.get_trace_data, (var,)
                )
            )

        return scpi_sequence
