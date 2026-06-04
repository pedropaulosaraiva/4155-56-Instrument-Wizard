"""
presenters/sweep_config_presenter.py
--------------------------------------
Presenter for the Sweep Configuration page.

Responsibilities
----------------
Channel context
  On every page_activated, calls channels_presenter.get_config() to read
  which channels are enabled, their functions, modes, and variable names.
  Derives has_var1/var2/vard, units (V or A), and the available display-var
  list from this snapshot.  SweepConfig never stores channel data itself —
  it only stores the sweep-specific fields (standby, VAR setup, etc.)

Model ownership
  Holds and mutates a single SweepConfig instance.  Every signal handler
  validates before mutating so the model is always self-consistent.

Validation
  Calls SweepConstraints.validate_all() on export_requested and routes
  individual field errors back to the view's section widgets.

JSON export
  build_json() merges channel context (from ChannelsPresenter) with the
  sweep config model into the exact structure the 4155/56 SCPI layer
  consumes.  "VAR1'" is mapped to "VARD" in the JSON per instrument
  convention.  Power compliance is exported as "pcompliance".

Public API for other presenters
  get_config()     → SweepConfig (deep copy)
  get_json()       → dict  (raises if validation fails)
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject

from wizard_4155_4156.models.channels import SMUMode, UnitFunction
from wizard_4155_4156.models.sweep_config import (
    IntegrationMode,
    SweepConfig,
    SweepConstraints,
    SweepSpacing,
    SweepStop,
    VAR1Mode,
)
from wizard_4155_4156.views.pages.sweep_config_page import SweepConfigPageView


# ── Channel context helper ─────────────────────────────────────────────────────


def _is_voltage_mode(mode_value: str) -> bool:
    """V and VPULSE sweep voltage; I and IPULSE sweep current."""
    return mode_value in ("V", "VPULSE")


def _fn_to_json_key(fn_value: str) -> str:
    """Map UnitFunction SCPI values to JSON-layer keys."""
    return "VARD" if fn_value == "VAR1'" else fn_value


# ── Presenter ─────────────────────────────────────────────────────────────────


class SweepConfigPresenter(QObject):
    """
    Mediates between SweepConfigPageView (View) and SweepConfig (Model).
    Requires a reference to ChannelsPresenter so it can call get_config()
    on each activation without holding a stale snapshot.
    """

    def __init__(
        self,
        view: SweepConfigPageView,
        channels_presenter,  # ChannelsPresenter — typed loosely to avoid circular
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._channels_presenter = channels_presenter
        self._config = SweepConfig()

        # Computed on every page_activated; empty until first activation
        self._ctx: Dict[str, Any] = {
            "has_var1": False,
            "has_var2": False,
            "has_vard": False,
            "var1_channel": None,
            "var2_channel": None,
            "vard_channel": None,
            "var1_is_voltage": True,
            "var2_is_voltage": True,
            "active_channels": [],
            "available_vars": [],
        }

        self._connect_view_signals()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_config(self) -> SweepConfig:
        return copy.deepcopy(self._config)

    def get_json(self) -> dict:
        """
        Validate and build.  Raises ValueError listing all errors if the
        config is invalid.
        """
        errors = self._run_validation()
        if errors:
            raise ValueError(
                "Sweep config invalid:\n" + "\n".join(errors.values())
            )
        return self._build_json()

    # ── Private — signal wiring ────────────────────────────────────────────────

    def _connect_view_signals(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)

        # Measurement Setup
        v.integration_mode_changed.connect(self._on_integration_mode)
        v.short_time_committed.connect(self._on_short_time)
        v.long_cycles_changed.connect(self._on_long_cycles)
        v.wait_time_committed.connect(self._on_wait_time)

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

        # VAR2
        v.var2_start_committed.connect(self._on_var2_start)
        v.var2_step_committed.connect(self._on_var2_step)
        v.var2_points_changed.connect(self._on_var2_points)
        v.var2_comp_committed.connect(self._on_var2_comp)
        v.var2_pcomp_committed.connect(self._on_var2_pcomp)

        # VARD
        v.vard_offset_committed.connect(self._on_vard_offset)
        v.vard_ratio_committed.connect(self._on_vard_ratio)
        v.vard_comp_committed.connect(self._on_vard_comp)
        v.vard_pcomp_committed.connect(self._on_vard_pcomp)

        # Per-channel
        v.smu_standby_changed.connect(self._on_smu_standby)

        # Display vars
        v.display_var_toggled.connect(self._on_display_var_toggled)

        # Export
        v.export_requested.connect(self._on_export_requested)

    # ── Private — page activation ──────────────────────────────────────────────

    def _on_page_activated(self) -> None:
        self._rebuild_channel_context()
        self._push_full_state()

    def _rebuild_channel_context(self) -> None:
        """
        Pull a fresh ChannelsConfig snapshot and derive everything the view
        needs: which channels are active, which have VAR functions, units.
        """
        ch_cfg = self._channels_presenter.get_config()
        active: List[dict] = []
        available_vars: List[str] = []

        var1_ch: Optional[str] = None
        var2_ch: Optional[str] = None
        vard_ch: Optional[str] = None
        var1_is_v: bool = True
        var2_is_v: bool = True

        # ── SMUs ─────────────────────────────────────────────────────────────
        for idx, smu in ch_cfg.smu.items():
            if not smu.enabled:
                continue
            ch_id = f"SMU{idx}"
            fn = smu.function.value  # "CONST", "VAR1", "VAR2", "VAR1'"
            is_v = _is_voltage_mode(smu.mode.value)

            # Seed standby default for new channels
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
            available_vars.extend([smu.voltage_name, smu.current_name])

            if fn == "VAR1":
                var1_ch, var1_is_v = ch_id, is_v
            elif fn == "VAR2":
                var2_ch, var2_is_v = ch_id, is_v
            elif fn == "VAR1'":
                vard_ch = ch_id  # VARD inherits VAR1's voltage/current context

        # ── VMUs ─────────────────────────────────────────────────────────────
        for idx, vmu in ch_cfg.vmu.items():
            if not vmu.enabled:
                continue
            ch_id = f"VMU{idx}"
            active.append({
                "id": ch_id,
                "unit_type": "VMU",
                "function": "MONIT",
                "mode": vmu.mode.value,
                "v_name": vmu.voltage_name,
                "i_name": "",
                "standby": False,
            })
            available_vars.append(vmu.voltage_name)

        # ── VSUs ─────────────────────────────────────────────────────────────
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
            available_vars.append(vsu.voltage_name)

        # Initialise display_vars from all available on first activation
        if not self._config.display_vars and available_vars:
            self._config.display_vars = list(dict.fromkeys(available_vars))

        self._ctx = {
            "has_var1": var1_ch is not None,
            "has_var2": var2_ch is not None,
            "has_vard": vard_ch is not None,
            "var1_channel": var1_ch,
            "var2_channel": var2_ch,
            "vard_channel": vard_ch,
            "var1_is_voltage": var1_is_v,
            "var2_is_voltage": var2_is_v,
            "active_channels": active,
            "available_vars": list(dict.fromkeys(available_vars)),
        }

    def _push_full_state(self) -> None:
        ctx = self._ctx
        cfg = self._config
        SC = SweepConstraints

        self._view.display_channel_summary(ctx["active_channels"])

        self._view.display_var_sections(
            ctx["has_var1"], ctx["has_var2"], ctx["has_vard"]
        )

        if ctx["has_var1"] and ctx["var1_channel"]:
            is_v = ctx["var1_is_voltage"]
            self._view.display_var1_context(
                ctx["var1_channel"],
                SC.source_unit(is_v),
                SC.compliance_unit(is_v),
            )

        if ctx["has_var2"] and ctx["var2_channel"]:
            is_v = ctx["var2_is_voltage"]
            self._view.display_var2_context(
                ctx["var2_channel"],
                SC.source_unit(is_v),
                SC.compliance_unit(is_v),
            )

        if ctx["has_vard"] and ctx["vard_channel"]:
            # VARD borrows VAR1's physical units
            is_v = ctx["var1_is_voltage"]
            self._view.display_vard_context(
                ctx["vard_channel"],
                SC.source_unit(is_v),
                SC.compliance_unit(is_v),
            )

        self._view.display_config(self._config_snapshot())
        self._view.display_available_vars(
            ctx["available_vars"], cfg.display_vars
        )
        # Clear stale validation errors from a previous session
        self._view.display_validation_errors({})

    # ── Private — signal handlers ──────────────────────────────────────────────

    # Measurement Setup
    def _on_integration_mode(self, val: str) -> None:
        try:
            self._config.measurement_setup.integration_mode = IntegrationMode(
                val
            )
        except ValueError:
            pass

    def _on_short_time(self, val: float) -> None:
        clamped, _ = SweepConstraints.validate_short_time(val)
        self._config.measurement_setup.short_time = clamped

    def _on_long_cycles(self, val: int) -> None:
        clamped, _ = SweepConstraints.validate_long_cycles(val)
        self._config.measurement_setup.long_time_cycles = clamped

    def _on_wait_time(self, val: float) -> None:
        clamped, _ = SweepConstraints.validate_timing(val, "Wait time")
        self._config.measurement_setup.wait_time = clamped

    # Sweep Timing
    def _on_delay(self, val: float) -> None:
        clamped, _ = SweepConstraints.validate_timing(val, "Delay")
        self._config.delay = clamped

    def _on_hold_time(self, val: float) -> None:
        clamped, _ = SweepConstraints.validate_timing(val, "Hold time")
        self._config.hold_time = clamped

    def _on_sweep_stop(self, val: str) -> None:
        try:
            self._config.sweep_stop = SweepStop(val)
        except ValueError:
            pass

    # VAR1
    def _on_var1_mode(self, val: str) -> None:
        try:
            self._config.var1.mode = VAR1Mode(val)
        except ValueError:
            pass

    def _on_var1_spacing(self, val: str) -> None:
        try:
            self._config.var1.spacing = SweepSpacing(val)
        except ValueError:
            pass

    def _on_var1_start(self, val: float) -> None:
        self._config.var1.start = val

    def _on_var1_stop(self, val: float) -> None:
        self._config.var1.stop = val

    def _on_var1_step(self, val: float) -> None:
        self._config.var1.step = val

    def _on_var1_comp(self, val: float) -> None:
        self._config.var1.compliance = val

    def _on_var1_pcomp(self, val: float) -> None:
        self._config.var1.power_compliance = val

    # VAR2
    def _on_var2_start(self, val: float) -> None:
        self._config.var2.start = val

    def _on_var2_step(self, val: float) -> None:
        self._config.var2.step = val

    def _on_var2_points(self, val: int) -> None:
        clamped, _ = SweepConstraints.validate_points(val, "VAR2 points")
        self._config.var2.points = clamped

    def _on_var2_comp(self, val: float) -> None:
        self._config.var2.compliance = val

    def _on_var2_pcomp(self, val: float) -> None:
        self._config.var2.power_compliance = val

    # VARD
    def _on_vard_offset(self, val: float) -> None:
        self._config.vard.offset = val

    def _on_vard_ratio(self, val: float) -> None:
        clamped, _ = SweepConstraints.validate_ratio(val)
        self._config.vard.ratio = clamped

    def _on_vard_comp(self, val: float) -> None:
        self._config.vard.compliance = val

    def _on_vard_pcomp(self, val: float) -> None:
        self._config.vard.power_compliance = val

    # Channel + display
    def _on_smu_standby(self, ch_id: str, on: bool) -> None:
        self._config.channel_standby[ch_id] = on

    def _on_display_var_toggled(self, var_name: str, selected: bool) -> None:
        if selected and var_name not in self._config.display_vars:
            self._config.display_vars.append(var_name)
        elif not selected and var_name in self._config.display_vars:
            self._config.display_vars.remove(var_name)

    # Export
    def _on_export_requested(self) -> None:
        errors = self._run_validation()
        self._view.display_validation_errors(errors)
        if not errors:
            result = self._build_json()
            self._view.display_json(json.dumps(result, indent=4))

    # ── Private — validation ───────────────────────────────────────────────────

    def _run_validation(self) -> Dict[str, str]:
        return SweepConstraints.validate_all(
            self._config,
            var1_is_voltage=self._ctx.get("var1_is_voltage", True),
            var2_is_voltage=self._ctx.get("var2_is_voltage", True),
            has_var1=self._ctx.get("has_var1", False),
            has_var2=self._ctx.get("has_var2", False),
            has_vard=self._ctx.get("has_vard", False),
        )

    # ── Private — JSON builder ─────────────────────────────────────────────────

    def _build_json(self) -> dict:
        """
        Merge channel context (from ChannelsPresenter) with SweepConfig
        into the 4155/56 JSON structure.

        Convention:
          - "VAR1'" function → "VARD" key in channels section
          - power_compliance → "pcompliance" key in sweep_setup sections
          - Disabled channels → {"disable": 1}
        """
        cfg = self._config
        ch_cfg = self._channels_presenter.get_config()
        channels_json: Dict[str, Any] = {}

        # SMUs
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
                    if cfg.channel_standby.get(ch_id, False)
                    else "OFF",
                }
            else:
                channels_json[ch_id] = {"disable": 1}

        # VMUs
        for idx in range(1, 3):
            ch_id = f"VMU{idx}"
            vmu = ch_cfg.vmu.get(idx)
            if vmu and vmu.enabled:
                channels_json[ch_id] = {
                    "v_name": vmu.voltage_name,
                    "vmu_mode": vmu.mode.value,
                }
            else:
                channels_json[ch_id] = {"disable": 1}

        # VSUs
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

        # Measurement setup — all fields always present
        ms = cfg.measurement_setup
        meas_json = {
            "integration_mode": ms.integration_mode.value,
            "short_time": ms.short_time,
            "long_time_cycles": ms.long_time_cycles,
            "wait_time": ms.wait_time,
        }

        # Sweep setup — VAR sections included only when function is assigned
        sweep_json: Dict[str, Any] = {
            "delay": cfg.delay,
            "hold_time": cfg.hold_time,
            "sweep_stop": cfg.sweep_stop.value,
        }

        if self._ctx.get("has_var1"):
            v1 = cfg.var1
            sweep_json["var1"] = {
                "mode": v1.mode.value,
                "spacing": v1.spacing.value,
                "start": v1.start,
                "stop": v1.stop,
                "step": v1.step,
                "compliance": v1.compliance,
                "pcompliance": v1.power_compliance,
            }

        if self._ctx.get("has_var2"):
            v2 = cfg.var2
            sweep_json["var2"] = {
                "start": v2.start,
                "step": v2.step,
                "points": v2.points,
                "compliance": v2.compliance,
                "pcompliance": v2.power_compliance,
            }

        if self._ctx.get("has_vard"):
            vd = cfg.vard
            sweep_json["vard"] = {
                "offset": vd.offset,
                "ratio": vd.ratio,
                "compliance": vd.compliance,
                "pcompliance": vd.power_compliance,
            }

        return {
            "mode": "SWEEP",
            "channels": channels_json,
            "measurement_setup": meas_json,
            "sweep_setup": sweep_json,
            "display_vars": list(cfg.display_vars),
        }

    # ── Private — view snapshot ────────────────────────────────────────────────

    def _config_snapshot(self) -> dict:
        """Plain-dict copy of SweepConfig for display_config(snap) calls."""
        cfg = self._config
        ms = cfg.measurement_setup
        return {
            "measurement_setup": {
                "integration_mode": ms.integration_mode.value,
                "short_time": ms.short_time,
                "long_time_cycles": ms.long_time_cycles,
                "wait_time": ms.wait_time,
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
            },
            "var2": {
                "start": cfg.var2.start,
                "step": cfg.var2.step,
                "points": cfg.var2.points,
                "compliance": cfg.var2.compliance,
                "power_compliance": cfg.var2.power_compliance,
            },
            "vard": {
                "offset": cfg.vard.offset,
                "ratio": cfg.vard.ratio,
                "compliance": cfg.vard.compliance,
                "power_compliance": cfg.vard.power_compliance,
            },
        }
