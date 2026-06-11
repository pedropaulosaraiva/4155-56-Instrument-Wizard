"""
presenters/channels_presenter.py
---------------------------------
Presenter for the channels configuration page.

Responsibilities
----------------
Model ownership
  Holds and mutates the single ChannelsConfig instance.

Constraint enforcement
  Every signal handler calls the relevant ChannelsConstraints rules and
  clamps / propagates changes before calling display_* on the view.
  No invalid configuration can exist in the model after a handler returns.

View driving
  Calls ChannelsPageView display_* methods to reflect the new model state.
  Never accesses view-internal widgets directly.

Public API for other presenters
  get_config() → ChannelsConfig
    Returns a deep copy of the current configuration.
    SweepConfigPresenter and MeasurementsPresenter will call this when they
    need to know which channels are active and what their variable names are.

Constraint summary (4155/56 rules)
------------------------------------
Model ────────────────────────────────────────────────────────────
  4155B / 4155C  → VMU panel hidden
  4155B / 4156B  → QSCV mode unavailable; clamped to SWEEP on switch

Mode ─────────────────────────────────────────────────────────────
  SWEEP    → SMU: CONST/VAR1/VAR2/VAR1'; VSU: same; VMU: active
  SAMPLING → SMU: CONST only;            VSU: CONST only; VMU: active
  QSCV     → SMU: CONST/VAR1;            VSU: CONST only; VMU: disabled

SMU mode COMM → function locked to CONST; combo disabled in view.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QObject, Signal

from wizard_4155_4156.models.channels import (
    ChannelsConfig,
    ChannelsConstraints,
    InstrumentModel,
    MeasurementMode,
    SMUMode,
    UnitFunction,
    VMUMode,
)
from wizard_4155_4156.views.pages.channels_page import ChannelsPageView


class ChannelsPresenter(QObject):
    """
    Mediates between ChannelsPageView (View) and ChannelsConfig (Model).
    """

    measure_configured = Signal(dict)

    def __init__(
        self,
        view: ChannelsPageView,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._config = ChannelsConfig()  # default: 4155C, SWEEP mode
        self._connect_view_signals()
        self._push_full_state()  # initialise view from default config

    # ── Public API ───────────────────────────────────────────────────────────

    def get_config(self) -> ChannelsConfig:
        """
        Return a deep copy so callers cannot mutate the presenter's model.
        """
        return copy.deepcopy(self._config)

    # ── Signal → model → view handlers ───────────────────────────────────────

    def _on_instrument_model_changed(self, value: str) -> None:
        try:
            new_model = InstrumentModel(value)
        except ValueError:
            return

        self._config.instrument_model = new_model

        # Clamp measurement mode if QSCV is no longer supported
        allowed_modes = ChannelsConstraints.allowed_modes(new_model)
        self._config.measurement_mode = ChannelsConstraints.clamp_mode(
            self._config.measurement_mode, allowed_modes
        )

        # _push_full_state re-pushes the allowed mode list and full state.
        self._push_full_state()

    def _on_measurement_mode_changed(self, value: str) -> None:
        try:
            new_mode = MeasurementMode(value)
        except ValueError:
            return

        self._config.measurement_mode = new_mode

        # Clamp all SMU functions to what's allowed in the new mode
        allowed_smu_fns = ChannelsConstraints.smu_functions(new_mode)
        for smu in self._config.smu.values():
            smu.function = ChannelsConstraints.clamp_function(
                smu.function, allowed_smu_fns
            )

        # Clamp all VSU functions
        allowed_vsu_fns = ChannelsConstraints.vsu_functions(new_mode)
        for vsu in self._config.vsu.values():
            vsu.function = ChannelsConstraints.clamp_function(
                vsu.function, allowed_vsu_fns
            )

        self._push_full_state()

    def _on_gndu_changed(self, checked: bool) -> None:
        self._config.gndu_to_common = checked
        self._update_validation()

    def _on_inlink_changed(self, checked: bool) -> None:
        self._config.inlink_enabled = checked
        self._update_validation()

    # SMU handlers ────────────────────────────────────────────────────────────

    def _on_smu_enabled(self, index: int, enabled: bool) -> None:
        self._config.smu[index].enabled = enabled
        self._update_validation()

    def _on_smu_mode(self, index: int, value: str) -> None:
        try:
            new_mode = SMUMode(value)
        except ValueError:
            return
        self._config.smu[index].mode = new_mode

        # Lock function to CONST when COMM mode is selected
        locked = ChannelsConstraints.smu_function_locked(new_mode)
        if locked:
            self._config.smu[index].function = UnitFunction.CONST
        self._view.display_smu_function_locked(index, locked)
        self._update_validation()

    def _on_smu_function(self, index: int, value: str) -> None:
        try:
            fn = UnitFunction(value)
        except ValueError:
            return
        allowed = ChannelsConstraints.smu_functions(
            self._config.measurement_mode
        )
        self._config.smu[index].function = ChannelsConstraints.clamp_function(
            fn, allowed
        )
        self._update_validation()

    def _on_smu_vname(self, index: int, name: str) -> None:
        self._config.smu[index].voltage_name = name
        self._update_validation()

    def _on_smu_iname(self, index: int, name: str) -> None:
        self._config.smu[index].current_name = name
        self._update_validation()

    # VMU handlers ────────────────────────────────────────────────────────────

    def _on_vmu_enabled(self, index: int, enabled: bool) -> None:
        self._config.vmu[index].enabled = enabled
        self._update_validation()

    def _on_vmu_mode(self, index: int, value: str) -> None:
        try:
            new_mode = VMUMode(value)
        except ValueError:
            return
        self._config.vmu[index].mode = new_mode
        self._update_validation()

    def _on_vmu_vname(self, index: int, name: str) -> None:
        self._config.vmu[index].voltage_name = name
        self._update_validation()

    # VSU handlers ────────────────────────────────────────────────────────────

    def _on_vsu_enabled(self, index: int, enabled: bool) -> None:
        self._config.vsu[index].enabled = enabled
        self._update_validation()

    def _on_vsu_function(self, index: int, value: str) -> None:
        try:
            fn = UnitFunction(value)
        except ValueError:
            return
        allowed = ChannelsConstraints.vsu_functions(
            self._config.measurement_mode
        )
        self._config.vsu[index].function = ChannelsConstraints.clamp_function(
            fn, allowed
        )
        self._update_validation()

    def _on_vsu_vname(self, index: int, name: str) -> None:
        self._config.vsu[index].voltage_name = name
        self._update_validation()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _connect_view_signals(self) -> None:
        v = self._view

        v.instrument_model_changed.connect(self._on_instrument_model_changed)
        v.measurement_mode_changed.connect(self._on_measurement_mode_changed)
        v.gndu_changed.connect(self._on_gndu_changed)
        v.inlink_changed.connect(self._on_inlink_changed)

        v.smu_enabled_changed.connect(self._on_smu_enabled)
        v.smu_mode_changed.connect(self._on_smu_mode)
        v.smu_function_changed.connect(self._on_smu_function)
        v.smu_vname_changed.connect(self._on_smu_vname)
        v.smu_iname_changed.connect(self._on_smu_iname)

        v.vmu_enabled_changed.connect(self._on_vmu_enabled)
        v.vmu_mode_changed.connect(self._on_vmu_mode)
        v.vmu_vname_changed.connect(self._on_vmu_vname)

        v.vsu_enabled_changed.connect(self._on_vsu_enabled)
        v.vsu_function_changed.connect(self._on_vsu_function)
        v.vsu_vname_changed.connect(self._on_vsu_vname)
        v.configure_measure_clicked.connect(self._on_configure_measure)

    def _push_full_state(self) -> None:
        """
        Compute the complete view state from the current config and push it.
        Called on init and after any change that affects multiple units
        (model switch, mode switch).
        """
        cfg = self._config
        mode = cfg.measurement_mode
        model = cfg.instrument_model

        allowed_modes = ChannelsConstraints.allowed_modes(model)
        allowed_smu_fns = ChannelsConstraints.smu_functions(mode)
        allowed_vsu_fns = ChannelsConstraints.vsu_functions(mode)
        vmu_usable = ChannelsConstraints.vmu_usable_in_mode(mode)

        # Build SMU state dicts
        smu_states = {
            idx: {
                "enabled": smu.enabled,
                "mode": smu.mode.value,
                "function": smu.function.value,
                "voltage_name": smu.voltage_name,
                "current_name": smu.current_name,
            }
            for idx, smu in cfg.smu.items()
        }

        # Build VMU state dicts
        vmu_states = {
            idx: {
                "enabled": vmu.enabled,
                "mode": vmu.mode.value,
                "voltage_name": vmu.voltage_name,
            }
            for idx, vmu in cfg.vmu.items()
        }

        # Build VSU state dicts
        vsu_states = {
            idx: {
                "enabled": vsu.enabled,
                "function": vsu.function.value,
                "voltage_name": vsu.voltage_name,
            }
            for idx, vsu in cfg.vsu.items()
        }

        # Full refresh
        self._view.display_config(
            model=model.value,
            mode=mode.value,
            gndu=cfg.gndu_to_common,
            inlink=cfg.inlink_enabled,
            smu_states=smu_states,
            vmu_states=vmu_states,
            vsu_states=vsu_states,
        )

        # Structural changes
        self._view.display_available_modes([m.value for m in allowed_modes])

        # Per-card function lists and COMM locks for SMUs
        for idx, smu in cfg.smu.items():
            self._view.display_smu_functions(
                idx, [f.value for f in allowed_smu_fns]
            )
            locked = ChannelsConstraints.smu_function_locked(smu.mode)
            self._view.display_smu_function_locked(idx, locked)

        # VMU usability per mode
        for idx in cfg.vmu:
            self._view.display_vmu_card_usable(idx, vmu_usable)

        # Per-card function lists for VSUs
        for idx in cfg.vsu:
            self._view.display_vsu_functions(
                idx, [f.value for f in allowed_vsu_fns]
            )

        self._update_validation()

    def _update_validation(self) -> None:
        errors = ChannelsConstraints.validate_config(self._config)
        if not errors:
            self._view.display_validation_status(
                True, "Configuration is valid"
            )
        else:
            first_err = errors[0]
            if len(errors) > 1:
                first_err += f" +{len(errors) - 1}"
            self._view.display_validation_status(False, first_err)

    def _on_configure_measure(self) -> None:
        # Never generate a measurement page from an invalid channel layout;
        # the validation label already shows the blocking error.
        if ChannelsConstraints.validate_config(self._config):
            return
        self.measure_configured.emit(self._config.to_measure_dict())
