"""
presenters/qscv_config_presenter.py
-----------------------------------
Presenter for the QSCV (Quasi-static C-V) Configuration page.

Mirrors SweepConfigPresenter: it mediates between QscvConfigPageView (View)
and QscvConfig (Model), deriving its context from a STATIC deep-copied
ChannelsConfig snapshot.  The QSCV integration-time limits depend on the AC
line frequency, so the line frequency (a global setting) is passed in at
construction time by the factory.

Public API consumed by other presenters / the factory
------------------------------------------------------
get_config()           → QscvConfig (deep copy)
get_instrument_model() → str
get_json()             → dict  (raises ValueError if validation fails)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject

from wizard_4155_4156.models.config_loader import qscv_config_from_setup
from wizard_4155_4156.models.qscv_config import (
    QscvConfig,
    QscvConstraints,
    SweepStop,
    VAR1Mode,
    ranges_for_model,
)
from wizard_4155_4156.models.sweep_config import DISPLAY_VARS_MAX
from wizard_4155_4156.views.pages.qscv_config_page import QscvConfigPageView

# ── Helpers ─────────────────────────────────────────────────────────────


def _fn_to_json_key(fn_value: str) -> str:
    """Map UnitFunction SCPI values to JSON-layer keys (mirrors sweep)."""
    if fn_value == "VAR1'":
        return "VARD"
    if fn_value == "CONST":
        return "CONS"
    return fn_value


class QscvConfigPresenter(QObject):
    """Mediates between QscvConfigPageView (View) and QscvConfig (Model)."""

    def __init__(
        self,
        view: QscvConfigPageView,
        channels_snapshot,  # ChannelsConfig — static deep-copied snapshot
        line_frequency_hz: int = 50,
        parent: QObject | None = None,
        initial_setup: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._channels_config = channels_snapshot
        self._line_frequency_hz = line_frequency_hz or 50
        self._config = (
            qscv_config_from_setup(initial_setup)
            if initial_setup is not None
            else QscvConfig()
        )

        self._ctx: Dict[str, Any] = {
            "instrument_model": "4156C",
            "interlock_open": False,
            "var1_channel": None,
            "enabled_smu_ids": [],
            "active_channels": [],
            "channel_vars": [],
        }

        self._connect_view_signals()
        self._on_page_activated()

    # ── Public API ─────────────────────────────────────────────────────

    def get_config(self) -> QscvConfig:
        return copy.deepcopy(self._config)

    def get_instrument_model(self) -> str:
        return self._channels_config.instrument_model.value

    def get_json(self) -> dict:
        errors = self._run_validation()
        if errors:
            raise ValueError(
                "QSCV config invalid:\n" + "\n".join(errors.values())
            )
        return self._build_json()

    # ── Signal wiring ────────────────────────────────────────────────────────

    def _connect_view_signals(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)

        v.unit_changed.connect(self._on_unit)
        v.range_changed.connect(self._on_range)
        v.cap_int_committed.connect(self._on_cap_int)
        v.leak_int_committed.connect(self._on_leak_int)
        v.cap_name_changed.connect(self._on_cap_name)
        v.leak_name_changed.connect(self._on_leak_name)
        v.leak_comp_changed.connect(self._on_leak_comp)
        v.zero_cancel_changed.connect(self._on_zero_cancel)

        v.delay_committed.connect(self._on_delay)
        v.hold_time_committed.connect(self._on_hold_time)
        v.sweep_stop_changed.connect(self._on_sweep_stop)

        v.var1_mode_changed.connect(self._on_var1_mode)
        v.var1_start_committed.connect(self._on_var1_start)
        v.var1_stop_committed.connect(self._on_var1_stop)
        v.var1_step_committed.connect(self._on_var1_step)
        v.var1_cstep_committed.connect(self._on_var1_cstep)
        v.var1_comp_committed.connect(self._on_var1_comp)

        v.smu_standby_changed.connect(self._on_smu_standby)
        v.display_var_toggled.connect(self._on_display_var_toggled)

        v.export_requested.connect(self._on_export_requested)
        v.save_requested.connect(self._on_save_requested)
        v.save_message_expired.connect(self._update_validation)

        v.const_source_changed.connect(self._on_const_source_changed)
        v.const_compliance_changed.connect(self._on_const_compliance_changed)

    # ── Page activation ─────────────────────────────────────────────────────

    def _on_page_activated(self) -> None:
        self._rebuild_channel_context()
        self._push_full_state()

    def _rebuild_channel_context(self) -> None:
        ch_cfg = self._channels_config
        active: List[dict] = []
        channel_vars: List[str] = []
        enabled_smu_ids: List[str] = []
        var1_ch: Optional[str] = None

        # ── SMUs ──────────────────────────────────────────────────────
        for idx, smu in ch_cfg.smu.items():
            if not smu.enabled:
                continue
            ch_id = f"SMU{idx}"
            fn = smu.function.value
            enabled_smu_ids.append(ch_id)
            if ch_id not in self._config.channel_standby:
                self._config.channel_standby[ch_id] = False
            active.append({
                "id": ch_id,
                "unit_type": "SMU",
                "function": fn,
                "mode": smu.mode.value,
                "v_name": smu.voltage_name,
                "i_name": smu.current_name,
                "standby": self._config.channel_standby.get(ch_id, False),
            })
            channel_vars.extend([smu.voltage_name, smu.current_name])
            if fn == "VAR1":
                var1_ch = ch_id

        # ── VSUs (CONST only in QSCV) ────────────────────────────────
        for idx, vsu in ch_cfg.vsu.items():
            if not vsu.enabled:
                continue
            ch_id = f"VSU{idx}"
            active.append({
                "id": ch_id,
                "unit_type": "VSU",
                "function": vsu.function.value,
                "mode": "V",
                "v_name": vsu.voltage_name,
                "i_name": "",
                "standby": False,
            })
            channel_vars.append(vsu.voltage_name)

        # VMUs are disabled in QSCV hardware — intentionally omitted.

        instrument_model = ch_cfg.instrument_model.value

        # Clamp the measurement range to one allowed for this instrument.
        allowed_values = [v for _, v, _ in ranges_for_model(instrument_model)]
        if self._config.meas_range not in allowed_values and allowed_values:
            self._config.meas_range = allowed_values[0]

        # Clamp the measuring unit if it no longer references an enabled SMU.
        if (
            self._config.measuring_unit != "DEFAULT"
            and self._config.measuring_unit not in enabled_smu_ids
        ):
            self._config.measuring_unit = "DEFAULT"

        # Prune/seed constants for active CONST SMU/VSU (excluding COMM SMUs).
        active_const_units = {
            ch["id"]: ch
            for ch in active
            if ch.get("function") == "CONST"
            and ch.get("unit_type") in ("SMU", "VSU")
            and ch.get("mode") != "COMM"
        }
        updated_constants: Dict[str, Dict[str, float]] = {}
        for uid, ch in active_const_units.items():
            if uid in self._config.constants:
                updated_constants[uid] = self._config.constants[uid]
            elif ch["unit_type"] == "VSU":
                updated_constants[uid] = {"source": 0.0}
            elif ch["mode"] in ("V", "VPULSE"):
                updated_constants[uid] = {"source": 0.0, "compliance": 0.01}
            else:  # I / IPULSE
                updated_constants[uid] = {"source": 0.0, "compliance": 2.0}
        self._config.constants = updated_constants

        self._ctx = {
            "instrument_model": instrument_model,
            "interlock_open": bool(ch_cfg.interlock_open),
            "var1_channel": var1_ch,
            "enabled_smu_ids": enabled_smu_ids,
            "active_channels": active,
            "channel_vars": list(dict.fromkeys(channel_vars)),
        }

        # Reconcile display variables with the now-available set.
        available = self._available_vars()
        self._config.display_vars = [
            v for v in self._config.display_vars if v in available
        ]
        if not self._config.display_vars and available:
            self._config.display_vars = available[:DISPLAY_VARS_MAX]

    def _available_vars(self) -> List[str]:
        """Display-variable candidates: channel names + QSCV outputs."""
        names = list(self._ctx.get("channel_vars", []))
        if self._config.cap_name.strip():
            names.append(self._config.cap_name.strip())
        if self._config.leak_name.strip():
            names.append(self._config.leak_name.strip())
        return list(dict.fromkeys(names))

    def _push_full_state(self) -> None:
        ctx = self._ctx
        cfg = self._config
        instrument_model = ctx["instrument_model"]

        self._view.display_channel_summary(ctx["active_channels"])
        self._view.display_measure_setup(
            unit_options=["DEFAULT", *ctx["enabled_smu_ids"]],
            current_unit=cfg.measuring_unit,
            ranges=list(ranges_for_model(instrument_model)),
            current_range=cfg.meas_range,
            cap_bounds=self._cap_bounds(),
            leak_bounds=self._leak_bounds(),
        )
        self._view.display_config(self._config_snapshot())

        var1_label = ctx.get("var1_channel") or "—"
        self._view.display_var1_context(
            var1_label, interlock_open=ctx["interlock_open"]
        )

        self._view.display_constants_setup(
            ctx["active_channels"],
            cfg.constants,
            interlock_open=ctx["interlock_open"],
        )
        self._view.display_available_vars(
            self._available_vars(), cfg.display_vars
        )
        self._update_validation()

    def _cap_bounds(self):
        from wizard_4155_4156.models.qscv_config import cap_integration_bounds

        return cap_integration_bounds(self._line_frequency_hz)

    def _leak_bounds(self):
        from wizard_4155_4156.models.qscv_config import leak_integration_bounds

        return leak_integration_bounds(self._line_frequency_hz)

    def _refresh_available_vars(self) -> None:
        available = self._available_vars()
        self._config.display_vars = [
            v for v in self._config.display_vars if v in available
        ]
        self._view.display_available_vars(available, self._config.display_vars)

    def _rename_display_var(self, old: str, new: str) -> None:
        """Preserve a display-var's selected state when its name changes.

        Renaming the capacitance/leakage variable must keep it selected (if it
        was) under the new name, rather than dropping it because the old name
        vanished from the available set.
        """
        old = (old or "").strip()
        new = (new or "").strip()
        if not old or old == new:
            return
        dv = self._config.display_vars
        if old not in dv:
            return
        idx = dv.index(old)
        if new and new not in dv:
            dv[idx] = new  # rename in place — keep position & selected state
        else:
            dv.pop(idx)  # cleared name or duplicate → drop

    # ── Signal handlers ──────────────────────────────────────────────────────

    def _on_unit(self, val: str) -> None:
        self._config.measuring_unit = val or "DEFAULT"
        self._update_validation()

    def _on_range(self, val: float) -> None:
        self._config.meas_range = val
        self._update_validation()

    def _on_cap_int(self, val: float) -> None:
        self._config.cap_integration_time = val
        self._update_validation()

    def _on_leak_int(self, val: float) -> None:
        self._config.leak_integration_time = val
        self._update_validation()

    def _on_cap_name(self, val: str) -> None:
        self._rename_display_var(self._config.cap_name, val)
        self._config.cap_name = val
        self._refresh_available_vars()
        self._update_validation()

    def _on_leak_name(self, val: str) -> None:
        self._rename_display_var(self._config.leak_name, val)
        self._config.leak_name = val
        self._refresh_available_vars()
        self._update_validation()

    def _on_leak_comp(self, enabled: bool) -> None:
        self._config.leak_compensation = enabled
        self._refresh_available_vars()
        self._update_validation()

    def _on_zero_cancel(self, enabled: bool) -> None:
        self._config.zero_cancel = enabled
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

    def _on_var1_start(self, val: float) -> None:
        self._config.var1.start = val
        self._update_validation()

    def _on_var1_stop(self, val: float) -> None:
        self._config.var1.stop = val
        self._update_validation()

    def _on_var1_step(self, val: float) -> None:
        self._config.var1.step = val
        self._update_validation()

    def _on_var1_cstep(self, val: float) -> None:
        self._config.var1.cstep = val
        self._update_validation()

    def _on_var1_comp(self, val: float) -> None:
        self._config.var1.compliance = val
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
        if not self._run_validation():
            self._view.display_json(json.dumps(self._build_json(), indent=4))

    def _on_save_requested(self, path: str) -> None:
        if self._run_validation():
            return
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(self._build_json(), fp, indent=4)
        self._view.display_save_success(Path(path).name)

    # ── Validation ─────────────────────────────────────────────────────

    def _run_validation(self) -> Dict[str, str]:
        errors = self._view.get_input_errors()
        model_errors = QscvConstraints.validate_config(
            self._config,
            active_channels=self._ctx.get("active_channels"),
            instrument_model=self._ctx.get("instrument_model", "4156C"),
            line_frequency_hz=self._line_frequency_hz,
            enabled_smu_ids=self._ctx.get("enabled_smu_ids"),
            interlock_open=self._ctx.get("interlock_open", False),
        )
        for i, err in enumerate(model_errors):
            errors[f"model_err_{i}"] = err
        return errors

    def _update_validation(self) -> None:
        errors = self._run_validation()
        if not errors:
            msg = "Configuration is valid"
            v1 = self._config.var1
            count = QscvConstraints.no_of_step(v1.start, v1.stop, v1.step)
            if count is not None:
                msg += f" ({count} steps)"
            self._view.display_validation_status(True, msg)
        else:
            first_err = list(errors.values())[0]
            if len(errors) > 1:
                first_err += f" +{len(errors) - 1}"
            self._view.display_validation_status(False, first_err)

    # ── JSON builder ───────────────────────────────────────────────────

    def _build_json(self) -> dict:
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

        # VMUs cannot run in QSCV — always disabled.
        for idx in range(1, 3):
            channels_json[f"VMU{idx}"] = {"disable": 1}

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

        qscv: Dict[str, Any] = {
            "cap_integration_time": cfg.cap_integration_time,
            "leak_integration_time": cfg.leak_integration_time,
            "delay": cfg.delay,
            "hold_time": cfg.hold_time,
            "cap_name": cfg.cap_name,
            "range": cfg.meas_range,
            "sweep_stop": cfg.sweep_stop.value,
            "unit": cfg.measuring_unit,
            "leak_cancel": cfg.leak_compensation,
            "zero_cancel": cfg.zero_cancel,
            "var1": {
                "mode": cfg.var1.mode.value,
                "start": cfg.var1.start,
                "stop": cfg.var1.stop,
                "step": cfg.var1.step,
                "cstep": cfg.var1.cstep,
                "compliance": cfg.var1.compliance,
            },
        }
        if cfg.leak_name.strip():
            qscv["leak_name"] = cfg.leak_name.strip()
        if cfg.constants:
            qscv["constants"] = copy.deepcopy(cfg.constants)

        return {
            "mode": "QSCV",
            "channels": channels_json,
            "qscv_setup": qscv,
            "display_vars": list(cfg.display_vars),
        }

    # ── Config snapshot (for display_config) ──────────────────────────

    def _config_snapshot(self) -> dict:
        cfg = self._config
        return {
            "measure_setup": {
                "cap_time": cfg.cap_integration_time,
                "leak_time": cfg.leak_integration_time,
                "cname": cfg.cap_name,
                "iname": cfg.leak_name,
                "leak_comp": cfg.leak_compensation,
                "zero_cancel": cfg.zero_cancel,
            },
            "delay": cfg.delay,
            "hold_time": cfg.hold_time,
            "sweep_stop": cfg.sweep_stop.value,
            "var1": {
                "mode": cfg.var1.mode.value,
                "start": cfg.var1.start,
                "stop": cfg.var1.stop,
                "step": cfg.var1.step,
                "cstep": cfg.var1.cstep,
                "compliance": cfg.var1.compliance,
            },
        }
