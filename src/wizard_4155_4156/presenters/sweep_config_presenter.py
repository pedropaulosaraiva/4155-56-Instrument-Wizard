"""
presenters/sweep_config_presenter.py
--------------------------------------
Presenter for the Sweep Configuration page.

What changed from the previous version
----------------------------------------
1. SweepSpacing: LOG10 replaced by L10 / L25 / L50.
2. MeasurementSetup.wait_time → wait_multiplier (0.0 – 10.0).
3. display_var*_context now passes (channel_label, is_voltage, is_vsu)
   instead of (channel_label, sweep_unit, comp_unit).  The view's section
   widgets compute their own unit labels from is_voltage / is_vsu and
   update their own widget bounds via update_ranges().
4. _rebuild_channel_context detects VSU channels assigned to VAR1/VAR2
   and sets var1_is_vsu / var2_is_vsu accordingly (VSU → always voltage,
   ±20 V range).
5. _run_validation is now lean: it only checks cross-parameter rules
   (VAR1 step count, total points).  Per-widget bounds are enforced
   by _SciDoubleEdit in the view — no need to re-validate them here.
6. JSON output key "wait_time" is kept for backward compatibility with
   the user's JSON specification, even though the internal field is
   called wait_multiplier.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject

from wizard_4155_4156.models.channels import (
    VMU_MODE_SCPI_MAP,
    ChannelsConstraints,
)
from wizard_4155_4156.models.config_loader import sweep_config_from_setup
from wizard_4155_4156.models.execution_time import (
    measurement_stat_values,
    sweep_measurement_stats,
)
from wizard_4155_4156.models.sweep_config import (
    DISPLAY_VARS_MAX,
    IntegrationMode,
    SweepConfig,
    SweepConstraints,
    SweepSpacing,
    SweepStop,
    SweepUnitFlags,
    VAR1Mode,
    default_range_config,
)
from wizard_4155_4156.presenters.live_run_helper import (
    LiveMeasurementRunner,
    confirm_quick_instrument_match,
)
from wizard_4155_4156.views.pages.sweep_config_page import SweepConfigPageView

# ── Helpers ─────────────────────────────────────────────────────────────


def _is_voltage_mode(mode_value: str) -> bool:
    """V and VPULSE sweep voltage; I and IPULSE sweep current."""
    return mode_value in ("V", "VPULSE")


def _fn_to_json_key(fn_value: str) -> str:
    """Map UnitFunction SCPI values to JSON-layer keys."""
    if fn_value == "VAR1'":
        return "VARD"
    if fn_value == "CONST":
        return "CONS"
    return fn_value


# ── Presenter ───────────────────────────────────────────────────────────


class SweepConfigPresenter(QObject):
    """
    Mediates between SweepConfigPageView (View) and SweepConfig (Model).

    Public API for other presenters
    --------------------------------
    get_config()  → SweepConfig (deep copy)
    get_json()    → dict   (raises ValueError if cross-param validation fails)
    """

    def __init__(
        self,
        view: SweepConfigPageView,
        channels_snapshot,  # ChannelsConfig — static deep-copied snapshot
        parent: QObject | None = None,
        initial_setup: dict | None = None,  # preload from a saved setup (copy)
        line_frequency_hz: int = 50,  # user preference; scales PLC estimate
        connector_presenter=None,  # ConnectorPresenter — quick apply/run
        settings_provider=None,  # GlobalSettingsManager — reset/cal toggles
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._channels_config = channels_snapshot
        self._line_frequency_hz = line_frequency_hz or 50
        # Ephemeral GPIB apply/run runner + tracked hardware state (None when
        # the page is built without a connector, e.g. in isolated tests).
        self._connector = connector_presenter
        self._runner = (
            LiveMeasurementRunner(connector_presenter, settings_provider)
            if connector_presenter is not None
            else None
        )
        self._connected = (
            connector_presenter.is_connected()
            if connector_presenter is not None
            else False
        )
        self._busy = False
        # When copying an existing setup, preload its
        # parameters; otherwise a fresh default config is
        # built and populated from the channel snapshot.
        self._config = (
            sweep_config_from_setup(initial_setup)
            if initial_setup is not None
            else SweepConfig()
        )

        # Derived once from the static channels snapshot (re-derived on
        # page_activated, which is idempotent against the same snapshot).
        self._ctx: Dict[str, Any] = {
            "instrument_model": "4155C",
            "has_var1": False,
            "has_var2": False,
            "has_vard": False,
            "var1_channel": None,
            "var2_channel": None,
            "vard_channel": None,
            "var1_is_voltage": True,
            "var2_is_voltage": True,
            "var1_is_vsu": False,
            "var2_is_vsu": False,
            "vard_is_vsu": False,
            "has_pulse": False,
            "pulse_channel": None,
            "pulse_is_voltage": True,
            "interlock_open": False,
            "active_channels": [],
            "available_vars": [],
        }

        self._connect_view_signals()
        self._connect_connector_signals()
        # Populate the freshly built page before it is first shown.
        self._on_page_activated()
        self._push_hardware_state()

    # ── Public API ─────────────────────────────────────────────────────

    def get_config(self) -> SweepConfig:
        return copy.deepcopy(self._config)

    def get_instrument_model(self) -> str:
        """Instrument model defined on the channels page for this config."""
        return self._channels_config.instrument_model.value

    def get_json(self) -> dict:
        """Build and return the JSON dict.  Raises ValueError if invalid."""
        errors, _warnings = self._run_validation()
        if errors:
            raise ValueError(
                "Sweep config invalid:\n" + "\n".join(errors.values())
            )
        return self._build_json()

    def get_runtime_bounds(self) -> Optional[Tuple[float, float]]:
        """Estimated minimum-runtime interval (seconds), or None when
        indeterminate — persisted alongside a saved setup."""
        return sweep_measurement_stats(
            self._config,
            self._ctx["active_channels"],
            self._ctx["instrument_model"],
            self._line_frequency_hz,
        ).exec_time

    # ── Signal wiring ──────────────────────────────────────────────────

    def _connect_view_signals(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)

        # Measurement Setup
        v.integration_mode_changed.connect(self._on_integration_mode)
        v.short_time_committed.connect(self._on_short_time)
        v.long_cycles_changed.connect(self._on_long_cycles)
        v.wait_multiplier_committed.connect(self._on_wait_multiplier)

        # Sweep Timing
        v.delay_committed.connect(self._on_delay)
        v.hold_time_committed.connect(self._on_hold_time)
        v.sweep_stop_changed.connect(self._on_sweep_stop)

        # VAR1
        v.var1_mode_changed.connect(self._on_var1_mode)
        v.var1_spacing_changed.connect(self._on_var1_spacing)
        v.var1_start_committed.connect(self._on_var1_start)
        v.var1_stop_committed.connect(self._on_var1_stop)
        v.var1_step_committed.connect(self._on_var1_step)
        v.var1_comp_committed.connect(self._on_var1_comp)
        v.var1_pcomp_committed.connect(self._on_var1_pcomp)
        v.var1_pcomp_enabled_changed.connect(self._on_var1_pcomp_enabled)

        # VAR2
        v.var2_start_committed.connect(self._on_var2_start)
        v.var2_step_committed.connect(self._on_var2_step)
        v.var2_n_of_steps_changed.connect(self._on_var2_n_of_steps)
        v.var2_comp_committed.connect(self._on_var2_comp)
        v.var2_pcomp_committed.connect(self._on_var2_pcomp)
        v.var2_pcomp_enabled_changed.connect(self._on_var2_pcomp_enabled)

        # VARD
        v.vard_offset_committed.connect(self._on_vard_offset)
        v.vard_ratio_committed.connect(self._on_vard_ratio)
        v.vard_comp_committed.connect(self._on_vard_comp)
        v.vard_pcomp_committed.connect(self._on_vard_pcomp)
        v.vard_pcomp_enabled_changed.connect(self._on_vard_pcomp_enabled)

        # PULSE
        v.pulse_period_committed.connect(self._on_pulse_period)
        v.pulse_width_committed.connect(self._on_pulse_width)
        v.pulse_base_committed.connect(self._on_pulse_base)

        # Channels + vars
        v.smu_standby_changed.connect(self._on_smu_standby)
        v.display_var_toggled.connect(self._on_display_var_toggled)

        # Export / Save
        v.export_requested.connect(self._on_export_requested)
        v.save_requested.connect(self._on_save_requested)
        v.save_message_expired.connect(self._update_validation)

        # Quick apply / run over GPIB
        v.apply_setup_requested.connect(self._on_quick_apply_setup)
        v.apply_run_fetch_requested.connect(self._on_quick_apply_run_fetch)

        # Ranges
        v.range_changed.connect(self._on_range_changed)

        # Constant Sources
        v.const_source_changed.connect(self._on_const_source_changed)
        v.const_compliance_changed.connect(self._on_const_compliance_changed)

    # ── Page activation ────────────────────────────────────────────────

    def _on_page_activated(self) -> None:
        self._rebuild_channel_context()
        self._push_full_state()
        self._update_validation()

    def _rebuild_channel_context(self) -> None:
        """
        Derive the full context from the static ChannelsConfig snapshot:
        which channels are active, their VAR assignments, and sweep units.
        VSU channels assigned to VAR1/VAR2 are flagged with is_vsu=True so
        the view can apply the ±20 V widget bounds instead of ±100 V.
        """
        ch_cfg = self._channels_config
        active: List[dict] = []
        available_vars: List[str] = []

        var1_ch: Optional[str] = None
        var2_ch: Optional[str] = None
        vard_ch: Optional[str] = None
        var1_is_v: bool = True
        var2_is_v: bool = True
        var1_is_vsu: bool = False
        var2_is_vsu: bool = False
        vard_is_vsu: bool = False
        pulsed_smus: List[Tuple[str, bool]] = []  # (ch_id, is_voltage)

        # ── SMUs ──────────────────────────────────────────────────────
        for idx, smu in ch_cfg.smu.items():
            if not smu.enabled:
                continue
            ch_id = f"SMU{idx}"
            fn = smu.function.value  # "CONST", "VAR1", "VAR2", "VAR1'"
            is_v = _is_voltage_mode(smu.mode.value)

            if ch_id not in self._config.channel_standby:
                self._config.channel_standby[ch_id] = False

            active.append(
                {
                    "id": ch_id,
                    "unit_type": "SMU",
                    "function": fn,
                    "mode": smu.mode.value,
                    "v_name": smu.voltage_name,
                    "i_name": smu.current_name,
                    "standby": self._config.channel_standby.get(ch_id, False),
                }
            )
            available_vars.extend([smu.voltage_name, smu.current_name])

            if fn == "VAR1":
                var1_ch, var1_is_v, var1_is_vsu = ch_id, is_v, False
            elif fn == "VAR2":
                var2_ch, var2_is_v, var2_is_vsu = ch_id, is_v, False
            elif fn == "VAR1'":
                vard_ch, vard_is_vsu = ch_id, False

            if smu.mode.value in ("VPULSE", "IPULSE"):
                pulsed_smus.append((ch_id, is_v))

        # ── VMUs ──────────────────────────────────────────────────────
        for idx, vmu in ch_cfg.vmu.items():
            if not vmu.enabled:
                continue
            # The dvol secondary is auto-coupled by VMU1 and nameless — it has
            # no measured variable and must not appear anywhere.
            if ChannelsConstraints.is_dvol_secondary(ch_cfg, idx):
                continue
            ch_id = f"VMU{idx}"
            active.append(
                {
                    "id": ch_id,
                    "unit_type": "VMU",
                    "function": "MONITOR",
                    "mode": vmu.mode.value,
                    "v_name": vmu.voltage_name,
                    "i_name": "",
                    "standby": False,
                }
            )
            available_vars.append(vmu.voltage_name)

        # ── VSUs ──────────────────────────────────────────────────────
        # VSUs source voltage only (always is_voltage=True, ±20 V range).
        for idx, vsu in ch_cfg.vsu.items():
            if not vsu.enabled:
                continue
            ch_id = f"VSU{idx}"
            fn = vsu.function.value

            active.append(
                {
                    "id": ch_id,
                    "unit_type": "VSU",
                    "function": fn,
                    "mode": "V",
                    "v_name": vsu.voltage_name,
                    "i_name": "",
                    "standby": False,
                }
            )
            available_vars.append(vsu.voltage_name)

            if fn == "VAR1":
                var1_ch, var1_is_v, var1_is_vsu = ch_id, True, True
            elif fn == "VAR2":
                var2_ch, var2_is_v, var2_is_vsu = ch_id, True, True
            elif fn == "VAR1'":
                # VARD from a VSU has no compliance / power compliance
                vard_ch, vard_is_vsu = ch_id, True

        # Filter display_vars to only keep currently available variables
        self._config.display_vars = [
            v for v in self._config.display_vars if v in available_vars
        ]

        # Initialise display_vars from all available variables on first use
        if not self._config.display_vars and available_vars:
            unique_vars = list(dict.fromkeys(available_vars))
            self._config.display_vars = unique_vars[:DISPLAY_VARS_MAX]

        # Prune ranges for disabled/inactive measurement units (SMUs and VMUs)
        # and initialize defaults for new active units (current-measuring
        # units → limited-auto at 1 nA; voltage-measuring units → AUTO).
        active_meas_units = {
            ch["id"]: ch for ch in active if ch["unit_type"] in ("SMU", "VMU")
        }
        updated_ranges = {}
        for uid, ch in active_meas_units.items():
            if uid in self._config.measurement_setup.ranges:
                updated_ranges[uid] = self._config.measurement_setup.ranges[
                    uid
                ]
            else:
                updated_ranges[uid] = default_range_config(ch)
        self._config.measurement_setup.ranges = updated_ranges

        # Prune/initialize constant entries to match
        # currently active CONST units (excluding COMM SMUs).
        # Initialize default values based on unit type
        # and source mode:
        # SMU Voltage source: source = 0.0 V, compliance = 0.01 A.
        # SMU Current source: source = 0.0 A, compliance = 2.0 V.
        # VSU: source = 0.0 V.
        active_const_units = {
            ch["id"]: ch
            for ch in active
            if ch.get("function") == "CONST"
            and ch.get("unit_type") in ("SMU", "VSU")
            and ch.get("mode") != "COMM"
        }
        updated_constants = {}
        for uid, ch in active_const_units.items():
            if uid in self._config.constants:
                updated_constants[uid] = self._config.constants[uid]
            elif ch["unit_type"] == "VSU":
                updated_constants[uid] = {"source": 0.0}
            elif ch["unit_type"] == "SMU":
                if ch["mode"] in ("V", "VPULSE"):
                    updated_constants[uid] = {
                        "source": 0.0,
                        "compliance": 0.01,
                    }
                elif ch["mode"] in ("I", "IPULSE"):
                    updated_constants[uid] = {"source": 0.0, "compliance": 2.0}
        self._config.constants = updated_constants

        self._ctx = {
            "instrument_model": ch_cfg.instrument_model.value,
            "has_var1": var1_ch is not None,
            "has_var2": var2_ch is not None,
            "has_vard": vard_ch is not None,
            "var1_channel": var1_ch,
            "var2_channel": var2_ch,
            "vard_channel": vard_ch,
            "var1_is_voltage": var1_is_v,
            "var2_is_voltage": var2_is_v,
            "var1_is_vsu": var1_is_vsu,
            "var2_is_vsu": var2_is_vsu,
            "vard_is_vsu": vard_is_vsu,
            # Only one SMU can be a pulse source (Channels page enforces
            # this); guard defensively against a multi-pulse snapshot.
            "has_pulse": len(pulsed_smus) == 1,
            "pulse_channel": (
                pulsed_smus[0][0] if len(pulsed_smus) == 1 else None
            ),
            "pulse_is_voltage": (
                pulsed_smus[0][1] if len(pulsed_smus) == 1 else True
            ),
            "interlock_open": bool(ch_cfg.interlock_open),
            "active_channels": active,
            "available_vars": list(dict.fromkeys(available_vars)),
        }

    def _push_full_state(self) -> None:
        ctx = self._ctx
        cfg = self._config

        self._view.display_channel_summary(
            ctx["active_channels"],
            instrument_model=self._channels_config.instrument_model.value,
            common_to_ground=bool(self._channels_config.common_to_ground),
            interlock_open=bool(self._channels_config.interlock_open),
        )
        self._view.display_ranges_setup(
            ctx["active_channels"],
            ctx["instrument_model"],
            cfg.measurement_setup.ranges,
        )

        self._view.display_var_sections(
            ctx["has_var1"], ctx["has_var2"], ctx["has_vard"]
        )

        interlock_open = ctx["interlock_open"]
        pulse_ch_id = ctx["pulse_channel"]
        if ctx["has_var1"] and ctx["var1_channel"]:
            self._view.display_var1_context(
                ctx["var1_channel"],
                is_voltage=ctx["var1_is_voltage"],
                is_vsu=ctx["var1_is_vsu"],
                interlock_open=interlock_open,
                is_pulsed=ctx["var1_channel"] == pulse_ch_id,
            )

        if ctx["has_var2"] and ctx["var2_channel"]:
            self._view.display_var2_context(
                ctx["var2_channel"],
                is_voltage=ctx["var2_is_voltage"],
                is_vsu=ctx["var2_is_vsu"],
                interlock_open=interlock_open,
            )

        if ctx["has_vard"] and ctx["vard_channel"]:
            # VARD follows VAR1's voltage/current type
            self._view.display_vard_context(
                ctx["vard_channel"],
                is_voltage=ctx["var1_is_voltage"],
                is_vsu=ctx["vard_is_vsu"],
                interlock_open=interlock_open,
                is_pulsed=ctx["vard_channel"] == pulse_ch_id,
            )

        self._view.display_pulse_section(ctx["has_pulse"])
        self._view.display_delay_visible(not ctx["has_pulse"])
        if ctx["has_pulse"] and ctx["pulse_channel"]:
            self._view.display_pulse_context(
                ctx["pulse_channel"],
                is_voltage=ctx["pulse_is_voltage"],
                interlock_open=interlock_open,
            )

        self._view.display_config(self._config_snapshot())
        self._view.display_constants_setup(
            ctx["active_channels"],
            cfg.constants,
            interlock_open=interlock_open,
        )
        self._view.display_available_vars(
            ctx["available_vars"], cfg.display_vars
        )
        self._update_validation()

    # ── Signal handlers ──────────────────────────────────────────────────────
    def _on_range_changed(
        self, unit_id: str, mode: str, value: Optional[float]
    ) -> None:
        r_entry = {"mode": mode}
        if mode in ("FIX", "LIM") and value is not None:
            r_entry["value"] = value
        self._config.measurement_setup.ranges[unit_id] = r_entry
        self._update_validation()

    def _on_integration_mode(self, val: str) -> None:
        try:
            self._config.measurement_setup.integration_mode = IntegrationMode(
                val
            )
        except ValueError:
            pass
        self._update_validation()

    def _on_short_time(self, val: float) -> None:
        self._config.measurement_setup.short_time = val
        self._update_validation()

    def _on_long_cycles(self, val: int) -> None:
        self._config.measurement_setup.long_time_cycles = val
        self._update_validation()

    def _on_wait_multiplier(self, val: float) -> None:
        self._config.measurement_setup.wait_multiplier = val
        self._update_validation()

    def _on_delay(self, val: float) -> None:
        self._config.delay = val
        self._update_validation()

    def _on_hold_time(self, val: float) -> None:
        self._config.hold_time = val
        self._update_validation()

    def _on_sweep_stop(self, val: str) -> None:
        try:
            self._config.sweep_stop = SweepStop(val)
        except ValueError:
            pass
        self._update_validation()

    def _on_var1_mode(self, val: str) -> None:
        try:
            self._config.var1.mode = VAR1Mode(val)
        except ValueError:
            pass
        self._update_validation()

    def _on_var1_spacing(self, val: str) -> None:
        try:
            self._config.var1.spacing = SweepSpacing(val)
        except ValueError:
            pass
        self._update_validation()

    def _on_var1_start(self, val: float) -> None:
        self._config.var1.start = val
        self._update_validation()

    def _on_var1_stop(self, val: float) -> None:
        self._config.var1.stop = val
        self._update_validation()

    def _on_var1_step(self, val: float) -> None:
        self._config.var1.step = val
        self._update_validation()

    def _on_var1_comp(self, val: float) -> None:
        self._config.var1.compliance = val
        self._update_validation()

    def _on_var1_pcomp(self, val: float) -> None:
        self._config.var1.power_compliance = val
        self._update_validation()

    def _on_var1_pcomp_enabled(self, enabled: bool) -> None:
        self._config.var1.power_compliance_enabled = enabled
        self._update_validation()

    def _on_var2_start(self, val: float) -> None:
        self._config.var2.start = val
        self._update_validation()

    def _on_var2_step(self, val: float) -> None:
        self._config.var2.step = val
        self._update_validation()

    def _on_var2_n_of_steps(self, val: int) -> None:
        self._config.var2.n_of_steps = val
        self._update_validation()

    def _on_var2_comp(self, val: float) -> None:
        self._config.var2.compliance = val
        self._update_validation()

    def _on_var2_pcomp(self, val: float) -> None:
        self._config.var2.power_compliance = val
        self._update_validation()

    def _on_var2_pcomp_enabled(self, enabled: bool) -> None:
        self._config.var2.power_compliance_enabled = enabled
        self._update_validation()

    def _on_vard_offset(self, val: float) -> None:
        self._config.vard.offset = val
        self._update_validation()

    def _on_vard_ratio(self, val: float) -> None:
        self._config.vard.ratio = val
        self._update_validation()

    def _on_vard_comp(self, val: float) -> None:
        self._config.vard.compliance = val
        self._update_validation()

    def _on_vard_pcomp(self, val: float) -> None:
        self._config.vard.power_compliance = val
        self._update_validation()

    def _on_vard_pcomp_enabled(self, enabled: bool) -> None:
        self._config.vard.power_compliance_enabled = enabled
        self._update_validation()

    def _on_pulse_period(self, val: float) -> None:
        self._config.pulse.period = val
        self._update_validation()

    def _on_pulse_width(self, val: float) -> None:
        self._config.pulse.width = val
        self._update_validation()

    def _on_pulse_base(self, val: float) -> None:
        self._config.pulse.base = val
        self._update_validation()

    def _on_smu_standby(self, ch_id: str, on: bool) -> None:
        self._config.channel_standby[ch_id] = on
        self._update_validation()

    def _on_const_source_changed(self, unit_id: str, val: float) -> None:
        if unit_id in self._config.constants:
            self._config.constants[unit_id]["source"] = val
            self._update_validation()

    def _on_const_compliance_changed(self, unit_id: str, val: float) -> None:
        if unit_id in self._config.constants:
            self._config.constants[unit_id]["compliance"] = val
            self._update_validation()

    def _on_display_var_toggled(self, var_name: str, selected: bool) -> None:
        if selected and var_name not in self._config.display_vars:
            self._config.display_vars.append(var_name)
        elif not selected and var_name in self._config.display_vars:
            self._config.display_vars.remove(var_name)
        self._update_validation()

    def _on_export_requested(self) -> None:
        errors, _warnings = self._run_validation()
        if not errors:
            result = self._build_json()
            self._view.display_json(json.dumps(result, indent=4))

    def _on_save_requested(self, path: str) -> None:
        errors, _warnings = self._run_validation()
        if errors:
            return
        result = self._build_json()
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(result, fp, indent=4)
        self._view.display_save_success(Path(path).name)

    # ── Quick apply / run (ephemeral GPIB) ─────────────────────────────

    def _connect_connector_signals(self) -> None:
        if self._connector is None:
            return
        self._connector.connection_changed.connect(
            self._on_hw_connection_changed
        )
        self._connector.hardware_busy.connect(self._on_hw_busy)

    def _on_hw_connection_changed(self, connected: bool, _name: str) -> None:
        self._connected = connected
        self._push_hardware_state()

    def _on_hw_busy(self, busy: bool) -> None:
        self._busy = busy
        self._push_hardware_state()

    def _push_hardware_state(self) -> None:
        self._view.display_hardware_state(self._connected, self._busy)

    def _confirm_instrument_match(self) -> bool:
        """Warn (once per session) before a quick apply/run on a foreign
        instrument model."""
        connected = (
            self._connector.connected_instrument_model()
            if self._connector is not None
            else None
        )
        return confirm_quick_instrument_match(
            self._view, self.get_instrument_model(), connected
        )

    def _on_quick_apply_setup(self) -> None:
        if self._runner is None:
            return
        try:
            config = self.get_json()
        except ValueError:
            return  # menu is gated on validity; ignore defensively
        if not self._confirm_instrument_match():
            return
        self._runner.apply_setup(config)

    def _on_quick_apply_run_fetch(self) -> None:
        if self._runner is None:
            return
        try:
            config = self.get_json()
        except ValueError:
            return
        if not self._confirm_instrument_match():
            return
        self._runner.apply_run_fetch(config)

    # ── Validation (model driven) ──────────────────────────────────────

    def _run_validation(self) -> Tuple[Dict[str, str], List[str]]:
        """
        Query input-level validation errors from the view, and combine them
        with the model's validation constraints.  Returns ``(errors,
        warnings)``; warnings are informational and never block.
        """
        errors = self._view.get_input_errors()

        model_errors, warnings = SweepConstraints.validate_config(
            cfg=self._config,
            flags=SweepUnitFlags(
                has_var1=self._ctx.get("has_var1", False),
                has_var2=self._ctx.get("has_var2", False),
                has_vard=self._ctx.get("has_vard", False),
                var1_is_voltage=self._ctx.get(
                    "var1_is_voltage",
                    True,
                ),
                var1_is_vsu=self._ctx.get("var1_is_vsu", False),
                var2_is_voltage=self._ctx.get(
                    "var2_is_voltage",
                    True,
                ),
                var2_is_vsu=self._ctx.get("var2_is_vsu", False),
                vard_is_vsu=self._ctx.get("vard_is_vsu", False),
            ),
            active_channels=self._ctx.get("active_channels"),
            interlock_open=self._ctx.get("interlock_open", False),
            instrument_model=self._ctx.get("instrument_model", "4155C"),
        )

        for i, err in enumerate(model_errors):
            errors[f"model_err_{i}"] = err

        return errors, warnings

    def _update_validation(self) -> None:
        errors, warnings = self._run_validation()
        criticals = list(errors.values())
        stats = sweep_measurement_stats(
            self._config,
            self._ctx["active_channels"],
            self._ctx["instrument_model"],
            self._line_frequency_hz,
        )
        indexes, points, exec_time = measurement_stat_values(stats)
        self._view.display_measurement_status(
            criticals, warnings, indexes, points, exec_time
        )

    # ── JSON builder ───────────────────────────────────────────────────

    def _build_json(self) -> dict:
        """
        Merge channel context (static ChannelsConfig snapshot) with
        SweepConfig.

        JSON conventions:
          "VAR1'"   function key → "VARD"
          power_compliance field → "pcompliance"
          wait_multiplier field  → "wait_time"  (backward-compat with spec)
          Disabled channels      → {"disable": 1}
          VSU-driven VARx omit "compliance"/"pcompliance" (VSUs cannot
          measure current); "pcompliance" is omitted when switched off.
        """
        cfg = self._config
        ch_cfg = self._channels_config
        channels_json: Dict[str, Any] = {}

        for idx in range(1, 5):
            ch_id = f"SMU{idx}"
            smu = ch_cfg.smu.get(idx)
            if smu and smu.enabled:
                channels_json[ch_id] = {
                    "v_name": smu.voltage_name,
                    "i_name": smu.current_name,
                    "function": _fn_to_json_key(smu.function.value),
                    "smu_mode": smu.mode.value,
                    "standby": "ON"
                    if cfg.channel_standby.get(ch_id)
                    else "OFF",
                }
            else:
                channels_json[ch_id] = {"disable": 1}

        for idx in range(1, 3):
            ch_id = f"VMU{idx}"
            vmu = ch_cfg.vmu.get(idx)
            # The dvol secondary is auto-coupled by VMU1's DVOLT command —
            # omit it entirely (no key) rather than disabling it.
            if vmu and ChannelsConstraints.is_dvol_secondary(ch_cfg, idx):
                continue
            if vmu and vmu.enabled:
                channels_json[ch_id] = {
                    "v_name": vmu.voltage_name,
                    "vmu_mode": VMU_MODE_SCPI_MAP[vmu.mode],
                }
            else:
                channels_json[ch_id] = {"disable": 1}

        for idx in range(1, 3):
            ch_id = f"VSU{idx}"
            vsu = ch_cfg.vsu.get(idx)
            if vsu and vsu.enabled:
                channels_json[ch_id] = {
                    "v_name": vsu.voltage_name,
                    "function": _fn_to_json_key(vsu.function.value),
                }
            else:
                channels_json[ch_id] = {"disable": 1}

        ms = cfg.measurement_setup
        meas_json: Dict[str, Any] = {
            "integration_mode": ms.integration_mode.value,
        }
        # short_time / long_time_cycles only apply to their own mode;
        # MED carries neither.
        if ms.integration_mode == IntegrationMode.SHORT:
            meas_json["short_time"] = ms.short_time
        elif ms.integration_mode == IntegrationMode.LONG:
            meas_json["long_time_cycles"] = ms.long_time_cycles
        meas_json["wait_time"] = ms.wait_multiplier  # JSON key kept
        meas_json["ranges"] = ms.ranges

        sweep_json: Dict[str, Any] = {}
        has_pulse = self._ctx.get("has_pulse", False)
        pulse_ch_id = self._ctx.get("pulse_channel")
        # The instrument ignores the delay during a pulse sweep (each step
        # is paced by the pulse period) — omit the key entirely.
        if not has_pulse:
            sweep_json["delay"] = cfg.delay
        sweep_json["hold_time"] = cfg.hold_time
        sweep_json["sweep_stop"] = cfg.sweep_stop.value

        if self._ctx.get("has_var1"):
            v1 = cfg.var1
            sweep_json["var1"] = {
                "mode": v1.mode.value,
                "spacing": v1.spacing.value,
                "start": v1.start,
                "stop": v1.stop,
            }
            # "step" only applies to LINEAR spacing; logarithmic
            # spacings (L10/L25/L50) derive their points from the decade.
            if v1.spacing == SweepSpacing.LINEAR:
                sweep_json["var1"]["step"] = v1.step
            if not self._ctx.get("var1_is_vsu"):
                sweep_json["var1"]["compliance"] = v1.compliance
                # A pulsed VAR1 unit has no power compliance.
                if v1.power_compliance_enabled and not (
                    self._ctx.get("var1_channel") == pulse_ch_id
                ):
                    sweep_json["var1"]["pcompliance"] = v1.power_compliance

        if self._ctx.get("has_var2"):
            v2 = cfg.var2
            sweep_json["var2"] = {
                "start": v2.start,
                "step": v2.step,
                "n_of_steps": v2.n_of_steps,
            }
            if not self._ctx.get("var2_is_vsu"):
                sweep_json["var2"]["compliance"] = v2.compliance
                if v2.power_compliance_enabled:
                    sweep_json["var2"]["pcompliance"] = v2.power_compliance

        if self._ctx.get("has_vard"):
            vd = cfg.vard
            sweep_json["vard"] = {
                "offset": vd.offset,
                "ratio": vd.ratio,
            }
            if not self._ctx.get("vard_is_vsu"):
                sweep_json["vard"]["compliance"] = vd.compliance
                # A pulsed VARD unit has no power compliance.
                if vd.power_compliance_enabled and not (
                    self._ctx.get("vard_channel") == pulse_ch_id
                ):
                    sweep_json["vard"]["pcompliance"] = vd.power_compliance

        if has_pulse:
            sweep_json["pulse"] = {
                "period": cfg.pulse.period,
                "width": cfg.pulse.width,
                "base": cfg.pulse.base,
            }

        if cfg.constants:
            sweep_json["constants"] = copy.deepcopy(cfg.constants)

        return {
            "mode": "SWEEP",
            "channels": channels_json,
            "measurement_setup": meas_json,
            "sweep_setup": sweep_json,
            "display_vars": list(cfg.display_vars),
        }

    # ── Config snapshot (for display_config) ──────────────────────────

    def _config_snapshot(self) -> dict:
        cfg = self._config
        ms = cfg.measurement_setup
        return {
            "measurement_setup": {
                "integration_mode": ms.integration_mode.value,
                "short_time": ms.short_time,
                "long_time_cycles": ms.long_time_cycles,
                "wait_multiplier": ms.wait_multiplier,
                "ranges": copy.deepcopy(ms.ranges),
            },
            "delay": cfg.delay,
            "hold_time": cfg.hold_time,
            "sweep_stop": cfg.sweep_stop.value,
            "var1": {
                "mode": cfg.var1.mode.value,
                "spacing": cfg.var1.spacing.value,
                "start": cfg.var1.start,
                "stop": cfg.var1.stop,
                "step": cfg.var1.step,
                "compliance": cfg.var1.compliance,
                "power_compliance": cfg.var1.power_compliance,
                "power_compliance_enabled": cfg.var1.power_compliance_enabled,
            },
            "var2": {
                "start": cfg.var2.start,
                "step": cfg.var2.step,
                "n_of_steps": cfg.var2.n_of_steps,
                "compliance": cfg.var2.compliance,
                "power_compliance": cfg.var2.power_compliance,
                "power_compliance_enabled": cfg.var2.power_compliance_enabled,
            },
            "vard": {
                "offset": cfg.vard.offset,
                "ratio": cfg.vard.ratio,
                "compliance": cfg.vard.compliance,
                "power_compliance": cfg.vard.power_compliance,
                "power_compliance_enabled": cfg.vard.power_compliance_enabled,
            },
            "pulse": {
                "period": cfg.pulse.period,
                "width": cfg.pulse.width,
                "base": cfg.pulse.base,
            },
            "constants": copy.deepcopy(cfg.constants),
        }
