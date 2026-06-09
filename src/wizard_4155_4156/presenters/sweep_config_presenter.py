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
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject

from wizard_4155_4156.models.sweep_config import (
    DISPLAY_VARS_MAX,
    IntegrationMode,
    SweepConfig,
    SweepConstraints,
    SweepSpacing,
    SweepStop,
    VAR1Mode,
)
from wizard_4155_4156.views.pages.sweep_config_page import SweepConfigPageView

# ── Helpers ───────────────────────────────────────────────────────────────────


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


# ── Presenter ─────────────────────────────────────────────────────────────────


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
        channels_presenter,  # ChannelsPresenter — loose type to avoid circular
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._channels_presenter = channels_presenter
        self._config = SweepConfig()

        # Populated on every page_activated from ChannelsPresenter.get_config()
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
            "active_channels": [],
            "available_vars": [],
        }

        self._connect_view_signals()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_config(self) -> SweepConfig:
        return copy.deepcopy(self._config)

    def get_json(self) -> dict:
        """Build and return the JSON dict.  Raises ValueError if invalid."""
        errors = self._run_validation()
        if errors:
            raise ValueError(
                "Sweep config invalid:\n" + "\n".join(errors.values())
            )
        return self._build_json()

    # ── Signal wiring ──────────────────────────────────────────────────────────

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

        # Channels + vars
        v.smu_standby_changed.connect(self._on_smu_standby)
        v.display_var_toggled.connect(self._on_display_var_toggled)

        # Export
        v.export_requested.connect(self._on_export_requested)

        # Ranges
        v.range_changed.connect(self._on_range_changed)

    # ── Page activation ────────────────────────────────────────────────────────

    def _on_page_activated(self) -> None:
        self._rebuild_channel_context()
        self._push_full_state()
        self._update_validation()

    def _rebuild_channel_context(self) -> None:
        """
        Pull a fresh ChannelsConfig snapshot and derive the full context:
        which channels are active, their VAR assignments, and sweep units.
        VSU channels assigned to VAR1/VAR2 are flagged with is_vsu=True so
        the view can apply the ±20 V widget bounds instead of ±100 V.
        """
        ch_cfg = self._channels_presenter.get_config()
        active: List[dict] = []
        available_vars: List[str] = []

        var1_ch: Optional[str] = None
        var2_ch: Optional[str] = None
        vard_ch: Optional[str] = None
        var1_is_v: bool = True
        var2_is_v: bool = True
        var1_is_vsu: bool = False
        var2_is_vsu: bool = False

        # ── SMUs ──────────────────────────────────────────────────────────────
        for idx, smu in ch_cfg.smu.items():
            if not smu.enabled:
                continue
            ch_id = f"SMU{idx}"
            fn = smu.function.value  # "CONST", "VAR1", "VAR2", "VAR1'"
            is_v = _is_voltage_mode(smu.mode.value)

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
                var1_ch, var1_is_v, var1_is_vsu = ch_id, is_v, False
            elif fn == "VAR2":
                var2_ch, var2_is_v, var2_is_vsu = ch_id, is_v, False
            elif fn == "VAR1'":
                vard_ch = ch_id

        # ── VMUs ──────────────────────────────────────────────────────────────
        for idx, vmu in ch_cfg.vmu.items():
            if not vmu.enabled:
                continue
            ch_id = f"VMU{idx}"
            active.append({
                "id": ch_id,
                "unit_type": "VMU",
                "function": "MONITOR",
                "mode": vmu.mode.value,
                "v_name": vmu.voltage_name,
                "i_name": "",
                "standby": False,
            })
            available_vars.append(vmu.voltage_name)

        # ── VSUs ──────────────────────────────────────────────────────────────
        # VSUs source voltage only (always is_voltage=True, ±20 V range).
        for idx, vsu in ch_cfg.vsu.items():
            if not vsu.enabled:
                continue
            ch_id = f"VSU{idx}"
            fn = vsu.function.value

            active.append({
                "id": ch_id,
                "unit_type": "VSU",
                "function": fn,
                "mode": "V",
                "v_name": vsu.voltage_name,
                "i_name": "",
                "standby": False,
            })
            available_vars.append(vsu.voltage_name)

            if fn == "VAR1":
                var1_ch, var1_is_v, var1_is_vsu = ch_id, True, True
            elif fn == "VAR2":
                var2_ch, var2_is_v, var2_is_vsu = ch_id, True, True
            elif fn == "VAR1'":
                vard_ch = ch_id
                # VARD from a VSU → offset uses VSU voltage range (±20 V)
                # Presenter sets is_vsu=True on the VARD context so the view
                # applies the correct offset bounds.

        # Filter display_vars to only keep currently available variables
        self._config.display_vars = [
            v for v in self._config.display_vars if v in available_vars
        ]

        # Initialise display_vars from all available variables on first use
        if not self._config.display_vars and available_vars:
            unique_vars = list(dict.fromkeys(available_vars))
            self._config.display_vars = unique_vars[:DISPLAY_VARS_MAX]

        # Prune ranges for disabled/inactive measurement units (SMUs and VMUs)
        # and initialize defaults (AUTO) for new active units.
        active_meas_units = {
            ch["id"] for ch in active if ch["unit_type"] in ("SMU", "VMU")
        }
        updated_ranges = {}
        for uid in active_meas_units:
            if uid in self._config.measurement_setup.ranges:
                updated_ranges[uid] = self._config.measurement_setup.ranges[
                    uid
                ]
            else:
                updated_ranges[uid] = {"mode": "AUTO"}
        self._config.measurement_setup.ranges = updated_ranges

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
            "active_channels": active,
            "available_vars": list(dict.fromkeys(available_vars)),
        }

    def _push_full_state(self) -> None:
        ctx = self._ctx
        cfg = self._config

        self._view.display_channel_summary(ctx["active_channels"])
        self._view.display_ranges_setup(
            ctx["active_channels"],
            ctx["instrument_model"],
            cfg.measurement_setup.ranges,
        )

        self._view.display_var_sections(
            ctx["has_var1"], ctx["has_var2"], ctx["has_vard"]
        )

        if ctx["has_var1"] and ctx["var1_channel"]:
            self._view.display_var1_context(
                ctx["var1_channel"],
                is_voltage=ctx["var1_is_voltage"],
                is_vsu=ctx["var1_is_vsu"],
            )

        if ctx["has_var2"] and ctx["var2_channel"]:
            self._view.display_var2_context(
                ctx["var2_channel"],
                is_voltage=ctx["var2_is_voltage"],
                is_vsu=ctx["var2_is_vsu"],
            )

        if ctx["has_vard"] and ctx["vard_channel"]:
            # VARD follows VAR1's voltage/current type
            self._view.display_vard_context(
                ctx["vard_channel"],
                is_voltage=ctx["var1_is_voltage"],
                is_vsu=ctx["var1_is_vsu"],
            )

        self._view.display_config(self._config_snapshot())
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

    def _on_var2_start(self, val: float) -> None:
        self._config.var2.start = val
        self._update_validation()

    def _on_var2_step(self, val: float) -> None:
        self._config.var2.step = val
        self._update_validation()

    def _on_var2_points(self, val: int) -> None:
        self._config.var2.points = val
        self._update_validation()

    def _on_var2_comp(self, val: float) -> None:
        self._config.var2.compliance = val
        self._update_validation()

    def _on_var2_pcomp(self, val: float) -> None:
        self._config.var2.power_compliance = val
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

    def _on_smu_standby(self, ch_id: str, on: bool) -> None:
        self._config.channel_standby[ch_id] = on
        self._update_validation()

    def _on_display_var_toggled(self, var_name: str, selected: bool) -> None:
        if selected and var_name not in self._config.display_vars:
            self._config.display_vars.append(var_name)
        elif not selected and var_name in self._config.display_vars:
            self._config.display_vars.remove(var_name)
        self._update_validation()

    def _on_export_requested(self) -> None:
        errors = self._run_validation()
        if not errors:
            result = self._build_json()
            self._view.display_json(json.dumps(result, indent=4))

    # ── Validation (model driven) ──────────────────────────────────────────────

    def _run_validation(self) -> Dict[str, str]:
        """
        Query input-level validation errors from the view, and combine them
        with the model's validation constraints.
        """
        errors = self._view.get_input_errors()

        model_errors = SweepConstraints.validate_config(
            cfg=self._config,
            has_var1=self._ctx.get("has_var1", False),
            has_var2=self._ctx.get("has_var2", False),
            has_vard=self._ctx.get("has_vard", False),
            var1_is_voltage=self._ctx.get("var1_is_voltage", True),
            var1_is_vsu=self._ctx.get("var1_is_vsu", False),
            var2_is_voltage=self._ctx.get("var2_is_voltage", True),
            var2_is_vsu=self._ctx.get("var2_is_vsu", False),
        )

        for i, err in enumerate(model_errors):
            errors[f"model_err_{i}"] = err

        return errors

    def _update_validation(self) -> None:
        errors = self._run_validation()
        if not errors:
            msg = "Configuration is valid"
            if self._ctx.get("has_var1"):
                v1 = self._config.var1
                step_val = (
                    v1.step if v1.spacing == SweepSpacing.LINEAR else 0.0
                )
                v1_count = SweepConstraints.var1_step_count(
                    v1.start, v1.stop, step_val, v1.spacing
                )
                if v1_count is not None:
                    if self._ctx.get("has_var2"):
                        total = v1_count * self._config.var2.points
                        msg += f" ({v1_count} x {self._config.var2.points} = {total} points)"
                    else:
                        msg += f" ({v1_count} points)"
            self._view.display_validation_status(True, msg)
        else:
            first_err = list(errors.values())[0]
            if len(errors) > 1:
                first_err += f" +{len(errors) - 1}"
            self._view.display_validation_status(False, first_err)

    # ── JSON builder ───────────────────────────────────────────────────────────

    def _build_json(self) -> dict:
        """
        Merge channel context (from ChannelsPresenter) with SweepConfig.

        JSON conventions:
          "VAR1'"   function key → "VARD"
          power_compliance field → "pcompliance"
          wait_multiplier field  → "wait_time"  (backward-compat with spec)
          Disabled channels      → {"disable": 1}
        """
        cfg = self._config
        ch_cfg = self._channels_presenter.get_config()
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
            if vmu and vmu.enabled:
                channels_json[ch_id] = {
                    "v_name": vmu.voltage_name,
                    "vmu_mode": vmu.mode.value,
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
        meas_json = {
            "integration_mode": ms.integration_mode.value,
            "short_time": ms.short_time,
            "long_time_cycles": ms.long_time_cycles,
            "wait_time": ms.wait_multiplier,  # JSON key kept as "wait_time"
            "ranges": ms.ranges,
        }

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

    # ── Config snapshot (for display_config) ──────────────────────────────────

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
