"""
presenters/runs_presenter.py
----------------------------
Presenter for the Measurement Runs (CRUD) page.

Wires ``RunsPageView`` to the per-project database (via ``ProjectManager``),
the live measurement-config provider (the ``MeasureConfigFactory``), and the
global settings.  It is the only layer here touching both Qt and the ORM.

All DB writes happen on the GUI thread inside this presenter — never on a GPIB
worker (no ``Session`` is ever handed to a worker).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal
from sqlalchemy.exc import IntegrityError

from wizard_4155_4156.db.assembler import (
    config_dict_to_setup,
    execution_to_data_dict,
    fetch_result_to_execution,
    setup_to_config_dict,
)
from wizard_4155_4156.db.repository import (
    ExecutionRepository,
    SetupRepository,
)
from wizard_4155_4156.extra_widgets.setup_metadata_dialog import (
    SetupMetadataDialog,
)
from wizard_4155_4156.SCPI.measurement_run_director import (
    MeasurementRunDirector,
)
from wizard_4155_4156.SCPI.measurement_setup_director import (
    MeasurementSetupDirector,
)
from wizard_4155_4156.views.pages.runs_page import RunsPageView

_SAMPLE_POINTS = 21

# Trace-fetch defaults (mirror MeasurementsPresenter / MeasureRunCommandBuilder).
_FETCH_FORMAT = "REAL"
_FETCH_LENGTH = 64
_FETCH_BORDER = "NORM"


class RunsPresenter(QObject):
    """Mediates RunsPageView ↔ the project database."""

    #: Emitted with a ``{var: [values]}`` dict so MainWindow can show the table.
    execution_data_ready = Signal(dict)

    def __init__(
        self,
        view: RunsPageView,
        project_manager,
        config_provider,  # MeasureConfigFactory — duck-typed get_json()
        settings_manager,  # GlobalSettingsManager
        connector_presenter,  # ConnectorPresenter — hardware I/O
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._projects = project_manager
        self._config_provider = config_provider
        self._settings = settings_manager
        self._connector = connector_presenter
        self._setup_director = MeasurementSetupDirector()
        self._run_director = MeasurementRunDirector()

        self._current_setup_id: Optional[int] = None
        self._connected = connector_presenter.is_connected()
        self._busy = False
        # Setup id whose run was triggered from here and whose fetched data
        # should be persisted when it returns (None ⇒ don't persist), plus the
        # user-chosen execution name/description for that pending run.
        self._pending_run_setup_id: Optional[int] = None
        self._pending_run_name: Optional[str] = None
        self._pending_run_desc: Optional[str] = None
        self._connect()
        self._push_hardware_state()

    # ── Public API (called by MainWindow) ────────────────────────────────────

    def set_database(self, _db=None) -> None:
        """Called when a project is created/opened/closed."""
        self._current_setup_id = None
        self._refresh()
        self._push_hardware_state()

    # ── Wiring ───────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        v = self._view
        v.page_activated.connect(self._refresh_keep_selection)
        v.setup_selected.connect(self._on_setup_selected)
        v.execution_selected.connect(self._on_execution_selected)
        v.create_setup_requested.connect(self._on_create_setup)
        v.edit_setup_metadata_requested.connect(self._on_edit_metadata)
        v.delete_setup_requested.connect(self._on_delete_setup)
        v.delete_execution_requested.connect(self._on_delete_execution)
        v.insert_sample_execution_requested.connect(self._on_insert_sample)
        v.view_execution_data_requested.connect(self._on_view_data)
        v.apply_setup_requested.connect(self._on_apply_setup)
        v.apply_run_fetch_requested.connect(self._on_apply_run_fetch)

        self._connector.connection_changed.connect(self._on_connection_changed)
        self._connector.hardware_busy.connect(self._on_hardware_busy)
        self._connector.data_ready.connect(self._on_connector_data)

    # ── Refresh ──────────────────────────────────────────────────────────────

    def _refresh(self, select_setup_id: Optional[int] = None) -> None:
        db = self._projects.current_db
        if db is None:
            self._view.display_empty(
                "No project open. Create or open a project from the Home page."
            )
            return
        with db.session() as s:
            rows = SetupRepository.list_rows(s)
        exists = select_setup_id is not None and any(
            r.id == select_setup_id for r in rows
        )
        self._view.display_error("")
        self._view.display_setups(rows)
        self._view.display_status(
            f"Project '{self._projects.current_name}' — "
            f"{len(rows)} setup(s)."
        )
        if exists:
            self._view.select_setup(select_setup_id)
        else:
            self._current_setup_id = None

    def _refresh_keep_selection(self) -> None:
        self._refresh(select_setup_id=self._current_setup_id)

    # ── Selection ────────────────────────────────────────────────────────────

    def _on_setup_selected(self, setup_id: int) -> None:
        self._current_setup_id = setup_id
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            config = setup_to_config_dict(setup)
            summary = self._summary(setup, config)
            exec_rows = ExecutionRepository.list_rows(s, setup_id)
        self._view.display_setup_detail(config, summary)
        self._view.display_executions(exec_rows)

    def _on_execution_selected(self, _execution_id: int) -> None:
        # Selection tracked by the view; nothing to fetch until "View data".
        pass

    # ── Mutations ────────────────────────────────────────────────────────────

    def _on_create_setup(self, name: str, description: str) -> None:
        error = self.create_setup_from_current(name, description)
        if error:
            self._view.display_error(error)

    def create_setup_from_current(
        self, name: str, description: str
    ) -> Optional[str]:
        """
        Persist the live measurement config as a new setup.

        Public so MainWindow can trigger it from the measurement-config page's
        "Save Setup" button.  Returns ``None`` on success, or an error message
        string the caller should surface.  On success the Runs view is
        refreshed with the new setup selected.
        """
        db = self._projects.current_db
        if db is None:
            return "Open or create a project first."
        try:
            config = self._config_provider.get_json()
        except ValueError as exc:
            return f"No valid measurement config to save: {exc}"

        settings = self._settings.get()
        new_id: Optional[int] = None
        try:
            with db.session() as s:
                if SetupRepository.name_exists(s, name):
                    return f"A setup named '{name}' already exists."
                setup = config_dict_to_setup(
                    config,
                    name=name,
                    description=description or None,
                    author=settings.author or None,
                    organization=settings.organization or None,
                    instrument_model=settings.default_instrument_model,
                )
                SetupRepository.add(s, setup)
                new_id = setup.id
        except IntegrityError:
            return f"A setup named '{name}' already exists."
        self._refresh(select_setup_id=new_id)
        return None

    def _on_edit_metadata(
        self, setup_id: int, name: str, description: str
    ) -> None:
        db = self._projects.current_db
        if db is None:
            return
        try:
            with db.session() as s:
                SetupRepository.update_metadata(
                    s, setup_id, name, description or None
                )
        except IntegrityError:
            self._view.display_error(
                f"A setup named '{name}' already exists."
            )
            return
        self._refresh(select_setup_id=setup_id)

    def _on_delete_setup(self, setup_id: int) -> None:
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            SetupRepository.delete(s, setup_id)
        if self._current_setup_id == setup_id:
            self._current_setup_id = None
        self._refresh()

    def _on_delete_execution(self, execution_id: int) -> None:
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            ExecutionRepository.delete(s, execution_id)
        self._refresh(select_setup_id=self._current_setup_id)

    def _on_insert_sample(self, setup_id: int) -> None:
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            var_names = [
                dv.var_name
                for dv in sorted(
                    setup.display_vars, key=lambda d: d.position
                )
            ] or ["V1", "I1"]
            results = self._synthetic_results(var_names)
            exec_name = self._unique_exec_name(s, setup.name)
            execution = fetch_result_to_execution(
                results,
                setup=setup,
                name=exec_name,
                instrument_model=setup.instrument_model,
                is_synthetic=True,
            )
            ExecutionRepository.add(s, execution)
        self._view.display_error("")
        self._refresh(select_setup_id=setup_id)

    def _on_view_data(self, execution_id: int) -> None:
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            execution = ExecutionRepository.get(s, execution_id)
            if execution is None:
                return
            data = execution_to_data_dict(execution)
        self.execution_data_ready.emit(data)

    # ── Hardware run (selected setup) ────────────────────────────────────────

    def _on_apply_setup(self, setup_id: int) -> None:
        """Send the selected setup to the instrument only — no DB write."""
        config = self._config_for(setup_id)
        if config is None:
            return
        setup_cmds = self._setup_director.setup_measurement(config)
        self._connector.trigger_setup_only(setup_cmds)

    def _on_apply_run_fetch(self, setup_id: int) -> None:
        """Prompt for the execution name/description, then run the sequence."""
        default_name = self._default_run_name(setup_id)
        if default_name is None:
            return
        dlg = SetupMetadataDialog(
            title="Run & Fetch — name this execution",
            name=default_name,
            parent=self._view,
        )
        if not dlg.exec():
            return
        self._start_run_fetch(setup_id, dlg.get_name(), dlg.get_description())

    def _start_run_fetch(
        self, setup_id: int, name: str, description: str
    ) -> None:
        """Setup → run → fetch; the fetched data is persisted on return."""
        config = self._config_for(setup_id)
        if config is None:
            return
        setup_cmds = self._setup_director.setup_measurement(config)
        run_cmds = self._run_director.run_measurement({"standby": "OFF"})
        fetch_cmds = self._run_director.take_data(self._fetch_config(config))
        # Persist the result when data_ready returns (see _on_connector_data).
        self._pending_run_setup_id = setup_id
        self._pending_run_name = name
        self._pending_run_desc = description
        self._connector.trigger_full_sequence(setup_cmds, run_cmds, fetch_cmds)

    def _on_connector_data(self, data: dict) -> None:
        """A fetch completed — persist it iff *this* page triggered the run."""
        setup_id = self._pending_run_setup_id
        chosen_name = self._pending_run_name
        description = self._pending_run_desc
        self._pending_run_setup_id = None
        self._pending_run_name = None
        self._pending_run_desc = None
        if setup_id is None:
            return  # run came from elsewhere (legacy page) — not ours to save.
        db = self._projects.current_db
        if db is None or not data:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            # Honor the user's chosen name; fall back to a unique auto-name if
            # it is blank or already taken.
            name = chosen_name
            if not name or ExecutionRepository.name_exists(s, name):
                name = self._unique_exec_name(s, setup.name, suffix="run")
            execution = fetch_result_to_execution(
                data,
                setup=setup,
                name=name,
                description=description or None,
                instrument_model=setup.instrument_model,
                is_synthetic=False,
            )
            ExecutionRepository.add(s, execution)
        self._refresh(select_setup_id=setup_id)

    def _default_run_name(self, setup_id: int) -> Optional[str]:
        db = self._projects.current_db
        if db is None:
            return None
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return None
            return self._unique_exec_name(s, setup.name, suffix="run")

    def _on_connection_changed(self, connected: bool, _name: str) -> None:
        self._connected = connected
        self._push_hardware_state()

    def _on_hardware_busy(self, busy: bool) -> None:
        self._busy = busy
        self._push_hardware_state()

    def _config_for(self, setup_id: int) -> Optional[dict]:
        db = self._projects.current_db
        if db is None:
            return None
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return None
            return setup_to_config_dict(setup)

    def _push_hardware_state(self) -> None:
        ready = self._connected and not self._busy
        self._view.set_hardware_ready(ready)
        if self._busy:
            status = "Running…"
        elif self._connected:
            status = "Connected — ready"
        else:
            status = "Disconnected — connect an instrument to run"
        self._view.display_hardware_status(status)

    @staticmethod
    def _fetch_config(config: dict) -> dict:
        return {
            "format": _FETCH_FORMAT,
            "length": _FETCH_LENGTH,
            "border": _FETCH_BORDER,
            "variables": config.get("display_vars", []),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _summary(setup, config: dict) -> str:
        parts = [config.get("mode", "?"), setup.instrument_model]
        if setup.author:
            parts.append(f"by {setup.author}")
        if setup.organization:
            parts.append(setup.organization)
        parts.append(f"{len(config.get('display_vars', []))} display var(s)")
        return "   ·   ".join(parts)

    @staticmethod
    def _synthetic_results(
        var_names: list[str], n: int = _SAMPLE_POINTS
    ) -> dict[str, list[float]]:
        """Generate plausible per-variable sample data (no hardware needed)."""
        x = np.linspace(0.0, 1.0, n)
        out: dict[str, list[float]] = {}
        for i, name in enumerate(var_names):
            if name == "@INDEX":
                out[name] = [float(j) for j in range(n)]
            elif name == "@TIME":
                out[name] = (x * (n - 1) * 1e-3).tolist()
            else:
                out[name] = (np.sin(x * np.pi) * (i + 1) + x * (i + 1)).tolist()
        return out

    @staticmethod
    def _unique_exec_name(session, base: str, suffix: str = "sample") -> str:
        k = 1
        while True:
            candidate = f"{base}-{suffix}-{k}"
            if not ExecutionRepository.name_exists(session, candidate):
                return candidate
            k += 1
