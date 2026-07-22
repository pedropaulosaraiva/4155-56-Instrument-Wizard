"""
presenters/sampling_config_presenter.py
---------------------------------------
Presenter for the Sampling Configuration page.

Built lazily by MeasureConfigFactory from a STATIC deep-copied
ChannelsConfig snapshot — it never holds a reference to the
ChannelsPresenter, so later edits on the channels page do not leak in.

Responsibilities
----------------
- Derive the channel context (active SMU/VMU/VSU units, measured
  variable names) once at construction.
- Own a SamplingConfig instance and mutate it on view signals.
- Recompute dependent widget bounds whenever mode / interval / points /
  display vars change (the measurement-unit count depends on which
  measured variables are displayed).
- Validate via SamplingConstraints.validate_config, which returns
  (errors, warnings): errors block JSON generation and saving, timing
  warnings are shown in amber but never block.
- Build the JSON dict consumed by MeasurementSetupDirector
  (mode "SAMP" + "sampling_setup").
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
from wizard_4155_4156.models.config_loader import sampling_config_from_setup
from wizard_4155_4156.models.execution_time import (
    measurement_stat_values,
    sampling_measurement_stats,
)
from wizard_4155_4156.models.sampling_config import (
    BUILTIN_DISPLAY_VARS,
    DISPLAY_VARS_MAX,
    EDELAY_MAX_MULTIPLIER,
    IINT_MAX,
    SAMP_HOLD_MAX,
    SAMP_HOLD_RESOLUTION,
    PeriodMode,
    SamplingConfig,
    SamplingConstraints,
    SamplingMode,
    SConEvent,
)
from wizard_4155_4156.models.sweep_config import (
    IntegrationMode,
    default_range_config,
)
from wizard_4155_4156.presenters.live_run_helper import LiveMeasurementRunner
from wizard_4155_4156.views.pages.sampling_config_page import (
    SamplingConfigPageView,
)

# ── Presenter ────────────────────────────────────────────────────────────────


class SamplingConfigPresenter(QObject):
    """
    Mediates between SamplingConfigPageView (View) and SamplingConfig
    (Model).

    Public API for other presenters
    --------------------------------
    get_config()  → SamplingConfig (deep copy)
    get_json()    → dict  (raises ValueError if validation errors exist;
                    non-blocking warnings never raise)
    """

    def __init__(
        self,
        view: SamplingConfigPageView,
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
        self._config = (
            sampling_config_from_setup(initial_setup)
            if initial_setup is not None
            else SamplingConfig()
        )

        self._ctx: Dict[str, Any] = {
            "instrument_model": "4155C",
            "active_channels": [],
            "available_vars": [],
            "measured_vars": [],
        }

        self._build_channel_context()
        self._connect_view_signals()
        self._connect_connector_signals()
        self._push_full_state()
        self._push_hardware_state()

    # ── Public API ─────────────────────────────────────────────────────────

    def get_config(self) -> SamplingConfig:
        return copy.deepcopy(self._config)

    def get_instrument_model(self) -> str:
        """Instrument model defined on the channels page for this config."""
        return self._channels_config.instrument_model.value

    def get_json(self) -> dict:
        """Build and return the JSON dict.  Raises ValueError if invalid.

        Non-blocking timing warnings do NOT prevent JSON generation.
        """
        errors, _warnings = self._run_validation()
        if errors:
            raise ValueError(
                "Sampling config invalid:\n" + "\n".join(errors.values())
            )
        return self._build_json()

    def get_runtime_bounds(self) -> Optional[Tuple[float, float]]:
        """Estimated minimum-runtime interval (seconds), or None when
        indeterminate — persisted alongside a saved setup."""
        return sampling_measurement_stats(
            self._config,
            self._ctx["active_channels"],
            self._ctx["instrument_model"],
            self._line_frequency_hz,
        ).exec_time

    # ── Channel context (derived once from the static snapshot) ────────────

    def _build_channel_context(self) -> None:
        ch_cfg = self._channels_config
        cfg = self._config
        active: List[dict] = []
        available_vars: List[str] = list(BUILTIN_DISPLAY_VARS)

        # SMUs — in SAMPLING all functions are CONST
        for idx, smu in ch_cfg.smu.items():
            if not smu.enabled:
                continue
            ch_id = f"SMU{idx}"
            cfg.channel_standby.setdefault(ch_id, False)
            active.append(
                {
                    "id": ch_id,
                    "unit_type": "SMU",
                    "function": smu.function.value,
                    "mode": smu.mode.value,
                    "v_name": smu.voltage_name,
                    "i_name": smu.current_name,
                    "standby": cfg.channel_standby.get(ch_id, False),
                }
            )
            available_vars.extend([smu.voltage_name, smu.current_name])

        # VMUs — monitor-only, usable in SAMPLING
        for idx, vmu in ch_cfg.vmu.items():
            if not vmu.enabled:
                continue
            # The dvol secondary is auto-coupled by VMU1 and nameless — it has
            # no measured variable and must not appear anywhere.
            if ChannelsConstraints.is_dvol_secondary(ch_cfg, idx):
                continue
            active.append(
                {
                    "id": f"VMU{idx}",
                    "unit_type": "VMU",
                    "function": "MONITOR",
                    "mode": vmu.mode.value,
                    "v_name": vmu.voltage_name,
                    "i_name": "",
                    "standby": False,
                }
            )
            available_vars.append(vmu.voltage_name)

        # VSUs — source only (CONST in SAMPLING)
        for idx, vsu in ch_cfg.vsu.items():
            if not vsu.enabled:
                continue
            active.append(
                {
                    "id": f"VSU{idx}",
                    "unit_type": "VSU",
                    "function": vsu.function.value,
                    "mode": "V",
                    "v_name": vsu.voltage_name,
                    "i_name": "",
                    "standby": False,
                }
            )
            available_vars.append(vsu.voltage_name)

        # Measured variables (stop-condition NAME candidates)
        measured_vars: List[str] = []
        for ch in active:
            measured = SamplingConstraints.measured_variable(ch)
            if measured:
                measured_vars.append(measured)
        measured_vars = list(dict.fromkeys(measured_vars))

        # Default display vars: @TIME first, then measured variables
        unique_vars = list(dict.fromkeys(available_vars))
        if not cfg.display_vars:
            defaults = ["@TIME"] + measured_vars
            cfg.display_vars = list(dict.fromkeys(defaults))[:DISPLAY_VARS_MAX]

        # Default ranges for measurement-capable units (current-measuring
        # units → limited-auto at 1 nA; voltage-measuring units → AUTO).
        for ch in active:
            if ch["unit_type"] in {"SMU", "VMU"}:
                cfg.measurement_setup.ranges.setdefault(
                    ch["id"], default_range_config(ch)
                )

        # Default constants for CONST source units (non-COMM)
        for ch in active:
            if (
                ch.get("function") == "CONST"
                and ch["unit_type"] in {"SMU", "VSU"}
                and ch.get("mode") != "COMM"
            ):
                if ch["id"] in cfg.constants:
                    continue
                if ch["unit_type"] == "VSU":
                    cfg.constants[ch["id"]] = {"source": 0.0}
                elif ch["mode"] in {"V", "VPULSE"}:
                    cfg.constants[ch["id"]] = {
                        "source": 0.0,
                        "compliance": 0.01,
                    }
                else:
                    cfg.constants[ch["id"]] = {
                        "source": 0.0,
                        "compliance": 2.0,
                    }

        # Default stop-condition variable
        if not cfg.stop_condition.name and measured_vars:
            cfg.stop_condition.name = measured_vars[0]

        self._ctx = {
            "instrument_model": ch_cfg.instrument_model.value,
            "active_channels": active,
            "available_vars": unique_vars,
            "measured_vars": measured_vars,
        }

    # ── Signal wiring ──────────────────────────────────────────────────────

    def _connect_view_signals(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)

        # Measurement setup
        v.integration_mode_changed.connect(self._on_integration_mode)
        v.short_time_committed.connect(self._on_short_time)
        v.long_cycles_changed.connect(self._on_long_cycles)
        v.wait_multiplier_committed.connect(self._on_wait_multiplier)
        v.range_changed.connect(self._on_range_changed)
        v.smu_standby_changed.connect(self._on_smu_standby)
        v.display_var_toggled.connect(self._on_display_var_toggled)

        # Sampling parameters
        v.sampling_mode_changed.connect(self._on_sampling_mode)
        v.initial_interval_committed.connect(self._on_initial_interval)
        v.points_changed.connect(self._on_points)
        v.period_mode_changed.connect(self._on_period_mode)
        v.period_committed.connect(self._on_period)
        v.hold_time_committed.connect(self._on_hold_time)
        v.filter_changed.connect(self._on_filter)

        # Stop condition
        v.scon_enabled_changed.connect(self._on_scon_enabled)
        v.scon_name_changed.connect(self._on_scon_name)
        v.scon_event_changed.connect(self._on_scon_event)
        v.scon_threshold_committed.connect(self._on_scon_threshold)
        v.scon_event_count_changed.connect(self._on_scon_event_count)
        v.scon_enable_delay_committed.connect(self._on_scon_enable_delay)

        # Constants / export / save
        v.const_source_changed.connect(self._on_const_source_changed)
        v.const_compliance_changed.connect(self._on_const_compliance_changed)
        v.export_requested.connect(self._on_export_requested)
        v.save_requested.connect(self._on_save_requested)
        v.save_message_expired.connect(self._update_validation)

        # Quick apply / run over GPIB
        v.apply_setup_requested.connect(self._on_quick_apply_setup)
        v.apply_run_fetch_requested.connect(self._on_quick_apply_run_fetch)

    # ── Page activation ────────────────────────────────────────────────────

    def _on_page_activated(self) -> None:
        # Context is static; just re-push state (idempotent).
        self._push_full_state()

    def _push_full_state(self) -> None:
        ctx = self._ctx
        cfg = self._config

        self._view.display_channel_summary(ctx["active_channels"])
        self._view.display_ranges_setup(
            ctx["active_channels"],
            ctx["instrument_model"],
            cfg.measurement_setup.ranges,
        )
        self._view.display_config(self._config_snapshot())
        self._view.display_available_vars(
            ctx["available_vars"], cfg.display_vars
        )
        self._view.display_scon_variables(
            ctx["measured_vars"], cfg.stop_condition.name
        )
        self._view.display_constants_setup(
            ctx["active_channels"],
            cfg.constants,
            interlock_open=bool(self._channels_config.interlock_open),
        )
        self._refresh_dependent_state()
        self._update_validation()

    def _refresh_dependent_state(self) -> None:
        """Push mode/interval/display-var dependent bounds to the view."""
        cfg = self._config
        iint = cfg.initial_interval
        n_units = SamplingConstraints.count_measurement_units(
            self._ctx["active_channels"], cfg.display_vars
        )

        self._view.display_iint_bounds(
            SamplingConstraints.iint_min(cfg.mode), IINT_MAX
        )
        self._view.display_points_bounds(
            SamplingConstraints.points_max(cfg.mode, n_units)
        )

        allowed = SamplingConstraints.allowed_period_modes(cfg.mode, iint)
        if allowed and cfg.period_mode not in allowed:
            cfg.period_mode = allowed[0]
        self._view.display_period_options(
            [p.value for p in allowed], cfg.period_mode.value
        )
        p_lo, p_hi = SamplingConstraints.period_numeric_bounds(
            iint, cfg.points
        )
        self._view.display_period_bounds(p_lo, p_hi)

        self._view.display_hold_bounds(
            SamplingConstraints.hold_time_min(iint), SAMP_HOLD_MAX
        )

        scon_allowed = SamplingConstraints.stop_condition_allowed(iint)
        if not scon_allowed and cfg.stop_condition.enabled:
            cfg.stop_condition.enabled = False
            self._view.display_config(self._config_snapshot())
        self._view.display_scon_allowed(scon_allowed)
        self._view.display_scon_delay_bounds(0.0, iint * EDELAY_MAX_MULTIPLIER)

    # ── Signal handlers ────────────────────────────────────────────────────

    def _on_integration_mode(self, val: str) -> None:
        try:
            self._config.measurement_setup.integration_mode = IntegrationMode(
                val
            )
        except ValueError:
            pass
        self._after_change()

    def _on_short_time(self, val: float) -> None:
        self._config.measurement_setup.short_time = val
        self._after_change()

    def _on_long_cycles(self, val: int) -> None:
        self._config.measurement_setup.long_time_cycles = val
        self._after_change()

    def _on_wait_multiplier(self, val: float) -> None:
        self._config.measurement_setup.wait_multiplier = val
        self._after_change()

    def _on_range_changed(self, unit_id: str, mode: str, value) -> None:
        r_entry: Dict[str, Any] = {"mode": mode}
        if mode in {"FIX", "LIM"} and value is not None:
            r_entry["value"] = value
        self._config.measurement_setup.ranges[unit_id] = r_entry
        self._update_validation()

    def _on_smu_standby(self, ch_id: str, on: bool) -> None:
        self._config.channel_standby[ch_id] = on
        self._update_validation()

    def _on_display_var_toggled(self, var_name: str, selected: bool) -> None:
        if selected and var_name not in self._config.display_vars:
            self._config.display_vars.append(var_name)
        elif not selected and var_name in self._config.display_vars:
            self._config.display_vars.remove(var_name)
        # The measurement-unit count depends on displayed variables.
        self._after_change()

    def _on_sampling_mode(self, val: str) -> None:
        try:
            self._config.mode = SamplingMode(val)
        except ValueError:
            return
        self._after_change()

    def _on_initial_interval(self, val: float) -> None:
        self._config.initial_interval = val
        self._after_change()

    def _on_points(self, val: int) -> None:
        self._config.points = val
        self._after_change()

    def _on_period_mode(self, val: str) -> None:
        try:
            self._config.period_mode = PeriodMode(val)
        except ValueError:
            return
        self._after_change()

    def _on_period(self, val: float) -> None:
        self._config.period = val
        self._update_validation()

    def _on_hold_time(self, val: float) -> None:
        # Round to the documented 100 µs hold-time resolution.
        rounded = round(val / SAMP_HOLD_RESOLUTION) * SAMP_HOLD_RESOLUTION
        self._config.hold_time = round(rounded, 9)
        self._update_validation()

    def _on_filter(self, val: str) -> None:
        self._config.filter_on = val == "ON"
        self._update_validation()

    def _on_scon_enabled(self, on: bool) -> None:
        self._config.stop_condition.enabled = on
        self._update_validation()

    def _on_scon_name(self, name: str) -> None:
        self._config.stop_condition.name = name
        self._update_validation()

    def _on_scon_event(self, val: str) -> None:
        try:
            self._config.stop_condition.event = SConEvent(val)
        except ValueError:
            return
        self._update_validation()

    def _on_scon_threshold(self, val: float) -> None:
        self._config.stop_condition.threshold = val
        self._update_validation()

    def _on_scon_event_count(self, val: int) -> None:
        self._config.stop_condition.event_count = val
        self._update_validation()

    def _on_scon_enable_delay(self, val: float) -> None:
        # Round to the nearest multiple of the initial interval
        # (documented resolution of ENABLE DELAY).
        iint = self._config.initial_interval
        if iint > 0:
            val = round(val / iint) * iint
        self._config.stop_condition.enable_delay = round(val, 9)
        self._update_validation()

    def _on_const_source_changed(self, unit_id: str, val: float) -> None:
        if unit_id in self._config.constants:
            self._config.constants[unit_id]["source"] = val
            self._update_validation()

    def _on_const_compliance_changed(self, unit_id: str, val: float) -> None:
        if unit_id in self._config.constants:
            self._config.constants[unit_id]["compliance"] = val
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

    def _on_quick_apply_setup(self) -> None:
        if self._runner is None:
            return
        try:
            config = self.get_json()
        except ValueError:
            return  # menu is gated on validity; ignore defensively
        self._runner.apply_setup(config)

    def _on_quick_apply_run_fetch(self) -> None:
        if self._runner is None:
            return
        try:
            config = self.get_json()
        except ValueError:
            return
        self._runner.apply_run_fetch(config)

    def _after_change(self) -> None:
        self._refresh_dependent_state()
        self._update_validation()

    # ── Validation ─────────────────────────────────────────────────────────

    def _run_validation(self) -> Tuple[Dict[str, str], List[str]]:
        """
        Combine view input-level errors with the model's (errors,
        warnings).  Warnings are returned separately and never block.
        """
        errors = self._view.get_input_errors()
        model_errors, warnings = SamplingConstraints.validate_config(
            self._config,
            self._ctx["active_channels"],
            self._ctx["measured_vars"],
            interlock_open=bool(self._channels_config.interlock_open),
            instrument_model=self._ctx["instrument_model"],
            line_frequency_hz=self._line_frequency_hz,
        )
        for i, err in enumerate(model_errors):
            errors[f"model_err_{i}"] = err
        return errors, warnings

    def _update_validation(self) -> None:
        errors, warnings = self._run_validation()
        criticals = list(errors.values())
        stats = sampling_measurement_stats(
            self._config,
            self._ctx["active_channels"],
            self._ctx["instrument_model"],
            self._line_frequency_hz,
        )
        indexes, points, exec_time = measurement_stat_values(stats)
        self._view.display_measurement_status(
            criticals, warnings, indexes, points, exec_time
        )

    # ── JSON builder ───────────────────────────────────────────────────────

    def _build_json(self) -> dict:
        """
        Build the dict consumed by MeasurementSetupDirector._setup_sampling.

        Period mapping:
          AUTO     → "period_auto": "ON"           (no "period" key)
          NO_LIMIT → "period": "INFINITY", "period_auto": "OFF"
          NUMERIC  → "period": <float>, "period_auto": "OFF"
          LOG modes → neither key (field not applicable)
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
                    "function": "CONS",
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
                    "function": "CONS",
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
        meas_json["ranges"] = copy.deepcopy(ms.ranges)

        sampling_json: Dict[str, Any] = {
            "mode": cfg.mode.value,
            "hold_time": cfg.hold_time,
            "initial_interval": cfg.initial_interval,
            "points": cfg.points,
            "filter": "ON" if cfg.filter_on else "OFF",
        }

        if not cfg.mode.is_log():
            if cfg.period_mode == PeriodMode.AUTO:
                sampling_json["period_auto"] = "ON"
            elif cfg.period_mode == PeriodMode.NO_LIMIT:
                sampling_json["period"] = "INFINITY"
                sampling_json["period_auto"] = "OFF"
            else:
                sampling_json["period"] = cfg.period
                sampling_json["period_auto"] = "OFF"

        sc = cfg.stop_condition
        if sc.enabled:
            sampling_json["scon"] = {
                "state": "ON",
                "name": sc.name,
                "threshold": sc.threshold,
                "event": sc.event.value,
                "event_count": sc.event_count,
                "enable_delay": sc.enable_delay,
            }
        else:
            sampling_json["scon"] = {"state": "OFF"}

        if cfg.constants:
            sampling_json["constants"] = copy.deepcopy(cfg.constants)

        return {
            "mode": "SAMP",
            "channels": channels_json,
            "measurement_setup": meas_json,
            "sampling_setup": sampling_json,
            "display_vars": list(cfg.display_vars),
        }

    # ── Config snapshot (for display_config) ──────────────────────────────

    def _config_snapshot(self) -> dict:
        cfg = self._config
        ms = cfg.measurement_setup
        sc = cfg.stop_condition
        return {
            "measurement_setup": {
                "integration_mode": ms.integration_mode.value,
                "short_time": ms.short_time,
                "long_time_cycles": ms.long_time_cycles,
                "wait_multiplier": ms.wait_multiplier,
                "ranges": copy.deepcopy(ms.ranges),
            },
            "mode": cfg.mode.value,
            "initial_interval": cfg.initial_interval,
            "points": cfg.points,
            "hold_time": cfg.hold_time,
            "period_mode": cfg.period_mode.value,
            "period": cfg.period,
            "filter_on": cfg.filter_on,
            "stop_condition": {
                "enabled": sc.enabled,
                "name": sc.name,
                "threshold": sc.threshold,
                "event": sc.event.value,
                "event_count": sc.event_count,
                "enable_delay": sc.enable_delay,
            },
            "constants": copy.deepcopy(cfg.constants),
        }
