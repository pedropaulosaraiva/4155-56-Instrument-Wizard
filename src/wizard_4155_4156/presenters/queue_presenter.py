"""
presenters/queue_presenter.py
-----------------------------
Controller for the measurement queue.

Responsibilities
----------------
- Owns the :class:`MeasurementQueue` (pure model) and the queue panel (view).
- Dispatches one item at a time through :class:`SetupRunService`, which is the
  *same* instance the Runs page uses — so a manual run and a queued run can
  never overlap.
- Translates queue entries into Qt-free ``QueueRow`` DTOs, resolving each
  setup's *current* name from the database so a rename shows through and a
  deletion is marked rather than silently executed.

Coupling
--------
Knows nothing about ``RunsPresenter``.  It talks to a run service, a project
manager, a connector (for the connection state) and its own view.  Adding
another way to enqueue means calling :meth:`enqueue` — nothing else changes.

Threading
---------
Everything here runs on the GUI thread.  Worker signals reach it as queued
connections, so the pump is never entered from a pool thread and no locking is
needed.  The two dispatch hazards are closed structurally:

- *Double dispatch* — :meth:`_pump` is the only place a run is started, it
  refuses to act while an item is RUNNING or the run service is busy, and
  ``MeasurementQueue.mark_running`` independently rejects a second runner.
- *Re-entrancy* — the pump is always invoked deferred through a single-shot
  timer bound to this object, and guarded by ``_pumping``.  It therefore never
  runs inside a terminal slot's call stack (nor after this object is gone).

Failure policy
--------------
- A *data* problem (project closed, setup deleted, imported setup, invalid
  configuration) is reported synchronously by ``SetupRunService.start`` — the
  item is marked FAILED and the queue moves on; the instrument is fine.
- A *hardware* failure (SCPI error, disconnect, aborted chain) arrives later on
  ``run_failed`` — the item is marked FAILED and the whole queue PAUSES until
  the user resumes or clears it.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.execution_time import format_execution_interval
from wizard_4155_4156.models.measurement_queue import (
    MeasurementQueue,
    QueueItem,
    QueueItemStatus,
    QueueRow,
    QueueState,
    positions,
)

_T = CommandWizardText

#: Timestamp format for the "Running · started …" line.
_TIME_FMT = "%H:%M:%S"


class QueuePresenter(QObject):
    """Schedules saved setups and drives them one at a time."""

    #: (active item count, QueueState value) — drives the toolbar badge.
    badge_changed = Signal(int, str)
    #: Transient text for the application status bar.
    status_message = Signal(str)

    def __init__(
        self,
        view,  # QueuePanelDialog
        run_service,  # SetupRunService
        project_manager,  # ProjectManager
        connector_presenter,  # ConnectorPresenter
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._runner = run_service
        self._projects = project_manager
        self._connector = connector_presenter

        self._queue = MeasurementQueue()
        self._paused = False
        self._pause_reason = ""
        self._notice = ""
        self._pumping = False
        self._active = True  # cleared by shutdown()

        self._connect()
        self._refresh()

    # ── Wiring ───────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        v = self._view
        v.remove_requested.connect(self._on_remove)
        v.move_requested.connect(self._on_move)
        v.clear_requested.connect(self._on_clear)
        v.clear_finished_requested.connect(self._on_clear_finished)
        v.pause_requested.connect(self._on_pause)
        v.resume_requested.connect(self._on_resume)

        self._runner.run_succeeded.connect(self._on_run_succeeded)
        self._runner.run_failed.connect(self._on_run_failed)
        self._connector.connection_changed.connect(
            self._on_connection_changed
        )
        # The bus going idle is the general "you may dispatch now" event.  It
        # covers work the queue knows nothing about — a manual Runs-page run,
        # or a quick apply/run from a config page — which otherwise would free
        # the instrument without ever waking the pump.
        self._connector.hardware_busy.connect(self._on_hardware_busy)

    # ── Public API ───────────────────────────────────────────────────────────

    def enqueue(
        self,
        setup_id: int,
        setup_name: str,
        run_name: str,
        description: str = "",
        runtime_bounds: Optional[tuple] = None,
        allow_mismatch: bool = False,
    ) -> None:
        """Append a setup to the queue and start it when the bus frees up."""
        item = self._queue.add(
            QueueItem(
                setup_id=setup_id,
                setup_name=setup_name,
                run_name=run_name,
                description=description,
                runtime_bounds=runtime_bounds,
                allow_mismatch=allow_mismatch,
            )
        )
        self.status_message.emit(
            tr_ui(_T.QUEUE_MSG_ENQUEUED).format(
                name=item.run_name or setup_name,
                count=self._queue.waiting_count,
            )
        )
        self._refresh()
        self._schedule_pump()

    def proposed_run_name(self, setup_id: int) -> Optional[str]:
        """A run name free in the database *and* not claimed by the queue."""
        return self._runner.default_run_name(
            setup_id, self._queue.reserved_names()
        )

    def open_panel(self) -> None:
        """Show the queue window and bring it forward (restoring if minimised).

        It is an independent top-level window, so it may be sitting minimised
        in the taskbar — the view's ``present`` handles that case.
        """
        self._refresh()
        self._view.present()

    def has_active_work(self) -> bool:
        """Whether a run is executing or entries are still waiting."""
        return self._queue.active_count > 0 or self._runner.owns_run

    def quit_detail(self) -> str:
        """One line describing what quitting now would interrupt."""
        waiting = self._queue.waiting_count
        running = self._queue.running is not None or self._runner.owns_run
        if running and waiting:
            return tr_ui(_T.QUEUE_QUIT_BOTH).format(count=waiting)
        if running:
            return tr_ui(_T.QUEUE_QUIT_RUNNING)
        return tr_ui(_T.QUEUE_QUIT_WAITING).format(count=waiting)

    def on_project_changed(self) -> None:
        """Discard the whole queue — a new project is being activated.

        Queued entries reference setups of the project being replaced, so they
        must never execute or be persisted.  A measurement already on the bus
        cannot be recalled; it is dropped from the queue here and its result is
        discarded by ``SetupRunService`` (which compares the project database
        by identity before writing).
        """
        dropped = self._queue.clear_all()
        self._paused = False
        self._pause_reason = ""
        self._notice = ""
        if dropped:
            self.status_message.emit(
                tr_ui(_T.QUEUE_MSG_DROPPED).format(count=dropped)
            )
        self._refresh()

    def shutdown(self) -> None:
        """Detach before teardown so no deferred pump reaches a dead object."""
        self._active = False
        self._queue.clear_all()
        for signal, slot in (
            (self._runner.run_succeeded, self._on_run_succeeded),
            (self._runner.run_failed, self._on_run_failed),
            (self._connector.connection_changed, self._on_connection_changed),
            (self._connector.hardware_busy, self._on_hardware_busy),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                # Already disconnected (or the emitter is gone) — no-op.
                pass
        self._view.close()

    # ── The pump — the ONLY place a queued run is dispatched ─────────────────

    def _schedule_pump(self) -> None:
        # `self` as the context object: the callback is dropped if this
        # presenter is destroyed before the event loop gets back to it.
        QTimer.singleShot(0, self, self._pump)

    @Slot()
    def _pump(self) -> None:
        if not self._active or self._pumping:
            return
        self._pumping = True
        try:
            self._dispatch_next()
        finally:
            self._pumping = False
        self._refresh()

    def _can_dispatch(self) -> bool:
        """Whether the instrument and the project are free for the next item.

        - ``_paused``      — halted after a failure, or by the user.
        - ``running``      — a queued item is already on the bus.
        - ``is_busy``      — a manual or quick run holds the instrument.
        - ``current_db``   — no project: nothing to resolve or persist into.
        """
        return not (
            self._paused
            or self._queue.running is not None
            or self._runner.is_busy
            or self._projects.current_db is None
        )

    def _dispatch_next(self) -> None:
        if not self._can_dispatch():
            return
        item = self._queue.next_waiting()
        if item is None:
            return
        if not self._connector.is_connected():
            self._pause(tr_ui(_T.QUEUE_PAUSE_DISCONNECTED))
            return

        error = self._runner.start(
            item.setup_id, item.run_name, item.description
        )
        if error is None:
            self._queue.mark_running(item.uid)
            return
        # A data problem: the instrument is untouched, so drop this entry and
        # keep the batch moving instead of stalling on it.
        self._queue.mark_failed(item.uid, error)
        self._notice = tr_ui(_T.QUEUE_NOTICE_SKIPPED).format(
            name=item.run_name or item.setup_name, error=error
        )
        self.status_message.emit(self._notice)
        self._schedule_pump()

    # ── Run outcomes ─────────────────────────────────────────────────────────

    @Slot(bool)
    def _on_hardware_busy(self, busy: bool) -> None:
        if not busy:
            self._schedule_pump()

    @Slot(int, int, str)
    def _on_run_succeeded(
        self, _setup_id: int, execution_id: int, exec_name: str
    ) -> None:
        running = self._queue.running
        if running is None:
            # The completed run came from the Runs page, not the queue.  The
            # bus is free either way, so let the pump have a look.
            self._schedule_pump()
            return
        running.run_name = exec_name  # the name actually persisted
        self._queue.mark_done(running.uid, execution_id)
        if self._queue.waiting_count == 0:
            self.status_message.emit(
                tr_ui(_T.QUEUE_MSG_FINISHED).format(
                    done=self._queue.done_count
                )
            )
        self._refresh()
        self._schedule_pump()

    @Slot(int, str)
    def _on_run_failed(self, _setup_id: int, reason: str) -> None:
        running = self._queue.running
        if running is None:
            # A Runs-page run failed; the queue was not involved, so it is not
            # paused on its account.  If the instrument really is unwell, the
            # next queued item will fail on its own and pause then — with a
            # reason that actually belongs to the queue.
            self._schedule_pump()
            return
        self._queue.mark_failed(running.uid, reason)
        # Hardware-side failure: stop the batch rather than push more work at
        # an instrument in an unknown state.
        self._pause(tr_ui(_T.QUEUE_PAUSE_ERROR))
        self._notice = tr_ui(_T.QUEUE_NOTICE_PAUSED_ERROR).format(error=reason)
        self.status_message.emit(self._notice)
        self._refresh()

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, _name: str) -> None:
        if not connected:
            if self._queue.active_count:
                self._pause(tr_ui(_T.QUEUE_PAUSE_DISCONNECTED))
                self._refresh()
            return
        # Reconnected: stay paused deliberately — the physical setup may have
        # been touched while the instrument was off the bus.
        if self._paused and self._queue.waiting_count:
            self._notice = tr_ui(_T.QUEUE_NOTICE_RECONNECTED)
            self._refresh()

    # ── View slots ───────────────────────────────────────────────────────────

    @Slot(str)
    def _on_remove(self, uid: str) -> None:
        self._queue.remove(uid)
        self._refresh()

    @Slot(str, int)
    def _on_move(self, uid: str, delta: int) -> None:
        self._queue.move(uid, delta)
        self._refresh()

    @Slot()
    def _on_clear(self) -> None:
        self._queue.clear_waiting()
        self._refresh()

    @Slot()
    def _on_clear_finished(self) -> None:
        self._queue.clear_finished()
        self._refresh()

    @Slot()
    def _on_pause(self) -> None:
        self._pause(tr_ui(_T.QUEUE_PAUSE_USER))
        self._refresh()

    @Slot()
    def _on_resume(self) -> None:
        self._paused = False
        self._pause_reason = ""
        self._notice = ""
        self._refresh()
        self._schedule_pump()

    # ── State push ───────────────────────────────────────────────────────────

    def _pause(self, reason: str) -> None:
        self._paused = True
        self._pause_reason = reason

    def _refresh(self) -> None:
        """Rebuild the rows and push queue state to the view and the badge."""
        rows = self._build_rows()
        state = self._queue.state(paused=self._paused)
        self._view.display_items(rows)
        self._view.display_state(
            str(state), self._state_text(state), self._paused
        )
        self._view.display_notice(self._notice)
        self.badge_changed.emit(self._queue.active_count, str(state))

    def _state_text(self, state: QueueState) -> str:
        if state is QueueState.PAUSED:
            return tr_ui(_T.QUEUE_STATE_PAUSED).format(
                reason=self._pause_reason
            )
        if state is QueueState.RUNNING:
            return tr_ui(_T.QUEUE_STATE_RUNNING).format(
                done=self._queue.done_count,
                total=self._queue.done_count + self._queue.active_count,
            )
        if state is QueueState.PENDING:
            return tr_ui(_T.QUEUE_STATE_PENDING).format(
                waiting=self._queue.waiting_count
            )
        return tr_ui(_T.QUEUE_STATE_IDLE)

    def _build_rows(self) -> List[QueueRow]:
        items = self._queue.items()
        slots = positions(items)
        waiting = [i for i in items if i.is_waiting]
        first_waiting = waiting[0].uid if waiting else None
        last_waiting = waiting[-1].uid if waiting else None
        # One database round trip for the whole panel, not one per row.
        names = self._runner.setup_names(i.setup_id for i in items)
        return [
            QueueRow(
                uid=item.uid,
                position=slot,
                setup_label=self._setup_label(item, names),
                run_name=item.run_name,
                runtime_label=format_execution_interval(item.runtime_bounds),
                status=item.status,
                status_text=self._status_text(item),
                can_edit=item.is_waiting,
                can_move_up=item.is_waiting and item.uid != first_waiting,
                can_move_down=item.is_waiting and item.uid != last_waiting,
            )
            for item, slot in zip(items, slots)
        ]

    @staticmethod
    def _setup_label(item: QueueItem, names: dict) -> str:
        """Live setup name, or the enqueue-time snapshot marked as deleted.

        Resolved on every refresh so a setup renamed after being queued shows
        its current name — the queue tracks setups by id, never by name.
        """
        current = names.get(item.setup_id)
        if current:
            return current
        return tr_ui(_T.QUEUE_SETUP_DELETED).format(name=item.setup_name)

    @staticmethod
    def _status_text(item: QueueItem) -> str:
        if item.status is QueueItemStatus.RUNNING:
            stamp = (
                item.started_at.strftime(_TIME_FMT) if item.started_at else "—"
            )
            return tr_ui(_T.QUEUE_STATUS_RUNNING).format(time=stamp)
        if item.status is QueueItemStatus.DONE:
            return tr_ui(_T.QUEUE_STATUS_DONE).format(name=item.run_name)
        if item.status is QueueItemStatus.FAILED:
            return tr_ui(_T.QUEUE_STATUS_FAILED).format(error=item.error)
        return tr_ui(_T.QUEUE_STATUS_WAITING)
