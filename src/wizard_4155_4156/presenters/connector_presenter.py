"""
presenters/connector_presenter.py
----------------------------------
Presenter for the GPIB connection workflow.

MVP responsibilities
--------------------
Model ownership
  - Instantiates and owns the single GPIB41xxController instance.
  - Owns the QThreadPool and enforces the FIFO single-thread constraint.

View mediation
  - Subscribes to CompactConnectorWidget user-intent signals.
  - Calls CompactConnectorWidget.display_* methods to push state updates.
  - Never accesses widget internals (labels, progress bars) directly.

Application signals
  - data_ready(dict)    — forwarded from DataFetchTask; MainWindow connects
                          this to switch to the graph/table pages.
  - hardware_busy(bool) — emitted at start/end of every trigger_* sequence;
                          MainWindow uses this to lock the status indicator
                          and ConnectionTopBar system-status pill.

Public trigger API
------------------
trigger_setup_only(setup_cmds)
trigger_run_only(run_cmds, fetch_cmds)
trigger_full_sequence(setup_cmds, run_cmds, fetch_cmds)

  These are called by future measurement presenters (e.g.
  MeasurementsPresenter) via a reference to this presenter.  They enqueue
  tasks onto the FIFO pool and emit hardware_busy(True) immediately.

  CRITICAL: Tasks are submitted in strict submission order.  The pool's
  single-thread constraint guarantees they execute in that order with no
  overlap, preserving the instrument state machine.

Lifecycle
---------
  start()   — trigger initial auto-scan after signal wiring is complete.
  cleanup() — drain and clear the pool; called from MainWindow.closeEvent().
"""
from typing import List

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from wizard_4155_4156.gpib.controller import GPIB41xxController
from wizard_4155_4156.gpib.workers import (
    ConnectTask,
    DataFetchTask,
    DisconnectTask,
    MeasurementRunTask,
    ScanTask,
    SetupTask,
)
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.gui_text.log_messages import LogMsg
from wizard_4155_4156.SCPI.base_director import CommandPair
from wizard_4155_4156.views.connector_widget import CompactConnectorWidget

# Union of all task types accepted by _wire_task
_AnyTask = (
    ScanTask | ConnectTask | DisconnectTask |
    SetupTask | MeasurementRunTask | DataFetchTask
)


