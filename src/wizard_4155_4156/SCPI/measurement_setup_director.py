from typing import Any

from wizard_4155_4156.SCPI.base_director import BaseDirector, CommandPair
from wizard_4155_4156.SCPI.command_builders import (
    ChannelsCommandBuilder,
    CommonCommandBuilder,
    MeasurementsSetupCommandBuilder,
    MeasureQscvCommandBuilder,
    MeasureRunCommandBuilder,
    MeasureSamplingCommandBuilder,
    MeasureSweepCommandBuilder,
)

SCPI_TRUE_STRINGS = ("TRUE", "1", "YES", "ON")
SCPI_FALSE_STRINGS = ("FALSE", "0", "NO", "OFF")


class MeasurementSetupDirector(BaseDirector):
    @staticmethod
    def _parse_bool(val: Any) -> bool:
        """Converts strings like 'True', 'False' or 1/0 to Python boolean."""
        if isinstance(val, str):
            return val.strip().upper() in SCPI_TRUE_STRINGS
        return bool(val)

    @staticmethod
    def _parse_bool_to_scpi_state(val: Any) -> str:
        """
        Converts Python bools or string representations of bools to 'ON'/'OFF'.
        """
        if isinstance(val, str):
            val_upper = val.strip().upper()
            if val_upper in SCPI_TRUE_STRINGS:
                return "ON"
            elif val_upper in SCPI_FALSE_STRINGS:
                return "OFF"
            return val_upper
        return "ON" if val else "OFF"

    def reset_instrument(self) -> list[CommandPair]:
        scpi_sequence: list[CommandPair] = []

        scpi_sequence.append(
            self._build_pair(
                CommonCommandBuilder, CommonCommandBuilder.reset, ()
            )
        )
        scpi_sequence.append(
            self._build_pair(
                CommonCommandBuilder, CommonCommandBuilder.clear, ()
            )
        )

        # Disable auto self-calibration. Ordering is load-bearing: this MUST
        # follow *RST, which resets :CAL:AUTO to its power-on default (ON).
        # Moving it before *RST would silently re-enable auto-calibration.
        scpi_sequence.append(
            self._build_pair(
                CommonCommandBuilder,
                CommonCommandBuilder.set_auto_calibration,
                ("OFF",),
                CommonCommandBuilder.get_auto_calibration,
                (),
            )
        )

        # The graph axes and display list are intentionally NOT cleared here:
        # applying the config re-populates them, so they are finalized in
        # `post_setup`, which clears and re-sets them after the config.
        return scpi_sequence

    def build_full_setup(self, config: dict[str, Any]) -> list[CommandPair]:
        """Reset, apply the measurement config, then finalize the display.

        This is the production entry point for configuring the instrument:
        every setup starts from *RST defaults with auto-calibration disabled,
        applies the measurement config, and ends with ``post_setup`` so the
        graph/list reflect the chosen display variables rather than whatever
        the instrument auto-assigned while the config commands were applied.
        """
        return (
            self.reset_instrument()
            + self.setup_measurement(config)
            + self.post_setup(config)
        )

    def post_setup(self, config: dict[str, Any]) -> list[CommandPair]:
        """Finalize the display after the config commands have been applied.

        Applying channel/variable config makes the instrument auto-assign
        graph axis variables and list entries. This runs *after* all config
        commands to undo that: clear each graph axis, clear the list, then set
        the list to the user's chosen display variables. Ordering follows the
        intended sequence (graph reset -> list reset -> list set); the list-set
        is deliberately the final command of the setup phase.
        """
        commands: list[CommandPair] = []

        for axis in ("X", "Y1", "Y2"):
            commands.append(
                self._build_pair(
                    MeasureRunCommandBuilder,
                    MeasureRunCommandBuilder.delete_graphics_axis,
                    (axis,),
                )
            )

        commands.append(
            self._build_pair(
                MeasureRunCommandBuilder,
                MeasureRunCommandBuilder.delete_all_display_list,
                (),
            )
        )

        if "display_vars" in config and config["display_vars"]:
            commands.append(
                self._build_pair(
                    MeasureRunCommandBuilder,
                    MeasureRunCommandBuilder.set_display_list_select,
                    tuple(config["display_vars"]),
                    MeasureRunCommandBuilder.get_display_list_select,
                    (),
                )
            )

        return commands

    def setup_measurement(self, config: dict[str, Any]) -> list[CommandPair]:
        scpi_sequence: list[CommandPair] = []

        mode = config.get("mode")
        if mode:
            scpi_sequence.append(
                self._build_pair(
                    ChannelsCommandBuilder,
                    ChannelsCommandBuilder.set_mode,
                    (mode,),
                    ChannelsCommandBuilder.get_mode,
                    (),
                )
            )

        if "channels" in config:
            scpi_sequence.extend(self._setup_channels(config["channels"]))

        if "measurement_setup" in config:
            scpi_sequence.extend(
                self._setup_general_measurement(config["measurement_setup"])
            )

        if mode == "SWEEP" and "sweep_setup" in config:
            scpi_sequence.extend(self._setup_sweep(config["sweep_setup"]))

        elif mode == "SAMP" and "sampling_setup" in config:
            scpi_sequence.extend(
                self._setup_sampling(config["sampling_setup"])
            )

        elif mode == "QSCV" and "qscv_setup" in config:
            scpi_sequence.extend(self._setup_qscv(config["qscv_setup"]))

        # The display list / graph are NOT set here on purpose: applying the
        # config above makes the instrument auto-assign them, so they are
        # finalized in `post_setup`, which runs after all config commands.
        return scpi_sequence

    def _setup_channels(
        self, channels_config: dict[str, Any]
    ) -> list[CommandPair]:
        commands = []
        builder = ChannelsCommandBuilder

        for unit, settings in channels_config.items():
            if "disable" in settings and self._parse_bool(settings["disable"]):
                commands.append(
                    self._build_pair(
                        builder, builder.set_disable, (unit,), None, ()
                    )
                )
                continue

            if "v_name" in settings:
                commands.append(
                    self._build_pair(
                        builder,
                        builder.set_v_name,
                        (unit, settings["v_name"]),
                        builder.get_v_name,
                        (unit,),
                    )
                )
            if "i_name" in settings:
                commands.append(
                    self._build_pair(
                        builder,
                        builder.set_i_name,
                        (unit, settings["i_name"]),
                        builder.get_i_name,
                        (unit,),
                    )
                )
            if "function" in settings:
                commands.append(
                    self._build_pair(
                        builder,
                        builder.set_function,
                        (unit, settings["function"]),
                        builder.get_function,
                        (unit,),
                    )
                )
            if "smu_mode" in settings:
                commands.append(
                    self._build_pair(
                        builder,
                        builder.set_smu_mode,
                        (unit, settings["smu_mode"]),
                        builder.get_smu_mode,
                        (unit,),
                    )
                )
            if "vmu_mode" in settings:
                commands.append(
                    self._build_pair(
                        builder,
                        builder.set_vmu_mode,
                        (unit, settings["vmu_mode"]),
                        builder.get_vmu_mode,
                        (unit,),
                    )
                )
            if "standby" in settings:
                commands.append(
                    self._build_pair(
                        builder,
                        builder.set_standby_mode,
                        (
                            unit,
                            self._parse_bool_to_scpi_state(
                                settings["standby"]
                            ),
                        ),
                        builder.get_standby_mode,
                        (unit,),
                    )
                )

        return commands

    def _setup_general_measurement(
        self, mset_config: dict[str, Any]
    ) -> list[CommandPair]:
        commands = []
        builder = MeasurementsSetupCommandBuilder

        if "integration_mode" in mset_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_integration_mode,
                    (mset_config["integration_mode"],),
                    builder.get_integration_mode,
                    (),
                )
            )
        if "short_time" in mset_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_short_time,
                    (mset_config["short_time"],),
                    builder.get_short_time,
                    (),
                )
            )
        if "long_time_cycles" in mset_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_long_time,
                    (mset_config["long_time_cycles"],),
                    builder.get_long_time,
                    (),
                )
            )
        if "wait_time" in mset_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_wait_time,
                    (mset_config["wait_time"],),
                    builder.get_wait_time,
                    (),
                )
            )

        if "ranges" in mset_config:
            for unit, r_data in mset_config["ranges"].items():
                if "mode" in r_data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_range_mode,
                            (unit, r_data["mode"]),
                            builder.get_range_mode,
                            (unit,),
                        )
                    )
                if "value" in r_data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_range,
                            (unit, r_data["value"]),
                            builder.get_range,
                            (unit,),
                        )
                    )

        return commands

    def _setup_sweep(self, sweep_config: dict[str, Any]) -> list[CommandPair]:
        commands = []
        builder = MeasureSweepCommandBuilder

        if "delay" in sweep_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_delay,
                    (sweep_config["delay"],),
                    builder.get_delay,
                    (),
                )
            )
        if "hold_time" in sweep_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_hold_time,
                    (sweep_config["hold_time"],),
                    builder.get_hold_time,
                    (),
                )
            )
        if "sweep_stop" in sweep_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_sweep_stop,
                    (sweep_config["sweep_stop"],),
                    builder.get_sweep_stop,
                    (),
                )
            )

        var1 = sweep_config.get("var1", {})
        if "mode" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_mode,
                    (var1["mode"],),
                    builder.get_var1_mode,
                    (),
                )
            )
        if "spacing" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_spacing,
                    (var1["spacing"],),
                    builder.get_var1_spacing,
                    (),
                )
            )
        if "start" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_start,
                    (var1["start"],),
                    builder.get_var1_start,
                    (),
                )
            )
        if "stop" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_stop,
                    (var1["stop"],),
                    builder.get_var1_stop,
                    (),
                )
            )
        if "step" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_step,
                    (var1["step"],),
                    builder.get_var1_step,
                    (),
                )
            )
        if "compliance" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_compliance,
                    (var1["compliance"],),
                    builder.get_var1_compliance,
                    (),
                )
            )
        if "pcompliance" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_pcompliance,
                    (var1["pcompliance"],),
                    builder.get_var1_pcompliance,
                    (),
                )
            )
        # ! Not sure if pcompliance_state is necessary
        if "pcompliance_state" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_pcompliance_state,
                    (
                        self._parse_bool_to_scpi_state(
                            var1["pcompliance_state"]
                        ),
                    ),
                    builder.get_var1_pcompliance_state,
                    (),
                )
            )

        var2 = sweep_config.get("var2", {})
        if "start" in var2:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var2_start,
                    (var2["start"],),
                    builder.get_var2_start,
                    (),
                )
            )
        if "step" in var2:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var2_step,
                    (var2["step"],),
                    builder.get_var2_step,
                    (),
                )
            )
        if "n_of_steps" in var2:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var2_n_of_steps,
                    (var2["n_of_steps"],),
                    builder.get_var2_n_of_steps,
                    (),
                )
            )
        if "compliance" in var2:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var2_compliance,
                    (var2["compliance"],),
                    builder.get_var2_compliance,
                    (),
                )
            )
        if "pcompliance" in var2:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var2_pcompliance,
                    (var2["pcompliance"],),
                    builder.get_var2_pcompliance,
                    (),
                )
            )
        # ! Not sure if pcompliance_state is necessary
        if "pcompliance_state" in var2:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var2_pcompliance_state,
                    (
                        self._parse_bool_to_scpi_state(
                            var2["pcompliance_state"]
                        ),
                    ),
                    builder.get_var2_pcompliance_state,
                    (),
                )
            )

        vard = sweep_config.get("vard", {})
        if "offset" in vard:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_vard_offset,
                    (vard["offset"],),
                    builder.get_vard_offset,
                    (),
                )
            )
        if "ratio" in vard:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_vard_ratio,
                    (vard["ratio"],),
                    builder.get_vard_ratio,
                    (),
                )
            )
        if "compliance" in vard:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_vard_compliance,
                    (vard["compliance"],),
                    builder.get_vard_compliance,
                    (),
                )
            )
        if "pcompliance" in vard:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_vard_pcompliance,
                    (vard["pcompliance"],),
                    builder.get_vard_pcompliance,
                    (),
                )
            )

        # ! Not sure if pcompliance_state is necessary
        if "pcompliance_state" in vard:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_vard_pcompliance_state,
                    (
                        self._parse_bool_to_scpi_state(
                            vard["pcompliance_state"]
                        ),
                    ),
                    builder.get_vard_pcompliance_state,
                    (),
                )
            )

        pulse = sweep_config.get("pulse", {})
        if "base" in pulse:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_pulse_base,
                    (pulse["base"],),
                    builder.get_pulse_base,
                    (),
                )
            )
        if "period" in pulse:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_pulse_period,
                    (pulse["period"],),
                    builder.get_pulse_period,
                    (),
                )
            )
        if "width" in pulse:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_pulse_width,
                    (pulse["width"],),
                    builder.get_pulse_width,
                    (),
                )
            )

        constants = sweep_config.get("constants", {})
        for unit, data in constants.items():
            if "SMU" in unit:
                if "source" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_smu_source,
                            (unit, data["source"]),
                            builder.get_smu_source,
                            (unit,),
                        )
                    )
                if "compliance" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_smu_compliance,
                            (unit, data["compliance"]),
                            builder.get_smu_compliance,
                            (unit,),
                        )
                    )
            elif "VSU" in unit:
                if "source" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_vsu_source,
                            (unit, data["source"]),
                            builder.get_vsu_source,
                            (unit,),
                        )
                    )

        return commands

    def _setup_qscv(self, qscv_config: dict[str, Any]) -> list[CommandPair]:
        commands = []
        builder = MeasureQscvCommandBuilder

        if "cap_integration_time" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_cap_integration_time,
                    (qscv_config["cap_integration_time"],),
                    builder.get_cap_integration_time,
                    (),
                )
            )
        if "leak_integration_time" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_leak_integration_time,
                    (qscv_config["leak_integration_time"],),
                    builder.get_leak_integration_time,
                    (),
                )
            )
        if "delay" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_delay,
                    (qscv_config["delay"],),
                    builder.get_delay,
                    (),
                )
            )
        if "hold_time" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_hold_time,
                    (qscv_config["hold_time"],),
                    builder.get_hold_time,
                    (),
                )
            )
        if "cap_name" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_cap_name,
                    (qscv_config["cap_name"],),
                    builder.get_cap_name,
                    (),
                )
            )
        if "leak_name" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_leak_name,
                    (qscv_config["leak_name"],),
                    builder.get_leak_name,
                    (),
                )
            )
        if "range" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_range,
                    (qscv_config["range"],),
                    builder.get_range,
                    (),
                )
            )
        if "sweep_stop" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_sweep_stop,
                    (qscv_config["sweep_stop"],),
                    builder.get_sweep_stop,
                    (),
                )
            )
        if "unit" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_unit,
                    (qscv_config["unit"],),
                    builder.get_unit,
                    (),
                )
            )
        if "leak_cancel" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_leak_cancel,
                    (
                        self._parse_bool_to_scpi_state(
                            qscv_config["leak_cancel"]
                        ),
                    ),
                    builder.get_leak_cancel,
                    (),
                )
            )
        if "zero_cancel" in qscv_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_zero_cancel,
                    (
                        self._parse_bool_to_scpi_state(
                            qscv_config["zero_cancel"]
                        ),
                    ),
                    builder.get_zero_cancel,
                    (),
                )
            )

        var1 = qscv_config.get("var1", {})
        if "mode" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_mode,
                    (var1["mode"],),
                    builder.get_var1_mode,
                    (),
                )
            )
        if "start" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_start,
                    (var1["start"],),
                    builder.get_var1_start,
                    (),
                )
            )
        if "stop" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_stop,
                    (var1["stop"],),
                    builder.get_var1_stop,
                    (),
                )
            )
        if "step" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_step,
                    (var1["step"],),
                    builder.get_var1_step,
                    (),
                )
            )
        if "cstep" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_cstep,
                    (var1["cstep"],),
                    builder.get_var1_cstep,
                    (),
                )
            )
        if "compliance" in var1:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_var1_compliance,
                    (var1["compliance"],),
                    builder.get_var1_compliance,
                    (),
                )
            )

        constants = qscv_config.get("constants", {})
        for unit, data in constants.items():
            if "SMU" in unit:
                if "source" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_smu_source,
                            (unit, data["source"]),
                            builder.get_smu_source,
                            (unit,),
                        )
                    )
                if "compliance" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_smu_compliance,
                            (unit, data["compliance"]),
                            builder.get_smu_compliance,
                            (unit,),
                        )
                    )
            elif "VSU" in unit:
                if "source" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_vsu_source,
                            (unit, data["source"]),
                            builder.get_vsu_source,
                            (unit,),
                        )
                    )

        return commands

    def _setup_sampling(
        self, samp_config: dict[str, Any]
    ) -> list[CommandPair]:
        commands = []
        builder = MeasureSamplingCommandBuilder

        if "mode" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_mode,
                    (samp_config["mode"],),
                    builder.get_mode,
                    (),
                )
            )
        if "hold_time" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_hold_time,
                    (samp_config["hold_time"],),
                    builder.get_hold_time,
                    (),
                )
            )
        if "initial_interval" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_initial_interval,
                    (samp_config["initial_interval"],),
                    builder.get_initial_interval,
                    (),
                )
            )
        if "period" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_period,
                    (samp_config["period"],),
                    builder.get_period,
                    (),
                )
            )
        if "period_auto" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_period_auto,
                    (
                        self._parse_bool_to_scpi_state(
                            samp_config["period_auto"]
                        ),
                    ),
                    builder.get_period_auto,
                    (),
                )
            )
        if "points" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_points,
                    (samp_config["points"],),
                    builder.get_points,
                    (),
                )
            )
        if "filter" in samp_config:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_filter,
                    (self._parse_bool_to_scpi_state(samp_config["filter"]),),
                    builder.get_filter,
                    (),
                )
            )

        scon = samp_config.get("scon", {})
        if "event_count" in scon:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_scon_event_count,
                    (scon["event_count"],),
                    builder.get_scon_event_count,
                    (),
                )
            )
        if "enable_delay" in scon:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_scon_enable_delay,
                    (scon["enable_delay"],),
                    builder.get_scon_enable_delay,
                    (),
                )
            )
        if "event" in scon:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_scon_event,
                    (scon["event"],),
                    builder.get_scon_event,
                    (),
                )
            )
        if "name" in scon:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_scon_name,
                    (scon["name"],),
                    builder.get_scon_name,
                    (),
                )
            )
        if "state" in scon:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_scon_state,
                    (self._parse_bool_to_scpi_state(scon["state"]),),
                    builder.get_scon_state,
                    (),
                )
            )
        if "threshold" in scon:
            commands.append(
                self._build_pair(
                    builder,
                    builder.set_scon_threshold,
                    (scon["threshold"],),
                    builder.get_scon_threshold,
                    (),
                )
            )

        constants = samp_config.get("constants", {})
        for unit, data in constants.items():
            if "SMU" in unit:
                if "source" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_smu_source,
                            (unit, data["source"]),
                            builder.get_smu_source,
                            (unit,),
                        )
                    )
                if "compliance" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_smu_compliance,
                            (unit, data["compliance"]),
                            builder.get_smu_compliance,
                            (unit,),
                        )
                    )
            elif "VSU" in unit:
                if "source" in data:
                    commands.append(
                        self._build_pair(
                            builder,
                            builder.set_vsu_source,
                            (unit, data["source"]),
                            builder.get_vsu_source,
                            (unit,),
                        )
                    )

        return commands
