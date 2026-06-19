"""
presenters/measurements_presenter.py
-------------------------------------
Presenter for the Measurements & Run page.

Orchestrates the existing SCPI → GPIB pipeline:

  config (live Sweep Config page  OR  a loaded .json file)
        │
        ├─ MeasurementSetupDirector.setup_measurement ─┐
        ├─ MeasurementRunDirector.run_measurement ─────┤→ ConnectorPresenter
        └─ MeasurementRunDirector.take_data ───────────┘   .trigger_* (pool)

Hardware I/O is never touched here directly — it is delegated to the
ConnectorPresenter, which owns the single-thread GPIB pool.  Run controls are
gated on the live connection state (``connection_changed``) and the busy state
(``hardware_busy``) of that presenter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Slot

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.SCPI.measurement_run_director import (
    MeasurementRunDirector,
)
from wizard_4155_4156.SCPI.measurement_setup_director import (
    MeasurementSetupDirector,
)
from wizard_4155_4156.views.pages.measurements_page import MeasurementsPageView

# Defaults for fetching trace data (see MeasureRunCommandBuilder literals).
_FETCH_FORMAT = "REAL"
_FETCH_LENGTH = 64
_FETCH_BORDER = "NORM"


class MeasurementsPresenter(QObject):
    """Mediates between MeasurementsPageView and the directors / connector."""

    def __init__(
        self,
        view: MeasurementsPageView,
        config_provider,  # MeasureConfigFactory — loose type to avoid cycles
        connector_presenter,  # ConnectorPresenter — loose type to avoid cycles
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._config_provider = config_provider
        self._connector_presenter = connector_presenter

        self._setup_director = MeasurementSetupDirector()
        self._run_director = MeasurementRunDirector()

        # None ⇒ use the live measure-config page; else use this loaded dict.
        self._loaded_config: Optional[Dict[str, Any]] = None
        self._loaded_name: str = ""

        self._connected = connector_presenter.is_connected()
        self._busy = False

        self._connect_signals()

    # ── Wiring ───────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)
        v.apply_setup_requested.connect(self._on_apply_setup)
        v.run_fetch_requested.connect(self._on_run_fetch)
        v.full_sequence_requested.connect(self._on_full_sequence)
        v.load_setup_file_requested.connect(self._on_load_setup_file)
        v.use_live_config_requested.connect(self._on_use_live_config)

        self._connector_presenter.connection_changed.connect(
            self._on_connection_changed
        )
        self._connector_presenter.hardware_busy.connect(self._on_hardware_busy)

    # ── View-intent slots ─────────────────────────────────────────────────

    @Slot()
    def _on_page_activated(self) -> None:
        self._refresh()

    @Slot()
    def _on_apply_setup(self) -> None:
        config = self._resolve_config()
        if config is None:
            return
        setup_cmds = self._setup_director.build_full_setup(config)
        self._connector_presenter.trigger_setup_only(setup_cmds)

    @Slot()
    def _on_run_fetch(self) -> None:
        config = self._resolve_config()
        if config is None:
            return
        run_cmds = self._run_director.run_measurement({"standby": "OFF"})
        fetch_cmds = self._run_director.take_data(self._fetch_config(config))
        self._connector_presenter.trigger_run_only(run_cmds, fetch_cmds)

    @Slot()
    def _on_full_sequence(self) -> None:
        config = self._resolve_config()
        if config is None:
            return
        setup_cmds = self._setup_director.build_full_setup(config)
        run_cmds = self._run_director.run_measurement({"standby": "OFF"})
        fetch_cmds = self._run_director.take_data(self._fetch_config(config))
        self._connector_presenter.trigger_full_sequence(
            setup_cmds, run_cmds, fetch_cmds
        )

    @Slot(str)
    def _on_load_setup_file(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8") as fp:
                config = json.load(fp)
            if not isinstance(config, dict) or "mode" not in config:
                raise ValueError(
                    "Setup file must be a JSON object with a 'mode'."
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._view.display_error(
                tr_ui(CommandWizardText.MEAS_FILE_ERROR).format(error=exc)
            )
            return

        self._loaded_config = config
        self._loaded_name = Path(path).name
        self._view.display_error("")
        self._refresh()

    @Slot()
    def _on_use_live_config(self) -> None:
        self._loaded_config = None
        self._loaded_name = ""
        self._view.display_error("")
        self._refresh()

    # ── Connector-state slots ─────────────────────────────────────────────

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, _name: str) -> None:
        self._connected = connected
        self._update_controls()

    @Slot(bool)
    def _on_hardware_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_controls()
        if busy:
            self._view.display_status(
                tr_ui(CommandWizardText.MEAS_STATUS_RUNNING)
            )
        elif self._connected:
            self._view.display_status(
                tr_ui(CommandWizardText.MEAS_STATUS_READY)
            )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _resolve_config(self) -> Optional[Dict[str, Any]]:
        """Return the active config, or None (and show an error) if invalid."""
        if self._loaded_config is not None:
            self._view.display_error("")
            return self._loaded_config
        try:
            config = self._config_provider.get_json()
        except ValueError as exc:
            self._view.display_error(
                tr_ui(CommandWizardText.MEAS_CONFIG_ERROR).format(error=exc)
            )
            return None
        self._view.display_error("")
        return config

    @staticmethod
    def _fetch_config(config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "format": _FETCH_FORMAT,
            "length": _FETCH_LENGTH,
            "border": _FETCH_BORDER,
            "variables": config.get("display_vars", []),
        }

    @staticmethod
    def _summarize(config: Dict[str, Any]) -> str:
        mode = config.get("mode", "—")
        channels = [
            unit
            for unit, settings in config.get("channels", {}).items()
            if not settings.get("disable")
        ]
        display_vars = config.get("display_vars", [])
        return tr_ui(CommandWizardText.MEAS_SUMMARY_TEMPLATE).format(
            mode=mode,
            channels=", ".join(channels) if channels else "none",
            vars=", ".join(display_vars) if display_vars else "none",
        )

    def _refresh(self) -> None:
        """Push source, summary, preview, and control state to the view."""
        if self._loaded_config is not None:
            self._view.display_source(
                tr_ui(CommandWizardText.MEAS_SOURCE_FILE).format(
                    name=self._loaded_name
                )
            )
            self._view.display_config_summary(
                self._summarize(self._loaded_config)
            )
            self._view.display_config_preview(self._loaded_config)
        else:
            self._view.display_source(
                tr_ui(CommandWizardText.MEAS_SOURCE_LIVE)
            )
            try:
                config = self._config_provider.get_json()
                self._view.display_config_summary(self._summarize(config))
                self._view.display_config_preview(config)
            except ValueError:
                self._view.display_config_summary(
                    tr_ui(CommandWizardText.MEAS_SUMMARY_EMPTY)
                )
                self._view.display_config_preview(None)

        self._update_controls()

    def _update_controls(self) -> None:
        enabled = self._connected and not self._busy
        self._view.set_controls_enabled(enabled)
        if not self._connected:
            self._view.display_status(
                tr_ui(CommandWizardText.MEAS_STATUS_DISCONNECTED)
            )
        elif not self._busy:
            self._view.display_status(
                tr_ui(CommandWizardText.MEAS_STATUS_READY)
            )
