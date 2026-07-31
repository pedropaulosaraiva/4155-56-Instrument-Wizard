"""
presenters/setup_run_service.py
-------------------------------
The single arbiter for "execute a saved setup and persist the result".

Why this exists
---------------
Two callers need that behavior: the Runs page (user clicks *Apply Setup and
Run*) and the measurement queue (batch execution).  Both must share **one**
state machine, because :meth:`ConnectorPresenter.trigger_full_sequence` is not
re-entrant — it stores the three tasks on the presenter and chains them with
lambdas that re-read those attributes when the finished signals fire, so a
second overlapping call would make the first chain start the second run task.
Routing every persisted run through this service guarantees at most one
sequence is ever in flight, and that a fetched dataset is written exactly once
no matter who asked for it.

Layer contract
--------------
Presenter layer: may touch Qt and the ORM.  All database writes happen on the
GUI thread inside this object — no ``Session`` is ever handed to a GPIB worker.

Terminal events
---------------
``data_ready`` and ``sequence_failed`` on the connector are the two terminal
outcomes of a triggered sequence.  Both consume the pending record first, so a
failed run can never leave the service armed to adopt an unrelated later fetch.

Project safety
--------------
The pending record captures the ``ProjectDatabase`` that owns the run.  If the
user opens another project while a measurement is on the bus, the returning
data is compared against the *current* database by identity and discarded
rather than written into the wrong project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Set

from PySide6.QtCore import QObject, Signal, Slot

from wizard_4155_4156.db.assembler import (
    fetch_result_to_execution,
    setup_to_config_dict,
)
from wizard_4155_4156.db.repository import ExecutionRepository, SetupRepository
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.SCPI.measurement_run_director import (
    MeasurementRunDirector,
)
from wizard_4155_4156.SCPI.measurement_setup_director import (
    MeasurementSetupDirector,
)

_T = CommandWizardText

# Trace-fetch defaults
# (mirror LiveMeasurementRunner / MeasureRunCommandBuilder).
_FETCH_FORMAT = "REAL"
_FETCH_LENGTH = 64
_FETCH_BORDER = "NORM"

#: Suffix used when an execution name has to be auto-generated.
_RUN_SUFFIX = "run"


@dataclass
class _Pending:
    """The run currently on the bus, staged for persistence on return."""

    setup_id: int
    name: Optional[str]
    description: Optional[str]
    #: Identity of the project database that owns this run.  Compared with
    #: ``is`` on return — a switched project must not inherit the result.
    db: object


class SetupRunService(QObject):
    """Runs a persisted setup on the instrument and stores the execution."""

    #: A sequence was handed to the instrument.
    run_started = Signal(int)  # setup_id
    #: Data came back and was persisted: (setup_id, execution_id, exec_name).
    run_succeeded = Signal(int, int, str)
    #: The sequence aborted on the instrument: (setup_id, reason).  Only
    #: hardware failures arrive here — configuration/data problems are
    #: reported synchronously as the return value of :meth:`start`.
    run_failed = Signal(int, str)
    #: True while this service owns an in-flight sequence.
    busy_changed = Signal(bool)

    def __init__(
        self,
        project_manager,  # ProjectManager
        settings_manager,  # GlobalSettingsManager
        connector_presenter,  # ConnectorPresenter
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._projects = project_manager
        self._settings = settings_manager
        self._connector = connector_presenter
        self._setup_director = MeasurementSetupDirector()
        self._run_director = MeasurementRunDirector()

        self._pending: Optional[_Pending] = None
        # Hardware may also be busy with a *quick* run started from a config
        # page (which never sets ``_pending``); track it so callers asking
        # "can I start now?" get the whole truth, not just our own runs.
        self._hardware_busy = False
        self._connected_model: Optional[str] = None

        connector_presenter.data_ready.connect(self._on_data_ready)
        connector_presenter.sequence_failed.connect(self._on_sequence_failed)
        connector_presenter.hardware_busy.connect(self._on_hardware_busy)
        connector_presenter.connection_changed.connect(
            self._on_connection_changed
        )

    # ── State ────────────────────────────────────────────────────────────────

    @property
    def is_busy(self) -> bool:
        """Whether any sequence (ours or a quick run) is on the bus."""
        return self._pending is not None or self._hardware_busy

    @property
    def owns_run(self) -> bool:
        """Whether the in-flight sequence is one this service will persist."""
        return self._pending is not None

    @property
    def connected_model(self) -> Optional[str]:
        """Model of the connected instrument, or None when offline."""
        return self._connected_model

    # ── Public API ───────────────────────────────────────────────────────────

    def apply_setup_only(self, setup_id: int) -> Optional[str]:
        """Send a setup's configuration to the instrument; no run, no write.

        Returns an error message, or ``None`` when the commands were queued.
        """
        config, error = self._runnable_config(setup_id)
        if error is not None:
            return error
        try:
            setup_cmds = self._build_setup_commands(config)
        except Exception as exc:  # noqa: BLE001 — surfaced to the user
            return tr_ui(_T.RUN_ERR_BUILD_FAILED).format(error=exc)
        self._connector.trigger_setup_only(setup_cmds)
        return None

    def start(
        self,
        setup_id: int,
        name: Optional[str],
        description: Optional[str],
    ) -> Optional[str]:
        """Run ``setup_id`` end to end (Setup → Run → Fetch) and persist it.

        Returns ``None`` once the sequence is on its way, or an error message
        describing a *data* problem (no project, setup gone, imported setup,
        invalid configuration, hardware already busy).  Hardware failures are
        not reported here — they arrive later on :attr:`run_failed`.
        """
        if self.is_busy:
            return tr_ui(_T.RUN_ERR_BUSY)
        config, error = self._runnable_config(setup_id)
        if error is not None:
            return error
        db = self._projects.current_db
        try:
            setup_cmds = self._build_setup_commands(config)
            run_cmds = self._run_director.run_measurement({"standby": "OFF"})
            fetch_cmds = self._run_director.take_data(
                self._fetch_config(config)
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to the user
            return tr_ui(_T.RUN_ERR_BUILD_FAILED).format(error=exc)

        # Arm BEFORE triggering: the connector may emit synchronously in tests.
        self._pending = _Pending(setup_id, name, description, db)
        self.busy_changed.emit(True)
        self.run_started.emit(setup_id)
        try:
            self._connector.trigger_full_sequence(
                setup_cmds, run_cmds, fetch_cmds
            )
        except Exception as exc:  # noqa: BLE001 — never leave the service armed
            self._pending = None
            self.busy_changed.emit(False)
            return tr_ui(_T.RUN_ERR_BUILD_FAILED).format(error=exc)
        return None

    def default_run_name(
        self, setup_id: int, reserved: Optional[Set[str]] = None
    ) -> Optional[str]:
        """A unique execution name for ``setup_id``, or None if it is gone.

        ``reserved`` holds names already claimed by callers that have not
        written to the database yet (queued items), so repeatedly queuing the
        same setup proposes a different name each time.

        The run **currently on the bus** is added to that set here rather than
        by the caller: its name was chosen when it started but is only written
        once the data comes back, so it exists in neither the database nor the
        queue.  Without it, queuing a setup while the same setup is running
        would propose the name the running one already took, and the queued
        execution would be silently renamed at persist time.
        """
        db = self._projects.current_db
        if db is None:
            return None
        claimed = set(reserved or ())
        if self._pending is not None and self._pending.name:
            claimed.add(self._pending.name)
        with db.session() as session:
            setup = SetupRepository.get(session, setup_id)
            if setup is None:
                return None
            return self._unique_exec_name(session, setup.name, claimed)

    def setup_names(self, setup_ids: Iterable[int]) -> dict[int, str]:
        """Current names of ``setup_ids``; missing ids are simply absent.

        Resolved in one session for the whole batch — the queue panel redraws
        every row on each refresh, and a session per row would be a needless
        N+1 against the project database.
        """
        db = self._projects.current_db
        if db is None:
            return {}
        names: dict[int, str] = {}
        with db.session() as session:
            for setup_id in set(setup_ids):
                setup = SetupRepository.get(session, setup_id)
                if setup is not None:
                    names[setup_id] = setup.name
        return names

    # ── Terminal handlers ────────────────────────────────────────────────────

    @Slot(dict)
    def _on_data_ready(self, data: dict) -> None:
        """A fetch returned — persist it iff *this service* staged the run."""
        pending, self._pending = self._pending, None
        if pending is None:
            # A quick run from a config page: shown live, never persisted.
            return
        self.busy_changed.emit(False)
        if self._projects.current_db is not pending.db:
            # The project was swapped while the instrument was measuring.
            # Writing into the new project would silently mix data sets.
            self.run_failed.emit(
                pending.setup_id, tr_ui(_T.RUN_ERR_PROJECT_CHANGED)
            )
            return
        if not data:
            self.run_failed.emit(
                pending.setup_id, tr_ui(_T.RUN_ERR_NO_DATA)
            )
            return
        try:
            execution_id, exec_name = self._persist(pending, data)
        except Exception as exc:  # noqa: BLE001 — a write must not kill a batch
            self.run_failed.emit(
                pending.setup_id,
                tr_ui(_T.RUN_ERR_SAVE_FAILED).format(error=exc),
            )
            return
        if execution_id is None:
            self.run_failed.emit(
                pending.setup_id, tr_ui(_T.RUN_ERR_SETUP_GONE)
            )
            return
        self.run_succeeded.emit(pending.setup_id, execution_id, exec_name)

    @Slot(str)
    def _on_sequence_failed(self, message: str) -> None:
        """The chain aborted — disarm so no later fetch is adopted."""
        pending, self._pending = self._pending, None
        if pending is None:
            return
        self.busy_changed.emit(False)
        self.run_failed.emit(pending.setup_id, message)

    @Slot(bool)
    def _on_hardware_busy(self, busy: bool) -> None:
        self._hardware_busy = busy

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, name: str) -> None:
        # The connector label is "<model> - <resource>"; keep just the model so
        # an execution records the actively connected instrument.
        if connected and name:
            self._connected_model = (
                name.split(" - ", maxsplit=1)[0].strip() or name
            )
        else:
            self._connected_model = None

    # ── Persistence ──────────────────────────────────────────────────────────

    def _persist(
        self, pending: _Pending, data: dict
    ) -> tuple[Optional[int], str]:
        db = self._projects.current_db
        if db is None:
            return None, ""
        with db.session() as session:
            setup = SetupRepository.get(session, pending.setup_id)
            if setup is None:
                return None, ""
            # Honor the requested name; fall back to a unique auto-name when it
            # is blank or already taken (execution names are unique per
            # project, so the same setup queued twice cannot reuse one).
            name = pending.name
            if not name or ExecutionRepository.name_exists(session, name):
                name = self._unique_exec_name(session, setup.name, set())
            execution = fetch_result_to_execution(
                data,
                setup=setup,
                name=name,
                description=pending.description or None,
                # The execution records the *connected* instrument, which may
                # differ from the model the setup was defined for.
                instrument_model=self._connected_model
                or setup.instrument_model,
                is_synthetic=False,
            )
            ExecutionRepository.add(session, execution)
            return execution.id, name

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _runnable_config(
        self, setup_id: int
    ) -> tuple[dict, Optional[str]]:
        """Config dict for ``setup_id``, or ``({}, error)`` when unusable."""
        db = self._projects.current_db
        if db is None:
            return {}, tr_ui(_T.RUN_ERR_NO_PROJECT)
        with db.session() as session:
            setup = SetupRepository.get(session, setup_id)
            if setup is None:
                return {}, tr_ui(_T.RUN_ERR_SETUP_GONE)
            config = setup_to_config_dict(setup)
        if config.get("mode") == "IMPORT":
            # Imported setups hold external data only — nothing to send.
            return {}, tr_ui(_T.RUN_ERR_IMPORT)
        return config, None

    def _build_setup_commands(self, config: dict):
        skip_reset, keep_auto_cal = self._reset_flags()
        return self._setup_director.build_full_setup(
            config,
            skip_reset=skip_reset,
            keep_auto_calibration=keep_auto_cal,
        )

    def _reset_flags(self) -> tuple[bool, bool]:
        """(skip_reset, keep_auto_calibration) from global settings."""
        try:
            settings = self._settings.get()
            return bool(settings.skip_reset), bool(
                settings.keep_auto_calibration
            )
        except Exception:  # noqa: BLE001
            return False, False

    @staticmethod
    def _fetch_config(config: dict) -> dict:
        return {
            "format": _FETCH_FORMAT,
            "length": _FETCH_LENGTH,
            "border": _FETCH_BORDER,
            "variables": config.get("display_vars", []),
        }

    @staticmethod
    def _unique_exec_name(session, base: str, reserved: Set[str]) -> str:
        """First ``<base>-run-<k>`` free in the DB and in ``reserved``."""
        k = 1
        while True:
            candidate = f"{base}-{_RUN_SUFFIX}-{k}"
            if candidate not in reserved and not (
                ExecutionRepository.name_exists(session, candidate)
            ):
                return candidate
            k += 1
