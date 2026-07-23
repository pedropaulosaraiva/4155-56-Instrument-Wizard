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

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal
from sqlalchemy.exc import IntegrityError

from wizard_4155_4156.db.assembler import (
    config_dict_to_setup,
    fetch_result_to_execution,
    setup_to_config_dict,
)
from wizard_4155_4156.db.repository import (
    ExecutionRepository,
    SetupRepository,
)
from wizard_4155_4156.extra_widgets.import_measure_dialog import (
    ImportMeasureDialog,
)
from wizard_4155_4156.extra_widgets.setup_metadata_dialog import (
    SetupMetadataDialog,
)
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.channels import normalize_instrument_model
from wizard_4155_4156.models.config_loader import channels_config_from_setup
from wizard_4155_4156.models.data_import import (
    CsvOptions,
    ImportResult,
    parse_import_files,
)
from wizard_4155_4156.SCPI.measurement_run_director import (
    MeasurementRunDirector,
)
from wizard_4155_4156.SCPI.measurement_setup_director import (
    MeasurementSetupDirector,
)
from wizard_4155_4156.views.pages.runs_page import RunsPageView

_SAMPLE_POINTS = 21

#: instrument_model recorded on setups/executions imported from data files.
_IMPORT_INSTRUMENT = "External"

# Trace-fetch defaults
# (mirror LiveMeasurementRunner / MeasureRunCommandBuilder).
_FETCH_FORMAT = "REAL"
_FETCH_LENGTH = 64
_FETCH_BORDER = "NORM"