class ConnectorPresenter(QObject):
    """
    Presenter: mediates between CompactConnectorWidget (View) and
    GPIB41xxController (Model).
    """

    # ── Application-level signals (consumed by MainWindow) ───────────────────
    data_ready = Signal(dict)     # forwarded from DataFetchTask.data_fetched
    hardware_busy = Signal(bool)  # True when any trigger_* sequence is active

    def __init__(
        self,
        view: CompactConnectorWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._view = view

        # ── Model: single shared controller instance ───────────────────────
        self._controller = GPIB41xxController()

        # ── FIFO thread pool: exactly one thread ───────────────────────────
        # ! CRITICAL: maxThreadCount=1 is the sole mechanism guaranteeing
        # ! sequential, non-concurrent GPIB I/O.  Do not increase this value.
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(1)

        self._connect_view_signals()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Initiate the initial bus scan.  Call this after constructing the
        presenter and connecting its output signals (data_ready, hardware_busy)
        to MainWindow slots — scanning before wiring would silently drop
        scan_results if nothing is connected yet.
        """
        self._scan_bus()

    def cleanup(self) -> None:
        """
        Drain pending tasks and wait for the active task to finish.
        Must be called from MainWindow.closeEvent() before the event is
        accepted to prevent tasks from accessing destroyed objects.
        """
        self._pool.clear()
        self._pool.waitForDone(3_000)   # 3 s grace period

    # ── Public trigger API (called by future measurement presenters) ─────────

    def trigger_setup_only(self, setup_cmds: List[CommandPair]) -> None:
        """Queue instrument configuration only."""
        self.hardware_busy.emit(True)
        task = self._wire_task(SetupTask(self._controller, setup_cmds))
        task.signals.finished_setup.connect(self._on_setup_finished)
        self._pool.start(task)

    def trigger_run_only(
        self,
        run_cmds: List[CommandPair],
        fetch_cmds: List[CommandPair],
    ) -> None:
        """Queue measurement execution followed by data extraction."""
        self.hardware_busy.emit(True)
        self.run_task = self._wire_task(
            MeasurementRunTask(self._controller, run_cmds)
        )
        self.fetch_task = self._wire_task(
            DataFetchTask(self._controller, fetch_cmds)
        )
        self.fetch_task.signals.data_fetched.connect(self._on_data_fetched)

        # Submission order == execution order (single-thread FIFO guarantee)
        self.run_task.signals.finished_measurement.connect(
            lambda: self._pool.start(self.fetch_task)
        )
        self._pool.start(self.run_task)

    def trigger_full_sequence(
        self,
        setup_cmds: List[CommandPair],
        run_cmds: List[CommandPair],
        fetch_cmds: List[CommandPair],
    ) -> None:
        """Queue a complete cycle: Setup → Run → Fetch."""
        self.hardware_busy.emit(True)
        self.setup_task = self._wire_task(
            SetupTask(self._controller, setup_cmds)
        )
        self.run_task = self._wire_task(
            MeasurementRunTask(self._controller, run_cmds)
        )
        self.fetch_task = self._wire_task(
            DataFetchTask(self._controller, fetch_cmds)
        )
        self.fetch_task.signals.data_fetched.connect(self._on_data_fetched)

        self.setup_task.signals.finished_setup.connect(
            lambda: self._pool.start(self.run_task)
        )
        self.run_task.signals.finished_measurement.connect(
            lambda: self._pool.start(self.fetch_task)
        )
        self._pool.start(self.setup_task)

    # ── Private wiring ───────────────────────────────────────────────────────

    def _connect_view_signals(self) -> None:
        """Subscribe to all user-intent signals on the View."""
        self._view.scan_requested.connect(self._scan_bus)
        self._view.connect_requested.connect(self._connect_to_instrument)
        self._view.disconnect_requested.connect(self._disconnect_bus)

    def _wire_task(self, task: _AnyTask) -> _AnyTask:
        """
        Connect the three universal task signals to their presenter slots.
        Returns the same task instance for chaining.
        """
        task.signals.log_msg.connect(self._view.modal.append_log)
        task.signals.progress_update.connect(self._on_progress_update)
        task.signals.worker_error.connect(self._on_worker_error)
        return task

    # ── Connection task dispatchers ──────────────────────────────────────────

    def _scan_bus(self) -> None:
        task = self._wire_task(ScanTask(self._controller))
        task.signals.scan_results.connect(self._on_scan_results)
        self._pool.start(task)

    def _connect_to_instrument(self, address: str, name: str) -> None:
        task = self._wire_task(ConnectTask(self._controller, address, name))
        task.signals.connection_status.connect(self._on_connection_status)
        self._pool.start(task)

    def _disconnect_bus(self) -> None:
        task = self._wire_task(DisconnectTask(self._controller))
        task.signals.connection_status.connect(self._on_connection_status)
        self._pool.start(task)

    # ── Slot handlers ────────────────────────────────────────────────────────

    @Slot()
    def _on_setup_finished(self) -> None:
        self.hardware_busy.emit(False)
        self._view.display_status(tr_ui(CommandWizardText.STATUS_IDLE))

    @Slot(dict)
    def _on_data_fetched(self, data: dict) -> None:
        self.hardware_busy.emit(False)
        self.data_ready.emit(data)

    @Slot(dict)
    def _on_scan_results(self, results: dict) -> None:
        self._view.modal.update_scan_results(results)
        if not results:
            self._view.display_scan_no_found()

    @Slot(bool, str)
    def _on_connection_status(self, connected: bool, name: str) -> None:
        self._view.modal.update_connection_status(connected)
        if connected:
            self._view.display_connected(name)
        else:
            self._view.display_disconnected()

    @Slot(int, int, str)
    def _on_progress_update(
        self, current: int, total: int, status: str
    ) -> None:
        self._view.display_progress(current, total, status)
        self._view.modal.update_progress(current, total, status)

    @Slot(str)
    def _on_worker_error(self, err_msg: str) -> None:
        # ! CRITICAL: clear the pool immediately.  Without this, tasks queued
        # ! after a failed Setup (e.g. Run, Fetch) would execute blindly on an
        # ! improperly configured instrument, producing undefined hardware
        # ! state.
        self._pool.clear()
        self.hardware_busy.emit(False)
        self._view.display_error(
            tr_ui(CommandWizardText.HARDWARE_ERROR_ALERT)
        )
        self._view.modal.append_log(LogMsg.WORKER_ERROR.format(error=err_msg))