class RunsPresenter(QObject):
    """Mediates RunsPageView ↔ the project database."""

    #: Emitted with (setup_id, execution_id) so the Table page can load and
    #: display that execution (the DB read happens in TablePresenter).
    view_execution_requested = Signal(int, int)
    #: Emitted with (ChannelsConfig, config_dict) to open a copied config page.
    copy_to_config_requested = Signal(object, dict)

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
        self._connected_model: Optional[str] = None
        self._busy = False
        # Setup id whose run was triggered from here and whose fetched data
        # should be persisted when it returns (None ⇒ don't persist), plus the
        # user-chosen execution name/description for that pending run.
        self._pending_run_setup_id: Optional[int] = None
        self._pending_run_name: Optional[str] = None
        self._pending_run_desc: Optional[str] = None
        # Session-scoped: once the user opts out, stop warning about running a
        # setup on an instrument other than the one it was created for. Resets
        # on restart (the presenter is rebuilt per program run).
        self._suppress_instrument_mismatch = False
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
        v.edit_setup_metadata_requested.connect(self._on_edit_setup)
        v.delete_setup_requested.connect(self._on_delete_setup)
        v.delete_execution_requested.connect(self._on_delete_execution)
        v.insert_sample_execution_requested.connect(self._on_insert_sample)
        v.view_execution_data_requested.connect(self._on_view_data)
        v.apply_setup_requested.connect(self._on_apply_setup)
        v.apply_run_fetch_requested.connect(self._on_apply_run_fetch)
        v.copy_to_config_requested.connect(self._on_copy_to_config)
        v.import_measure_requested.connect(self._on_import_measure)
        v.import_execution_requested.connect(self._on_import_execution)

        self._connector.connection_changed.connect(self._on_connection_changed)
        self._connector.hardware_busy.connect(self._on_hardware_busy)
        self._connector.data_ready.connect(self._on_connector_data)

    # ── Refresh ──────────────────────────────────────────────────────────────

    def _refresh(self, select_setup_id: Optional[int] = None) -> None:
        db = self._projects.current_db
        if db is None:
            # Unreachable in normal flow — the Runs page is only navigable once
            # a project is open. Guard defensively without UI noise.
            return
        with db.session() as s:
            rows = SetupRepository.list_rows(s)
        exists = select_setup_id is not None and any(
            r.id == select_setup_id for r in rows
        )
        self._view.display_error("")
        self._view.display_setups(rows)
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

    def _on_create_setup(self) -> None:
        # The dialog drives the save via on_submit so a duplicate-name error is
        # shown red inside the still-open modal (never the page error bar).
        dlg = SetupMetadataDialog(
            title="Save setup",
            parent=self._view,
            on_submit=self.create_setup_from_current,
        )
        dlg.exec()

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

        # Estimated minimum-runtime interval (seconds), captured so the Runs
        # page can show it without recomputing.  None ⇒ indeterminate.
        try:
            runtime = self._config_provider.get_runtime_bounds()
        except ValueError:
            runtime = None
        runtime_min = runtime[0] if runtime else None
        runtime_max = runtime[1] if runtime else None

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
                    # The setup records the instrument defined on the Channels
                    # page (behind the live config), not a global default.
                    instrument_model=self._config_provider.get_instrument_model(),
                    runtime_min=runtime_min,
                    runtime_max=runtime_max,
                )
                SetupRepository.add(s, setup)
                new_id = setup.id
        except IntegrityError:
            return f"A setup named '{name}' already exists."
        self._refresh(select_setup_id=new_id)
        return None

    def _on_edit_setup(self, setup_id: int) -> None:
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            name, description = setup.name, setup.description or ""
        # As with create, the modal stays open and shows a duplicate-name error
        # in red rather than flashing it in the page error bar.
        dlg = SetupMetadataDialog(
            title="Edit setup",
            name=name,
            description=description,
            parent=self._view,
            on_submit=lambda n, d: self._update_metadata(setup_id, n, d),
        )
        dlg.exec()

    def _update_metadata(
        self, setup_id: int, name: str, description: str
    ) -> Optional[str]:
        db = self._projects.current_db
        if db is None:
            return "Open or create a project first."
        try:
            with db.session() as s:
                SetupRepository.update_metadata(
                    s, setup_id, name, description or None
                )
        except IntegrityError:
            return f"A setup named '{name}' already exists."
        self._refresh(select_setup_id=setup_id)
        return None

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

    def delete_all_runs(self) -> int:
        """Delete every recorded execution, preserving setups and graph scenes.

        Pure DB action invoked by the Preferences dialog's "Delete All
        Measurement Runs…" advanced option (the irreversible-confirmation UX
        lives in the dialog).  Returns the number of executions removed; 0 when
        no project is open.
        """
        db = self._projects.current_db
        if db is None:
            return 0
        with db.session() as s:
            deleted = ExecutionRepository.delete_all(s)
        self._refresh(select_setup_id=self._current_setup_id)
        return deleted

    def _reset_flags(self) -> tuple[bool, bool]:
        """(skip_reset, keep_auto_calibration) from global settings."""
        try:
            s = self._settings.get()
            return bool(s.skip_reset), bool(s.keep_auto_calibration)
        except Exception:  # noqa: BLE001
            return False, False

    def _on_insert_sample(self, setup_id: int) -> None:
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            var_names = list(
                setup_to_config_dict(setup).get("display_vars", [])
            ) or ["V1", "I1"]
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

    # ── Import Measure (external data files → setup + runs) ──────────────────

    def _on_import_measure(self) -> None:
        # As with create, the dialog drives the save via on_submit so the
        # per-file validation report is shown inside the still-open modal.
        dlg = ImportMeasureDialog(
            parent=self._view,
            on_submit=self._import_measure_files,
        )
        dlg.exec()

    def _import_measure_files(
        self,
        name: str,
        description: str,
        paths: list[str],
        options: CsvOptions,
    ) -> Optional[str]:
        """Validate + persist an import; error string keeps the modal open."""
        db = self._projects.current_db
        if db is None:
            return "Open or create a project first."
        with db.session() as s:
            if SetupRepository.name_exists(s, name):
                return f"A setup named '{name}' already exists."
            taken = {
                stem
                for stem in (Path(p).stem for p in paths)
                if ExecutionRepository.name_exists(s, stem)
            }
        result = parse_import_files(paths, options, taken_names=taken)
        if not result.all_ok:
            return self._format_import_errors(result)

        settings = self._settings.get()
        new_id: Optional[int] = None
        try:
            # One session ⇒ one transaction: either the setup and every file's
            # execution land together, or nothing is saved.
            with db.session() as s:
                setup = config_dict_to_setup(
                    {
                        "mode": "IMPORT",
                        "display_vars": list(result.variables),
                    },
                    name=name,
                    description=description or None,
                    author=settings.author or None,
                    organization=settings.organization or None,
                    instrument_model=_IMPORT_INSTRUMENT,
                )
                SetupRepository.add(s, setup)
                for file in result.files:
                    execution = fetch_result_to_execution(
                        file.data,
                        setup=setup,
                        name=file.stem,
                        instrument_model=_IMPORT_INSTRUMENT,
                        is_synthetic=True,
                    )
                    ExecutionRepository.add(s, execution)
                new_id = setup.id
        except IntegrityError:
            return "A setup or run with one of these names already exists."
        self._refresh(select_setup_id=new_id)
        return None

    def _on_import_execution(self, setup_id: int) -> None:
        """Import CSV files as runs of the selected (existing) setup."""
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            setup_name = setup.name
            expected = [
                str(v)
                for v in setup_to_config_dict(setup).get("display_vars", [])
            ]
            suggested = self._unique_exec_name(
                s, setup_name, suffix="import"
            )
        if not expected:
            self._view.display_error(
                tr_ui(CommandWizardText.RUNS_IMPORT_EXEC_NO_VARS)
            )
            return
        dlg = ImportMeasureDialog(
            parent=self._view,
            on_submit=lambda name, desc, paths, options: (
                self._import_execution_files(
                    setup_id, expected, name, desc, paths, options
                )
            ),
            title=tr_ui(CommandWizardText.RUNS_IMPORT_EXEC_TITLE).format(
                setup=setup_name
            ),
            name_label=tr_ui(CommandWizardText.RUNS_IMPORT_EXEC_NAME_LABEL),
            name_placeholder=tr_ui(
                CommandWizardText.RUNS_IMPORT_EXEC_NAME_PLACEHOLDER
            ),
            suggested_name=suggested,
            hint=tr_ui(CommandWizardText.RUNS_IMPORT_EXEC_HINT).format(
                vars=", ".join(expected)
            ),
            name_for_single_file=True,
        )
        dlg.exec()

    def _import_execution_files(
        self,
        setup_id: int,
        expected: list[str],
        name: str,
        description: str,
        paths: list[str],
        options: CsvOptions,
    ) -> Optional[str]:
        """Validate + persist runs into *setup_id*; error keeps modal open."""
        db = self._projects.current_db
        if db is None:
            return "Open or create a project first."
        single_name = name if len(paths) == 1 and name else None
        with db.session() as s:
            if single_name and ExecutionRepository.name_exists(
                s, single_name
            ):
                return f"A run named '{single_name}' already exists."
            taken = ()
            if single_name is None:
                taken = {
                    stem
                    for stem in (Path(p).stem for p in paths)
                    if ExecutionRepository.name_exists(s, stem)
                }
        result = parse_import_files(
            paths, options, taken_names=taken, expected_variables=expected
        )
        if not result.all_ok:
            return self._format_import_errors(result)
        try:
            with db.session() as s:
                setup = SetupRepository.get(s, setup_id)
                if setup is None:
                    return "The selected setup no longer exists."
                for file in result.files:
                    execution = fetch_result_to_execution(
                        file.data,
                        setup=setup,
                        name=single_name or file.stem,
                        description=description or None,
                        instrument_model=_IMPORT_INSTRUMENT,
                        is_synthetic=True,
                    )
                    ExecutionRepository.add(s, execution)
        except IntegrityError:
            return "A run with one of these names already exists."
        self._refresh(select_setup_id=setup_id)
        return None

    @staticmethod
    def _format_import_errors(result: ImportResult) -> str:
        lines = [tr_ui(CommandWizardText.RUNS_IMPORT_ERR_HEADER)]
        lines += [
            f"• {file.stem}: {file.error}"
            for file in result.files
            if file.error
        ]
        if result.variables:
            lines.append(
                tr_ui(
                    CommandWizardText.RUNS_IMPORT_ERR_STANDARD_VARS
                ).format(vars=", ".join(result.variables))
            )
        else:
            lines.append(
                tr_ui(CommandWizardText.RUNS_IMPORT_ERR_NO_STANDARD)
            )
        return "\n".join(lines)

    def _on_view_data(self, execution_id: int) -> None:
        if self._current_setup_id is None:
            return
        # Hand the ids to the Table page; it owns the single load/resolve path.
        self.view_execution_requested.emit(
            self._current_setup_id, execution_id
        )

    # ── Hardware run (selected setup) ────────────────────────────────────────

    def _on_apply_setup(self, setup_id: int) -> None:
        """Send the selected setup to the instrument only — no DB write."""
        if not self._confirm_instrument_match(setup_id):
            return
        config = self._config_for(setup_id)
        if config is None or config.get("mode") == "IMPORT":
            # Imported setups have no instrument configuration; the view keeps
            # the button disabled, this is a belt-and-suspenders guard.
            return
        skip_reset, keep_auto_cal = self._reset_flags()
        setup_cmds = self._setup_director.build_full_setup(
            config,
            skip_reset=skip_reset,
            keep_auto_calibration=keep_auto_cal,
        )
        self._connector.trigger_setup_only(setup_cmds)

    def _on_apply_run_fetch(self, setup_id: int) -> None:
        """Prompt for the execution name/description, then run the sequence."""
        if not self._confirm_instrument_match(setup_id):
            return
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
        if config is None or config.get("mode") == "IMPORT":
            return
        skip_reset, keep_auto_cal = self._reset_flags()
        setup_cmds = self._setup_director.build_full_setup(
            config,
            skip_reset=skip_reset,
            keep_auto_calibration=keep_auto_cal,
        )
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
                # The execution records the connected instrument, not the
                # setup's defined model (they may differ).
                instrument_model=self._connected_model
                or setup.instrument_model,
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

    def _on_connection_changed(self, connected: bool, name: str) -> None:
        self._connected = connected
        # The connector label is "<model> - <resource>"; keep just the model so
        # an execution records the *actively connected* instrument (which may
        # differ from the setup's defined instrument).
        if connected and name:
            self._connected_model = (
                name.split(" - ", maxsplit=1)[0].strip() or name
            )
        else:
            self._connected_model = None
        self._push_hardware_state()

    def _on_hardware_busy(self, busy: bool) -> None:
        self._busy = busy
        self._push_hardware_state()

    def _on_copy_to_config(self, setup_id: int) -> None:
        """Reconstruct a channels layout + params from a setup and hand them
        to MainWindow so it can open a fresh (preloaded) config page."""
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return
            config_dict = setup_to_config_dict(setup)
            channels_config = channels_config_from_setup(
                config_dict,
                instrument_model=setup.instrument_model,
                interlock_open=setup.interlock_open,
                common_to_ground=setup.common_to_ground,
            )
        self.copy_to_config_requested.emit(channels_config, config_dict)

    def _config_for(self, setup_id: int) -> Optional[dict]:
        db = self._projects.current_db
        if db is None:
            return None
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            if setup is None:
                return None
            return setup_to_config_dict(setup)

    def _setup_model(self, setup_id: int) -> Optional[str]:
        db = self._projects.current_db
        if db is None:
            return None
        with db.session() as s:
            setup = SetupRepository.get(s, setup_id)
            return setup.instrument_model if setup else None

    def _confirm_instrument_match(self, setup_id: int) -> bool:
        """Warn (once per session) before running a setup on a foreign model.

        Returns True to proceed. No prompt when suppressed, when disconnected,
        or when the connected model matches the setup's instrument (A-series
        instruments match their B-series equivalent).
        """
        if self._suppress_instrument_mismatch:
            return True
        connected = self._connected_model
        setup_model = self._setup_model(setup_id)
        if (
            not connected
            or not setup_model
            or normalize_instrument_model(setup_model)
            == normalize_instrument_model(connected)
        ):
            return True
        proceed, dont_ask = self._view.confirm_instrument_mismatch(
            setup_model, connected
        )
        if proceed and dont_ask:
            self._suppress_instrument_mismatch = True
        return proceed

    def _push_hardware_state(self) -> None:
        # Connection/run state is surfaced by the global connector widget, so
        # this page only gates its Apply buttons on hardware readiness.
        self._view.set_hardware_ready(self._connected and not self._busy)

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
                out[name] = (
                    np.sin(x * np.pi) * (i + 1) + x * (i + 1)
                ).tolist()
        return out

    @staticmethod
    def _unique_exec_name(session, base: str, suffix: str = "sample") -> str:
        k = 1
        while True:
            candidate = f"{base}-{suffix}-{k}"
            if not ExecutionRepository.name_exists(session, candidate):
                return candidate
            k += 1
