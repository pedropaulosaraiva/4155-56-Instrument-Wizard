"""
test/db/test_queue_flow.py
--------------------------
Integration tests for the measurement queue: ``QueuePresenter`` driving the
real ``SetupRunService`` against a real project database.

Only the two ends are faked:

- ``_FakeConnector`` stands in for ``ConnectorPresenter``.  It records each
  triggered sequence instead of talking to GPIB and lets a test decide when
  data comes back (``finish``) or the chain aborts (``fail``), emitting exactly
  the same signals in exactly the same order as the real presenter.
- ``_FakeQueuePanel`` stands in for the dialog, capturing what the view was
  told to display.  No widgets are created, so these run headless.

A ``QCoreApplication`` is required because the pump is dispatched through
``QTimer.singleShot(0, ...)``; ``processEvents()`` is what lets it fire.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional

# Must be set before the first QApplication is constructed.  The widget-level
# regression test below needs a real QApplication; offscreen keeps it headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

from wizard_4155_4156.db.engine import (  # noqa: E402
    PROJECT_EXTENSION,
    ProjectDatabase,
)
from wizard_4155_4156.db.repository import (  # noqa: E402
    ExecutionRepository,
    SetupRepository,
)
from wizard_4155_4156.db.schema import (  # noqa: E402
    MeasurementExecution,
    MeasurementSetup,
)
from wizard_4155_4156.extra_widgets.queue_panel_dialog import (  # noqa: E402
    QueuePanelDialog,
)
from wizard_4155_4156.gui_text.general_text import (  # noqa: E402
    CommandWizardText as _T,
)
from wizard_4155_4156.gui_text.general_text import tr_ui  # noqa: E402
from wizard_4155_4156.models.measurement_queue import (  # noqa: E402
    QueueItemStatus,
    QueueRow,
    QueueState,
)
from wizard_4155_4156.presenters.queue_presenter import (  # noqa: E402
    QueuePresenter,
)
from wizard_4155_4156.presenters.setup_run_service import (  # noqa: E402
    SetupRunService,
)
from wizard_4155_4156.views.pages.runs_page import RunsPageView  # noqa: E402

# A minimal but real sweep config: enough for MeasurementSetupDirector to
# build a genuine command list without any hardware (same shape as the
# director's own tests use).
_SWEEP_CONFIG = {
    "mode": "SWEEP",
    "channels": {"SMU1": {"disable": True}},
    "measurement_setup": {"integration_mode": "SHORT"},
    "sweep_setup": {"delay": 0.1},
    "display_vars": ["V1", "I1"],
}

#: Batch sizes used by the multi-item tests.
_BATCH = 3
_PAIR = 2


# ── Fakes ────────────────────────────────────────────────────────────────────


class _FakeConnector(QObject):
    """Records triggered sequences; a test drives their outcome."""

    data_ready = Signal(dict)
    hardware_busy = Signal(bool)
    connection_changed = Signal(bool, str)
    sequence_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.sequences: List[tuple] = []
        self.setup_only: List[list] = []
        self._connected = True
        #: Sequences triggered but not yet resolved — must never exceed 1.
        self.in_flight = 0
        self.max_in_flight = 0

    # ConnectorPresenter API used by SetupRunService / QueuePresenter
    def is_connected(self) -> bool:
        return self._connected

    def trigger_setup_only(self, setup_cmds) -> None:
        self.setup_only.append(setup_cmds)

    def trigger_full_sequence(self, setup_cmds, run_cmds, fetch_cmds) -> None:
        self.sequences.append((setup_cmds, run_cmds, fetch_cmds))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.hardware_busy.emit(True)

    # Test drivers — mirroring ConnectorPresenter's emission order exactly.
    def finish(self, data: Optional[dict] = None) -> None:
        self.in_flight -= 1
        self.hardware_busy.emit(False)
        default = {"V1": [0.0, 1.0], "I1": [1e-3, 2e-3]}
        self.data_ready.emit(default if data is None else data)

    def fail(self, message: str = "SCPI error") -> None:
        self.in_flight -= 1
        self.hardware_busy.emit(False)
        self.sequence_failed.emit(message)

    def disconnect_bus(self) -> None:
        self._connected = False
        self.connection_changed.emit(False, "")

    def reconnect_bus(self) -> None:
        self._connected = True
        self.connection_changed.emit(True, "4156C - GPIB0::17::INSTR")


class _FakeQueuePanel(QObject):
    """Captures what the presenter pushes to the view."""

    remove_requested = Signal(str)
    move_requested = Signal(str, int)
    clear_requested = Signal()
    clear_finished_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.rows: list = []
        self.state = ""
        self.state_text = ""
        self.paused = False
        self.notice = ""
        self.closed = False
        self.presented = 0

    def display_items(self, rows) -> None:
        self.rows = list(rows)

    def display_state(self, state: str, text: str, paused: bool) -> None:
        self.state, self.state_text, self.paused = state, text, paused

    def display_notice(self, text: str) -> None:
        self.notice = text

    def present(self) -> None:
        self.presented += 1

    def close(self) -> None:
        self.closed = True


class _FakeSettings:
    class _Value:
        skip_reset = True  # keeps the built command list short
        keep_auto_calibration = False

    def get(self) -> "_FakeSettings._Value":
        return self._Value()


class _FakeProjects:
    """Stand-in for ProjectManager, so a test can swap the open project."""

    def __init__(self, db) -> None:
        self.current_db = db


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def qt_app():
    # QTimer.singleShot needs an application object to own the event loop.
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    tmp = Path(tempfile.mkdtemp(prefix="wiz_queue_"))
    database = ProjectDatabase.create_new(tmp / f"demo{PROJECT_EXTENSION}")
    yield database
    database.close()


@pytest.fixture
def rig(qt_app, db):
    """(presenter, service, connector, panel, projects) wired as in the app."""
    connector = _FakeConnector()
    projects = _FakeProjects(db)
    service = SetupRunService(projects, _FakeSettings(), connector)
    panel = _FakeQueuePanel()
    presenter = QueuePresenter(panel, service, projects, connector)
    # The service caches the connected model from this signal, exactly as it
    # does in the app.
    connector.connection_changed.emit(True, "4156C - GPIB0::17::INSTR")
    return presenter, service, connector, panel, projects


def _add_setup(db, name: str) -> int:
    with db.session() as s:
        setup = MeasurementSetup(
            name=name,
            instrument_model="4156C",
            setup_type="SWEEP",
            setup_data=dict(_SWEEP_CONFIG),
        )
        s.add(setup)
        s.flush()
        return setup.id


def _pump(qt_app, rounds: int = 6) -> None:
    """Let every queued single-shot dispatch fire."""
    for _ in range(rounds):
        qt_app.processEvents()


def _exec_names(db) -> list[str]:
    with db.session() as s:
        return sorted(
            e.name for e in s.query(MeasurementExecution).all()  # noqa: F401
        )


def _statuses(panel) -> list[QueueItemStatus]:
    return [row.status for row in panel.rows]


# ── Sequential execution ─────────────────────────────────────────────────────


def test_queue_runs_items_in_order_one_at_a_time(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    ids = [_add_setup(db, f"setup_{n}") for n in range(3)]
    for n, setup_id in enumerate(ids):
        presenter.enqueue(setup_id, f"setup_{n}", f"run_{n}")
    _pump(qt_app)

    # Only the first item may be on the bus.
    assert len(connector.sequences) == 1
    assert _statuses(panel)[0] is QueueItemStatus.RUNNING
    assert _statuses(panel)[1:] == [QueueItemStatus.WAITING] * 2

    for _ in range(3):
        connector.finish()
        _pump(qt_app)

    # This is the invariant the whole design protects: trigger_full_sequence is
    # not re-entrant, so two overlapping sequences must never exist.
    assert connector.max_in_flight == 1
    assert len(connector.sequences) == _BATCH
    assert _statuses(panel) == [QueueItemStatus.DONE] * _BATCH
    assert _exec_names(db) == ["run_0", "run_1", "run_2"]


def test_enqueue_while_idle_starts_immediately(rig, qt_app, db):
    presenter, _service, connector, _panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s"), "s", "run_now")
    _pump(qt_app)
    assert len(connector.sequences) == 1


def test_queue_waits_for_a_manual_run_to_finish(rig, qt_app, db):
    presenter, service, connector, panel, _projects = rig
    manual_id = _add_setup(db, "manual")
    queued_id = _add_setup(db, "queued")

    # A Runs-page run takes the bus first.
    assert service.start(manual_id, "manual_run", "") is None
    presenter.enqueue(queued_id, "queued", "queued_run")
    _pump(qt_app)

    assert len(connector.sequences) == 1  # the queued item held back
    assert _statuses(panel) == [QueueItemStatus.WAITING]

    connector.finish()  # the manual run returns; the queue takes the bus
    _pump(qt_app)
    assert len(connector.sequences) == _PAIR
    assert connector.max_in_flight == 1

    connector.finish()  # the queued run returns
    _pump(qt_app)
    assert _exec_names(db) == ["manual_run", "queued_run"]
    assert _statuses(panel) == [QueueItemStatus.DONE]


# ── Duplicate setups / name collisions ───────────────────────────────────────


def test_same_setup_queued_repeatedly_gets_distinct_run_names(
    rig, qt_app, db
):
    presenter, _service, connector, _panel, _projects = rig
    setup_id = _add_setup(db, "repeat")

    # Names proposed the way the Runs page does it: each one must account for
    # the entries already queued but not yet written to the database.
    for _ in range(3):
        proposed = presenter.proposed_run_name(setup_id)
        presenter.enqueue(setup_id, "repeat", proposed)
    _pump(qt_app)
    for _ in range(3):
        connector.finish()
        _pump(qt_app)

    names = _exec_names(db)
    assert names == ["repeat-run-1", "repeat-run-2", "repeat-run-3"]
    assert len(set(names)) == _BATCH


def test_proposed_name_accounts_for_the_run_already_on_the_bus(
    rig, qt_app, db
):
    """A manual run holds its name before the database ever sees it.

    Apply Setup and Run takes "<setup>-run-1" and only writes it when the data
    comes back.  Queuing the same setup meanwhile must not be offered that
    same name — it is claimed, just not yet persisted.
    """
    presenter, service, connector, _panel, _projects = rig
    setup_id = _add_setup(db, "bjt")

    manual = presenter.proposed_run_name(setup_id)
    assert manual == "bjt-run-1"
    assert service.start(setup_id, manual, "") is None
    assert service.is_busy is True

    # The run is in flight: nothing is in the database and the queue is empty,
    # yet the next proposal must still step past the running one.
    assert _exec_names(db) == []
    queued = presenter.proposed_run_name(setup_id)
    assert queued == "bjt-run-2"

    presenter.enqueue(setup_id, "bjt", queued)
    _pump(qt_app)
    connector.finish()  # the manual run returns
    _pump(qt_app)
    connector.finish()  # the queued run returns
    _pump(qt_app)

    # Both landed under the names that were offered — neither was silently
    # renamed at persist time.
    assert _exec_names(db) == ["bjt-run-1", "bjt-run-2"]


def test_colliding_run_name_is_corrected_at_dispatch(rig, qt_app, db):
    presenter, _service, connector, _panel, _projects = rig
    setup_id = _add_setup(db, "dup")
    # Both entries deliberately request the SAME name — the second must be
    # renamed rather than rejected (execution names are unique per project).
    presenter.enqueue(setup_id, "dup", "same_name")
    presenter.enqueue(setup_id, "dup", "same_name")
    _pump(qt_app)
    connector.finish()
    _pump(qt_app)
    connector.finish()
    _pump(qt_app)

    names = _exec_names(db)
    assert len(names) == _PAIR
    assert len(set(names)) == _PAIR
    assert "same_name" in names


# ── Hardware failure → pause ─────────────────────────────────────────────────


def test_hardware_failure_pauses_the_queue(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    for n in range(3):
        presenter.enqueue(_add_setup(db, f"s{n}"), f"s{n}", f"run_{n}")
    _pump(qt_app)

    connector.fail("SCPI Error: -113")
    _pump(qt_app)

    assert panel.paused is True
    assert panel.state == str(QueueState.PAUSED)
    assert _statuses(panel) == [
        QueueItemStatus.FAILED,
        QueueItemStatus.WAITING,
        QueueItemStatus.WAITING,
    ]
    # Nothing new was pushed at an instrument in an unknown state.
    assert len(connector.sequences) == 1
    assert _exec_names(db) == []


def test_resume_drains_the_rest_of_the_queue(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    for n in range(3):
        presenter.enqueue(_add_setup(db, f"s{n}"), f"s{n}", f"run_{n}")
    _pump(qt_app)
    connector.fail()
    _pump(qt_app)

    panel.resume_requested.emit()
    _pump(qt_app)
    connector.finish()
    _pump(qt_app)
    connector.finish()
    _pump(qt_app)

    assert panel.paused is False
    assert _statuses(panel) == [
        QueueItemStatus.FAILED,
        QueueItemStatus.DONE,
        QueueItemStatus.DONE,
    ]
    assert _exec_names(db) == ["run_1", "run_2"]


def test_a_failed_run_does_not_adopt_the_next_dataset(rig, qt_app, db):
    """The stale-pending hazard: a failure must disarm the service."""
    presenter, service, connector, panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    _pump(qt_app)
    connector.fail()
    _pump(qt_app)

    assert service.owns_run is False
    # A quick run from a config page returns data next; it must NOT be saved
    # under the failed queue entry.
    connector.data_ready.emit({"V1": [1.0]})
    _pump(qt_app)
    assert _exec_names(db) == []


# ── Disconnection ────────────────────────────────────────────────────────────


def test_disconnect_pauses_the_queue(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)

    connector.disconnect_bus()
    _pump(qt_app)
    assert panel.paused is True


def test_reconnect_does_not_auto_resume(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)
    connector.fail()  # frees the bus and pauses
    _pump(qt_app)
    started = len(connector.sequences)

    connector.reconnect_bus()
    _pump(qt_app)

    # Deliberate: the physical setup may have been touched while the
    # instrument was off the bus, so a human decides when to continue.
    assert panel.paused is True
    assert len(connector.sequences) == started
    assert panel.notice != ""


def test_queue_pauses_rather_than_dispatching_while_offline(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    connector.disconnect_bus()
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    _pump(qt_app)

    assert connector.sequences == []
    assert panel.paused is True


# ── Setup deleted / renamed after enqueue ────────────────────────────────────


def test_deleted_setup_is_skipped_and_the_batch_continues(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    doomed = _add_setup(db, "doomed")
    survivor = _add_setup(db, "survivor")
    presenter.enqueue(doomed, "doomed", "run_doomed")
    presenter.enqueue(survivor, "survivor", "run_survivor")

    # Delete before anything is dispatched.
    with db.session() as s:
        s.delete(s.get(MeasurementSetup, doomed))
    _pump(qt_app)

    # A data problem, not a hardware one: skip it, keep the batch alive.
    assert panel.paused is False
    assert _statuses(panel)[0] is QueueItemStatus.FAILED
    assert _statuses(panel)[1] is QueueItemStatus.RUNNING
    assert panel.rows[0].setup_label.endswith("(deleted)")

    connector.finish()
    _pump(qt_app)
    assert _exec_names(db) == ["run_survivor"]


def test_a_new_setup_never_inherits_a_deleted_setup_id(rig, qt_app, db):
    """A replacement setup must not be executed in a deleted one's place.

    The queue holds only ``setup_id`` and re-reads the configuration at
    dispatch time.  When SQLite recycled the rowid of the last deleted setup,
    a setup saved after the queued one was deleted took over its id — and the
    queued item silently ran the *replacement's* configuration on hardware.
    """
    doomed = _add_setup(db, "doomed")
    presenter, _service, connector, panel, _projects = rig
    presenter.enqueue(doomed, "doomed", "run_doomed")

    with db.session() as s:
        s.delete(s.get(MeasurementSetup, doomed))
    replacement = _add_setup(db, "replacement")
    _pump(qt_app)

    assert replacement != doomed, "a deleted setup id was reassigned"
    # The queued item is gone for good: nothing reached the instrument and no
    # execution was written against the replacement.
    assert connector.sequences == []
    assert _statuses(panel)[0] is QueueItemStatus.FAILED
    assert panel.rows[0].setup_label.endswith("(deleted)")
    assert _exec_names(db) == []


def test_renamed_setup_shows_its_current_name_and_still_runs(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    setup_id = _add_setup(db, "old_name")
    presenter.enqueue(setup_id, "old_name", "run_0")

    with db.session() as s:
        s.get(MeasurementSetup, setup_id).name = "new_name"
    _pump(qt_app)

    # The queue tracks setups by id, so a rename shows through and the run
    # still executes against the right configuration.
    assert panel.rows[0].setup_label == "new_name"
    connector.finish()
    _pump(qt_app)
    assert _exec_names(db) == ["run_0"]


def test_imported_setup_is_rejected_without_touching_hardware(
    rig, qt_app, db
):
    presenter, _service, connector, panel, _projects = rig
    with db.session() as s:
        setup = MeasurementSetup(
            name="imported",
            instrument_model="External",
            setup_type="IMPORT",
            setup_data={"mode": "IMPORT", "display_vars": ["V1"]},
        )
        s.add(setup)
        s.flush()
        imported_id = setup.id
    presenter.enqueue(imported_id, "imported", "run_0")
    _pump(qt_app)

    assert connector.sequences == []
    assert _statuses(panel) == [QueueItemStatus.FAILED]
    assert panel.paused is False


# ── Project switching ────────────────────────────────────────────────────────


def test_project_switch_drops_the_queue_and_discards_in_flight_data(
    rig, qt_app, db
):
    presenter, service, connector, panel, projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)
    assert len(connector.sequences) == 1  # one measurement on the bus

    # The user opens another project while the instrument is measuring.
    other_dir = Path(tempfile.mkdtemp(prefix="wiz_queue_other_"))
    other = ProjectDatabase.create_new(other_dir / f"other{PROJECT_EXTENSION}")
    try:
        projects.current_db = other
        presenter.on_project_changed()
        _pump(qt_app)

        # The queue is emptied, but the measurement already handed to the
        # instrument cannot be recalled — it is still genuinely in flight.
        assert panel.rows == []
        assert service.owns_run is True
        assert presenter.has_active_work() is True

        # It finishes and returns data belonging to the OLD project — that
        # data must be discarded, not misfiled into the new one.
        connector.finish()
        _pump(qt_app)

        with other.session() as s:
            assert s.query(MeasurementExecution).count() == 0
        with db.session() as s:
            assert s.query(MeasurementExecution).count() == 0
        # And nothing from the dropped queue was started against either.
        assert len(connector.sequences) == 1
        assert service.owns_run is False
        assert presenter.has_active_work() is False
    finally:
        other.close()


# ── Panel actions ────────────────────────────────────────────────────────────


def test_remove_and_reorder_from_the_panel(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    for n in range(4):
        presenter.enqueue(_add_setup(db, f"s{n}"), f"s{n}", f"run_{n}")
    _pump(qt_app)  # run_0 starts

    waiting = [r for r in panel.rows if r.status is QueueItemStatus.WAITING]
    panel.remove_requested.emit(waiting[0].uid)  # drop run_1
    panel.move_requested.emit(waiting[2].uid, -1)  # run_3 ahead of run_2

    remaining = [
        r.run_name
        for r in panel.rows
        if r.status is QueueItemStatus.WAITING
    ]
    assert remaining == ["run_3", "run_2"]

    for _ in range(3):
        connector.finish()
        _pump(qt_app)
    assert _exec_names(db) == ["run_0", "run_2", "run_3"]
    with db.session() as s:
        assert not ExecutionRepository.name_exists(s, "run_1")


def test_clear_queue_spares_the_running_item(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    for n in range(3):
        presenter.enqueue(_add_setup(db, f"s{n}"), f"s{n}", f"run_{n}")
    _pump(qt_app)

    panel.clear_requested.emit()
    assert _statuses(panel) == [QueueItemStatus.RUNNING]

    connector.finish()
    _pump(qt_app)
    # The measurement already on the bus completes and is saved; nothing else
    # is started.
    assert _exec_names(db) == ["run_0"]
    assert len(connector.sequences) == 1


def test_pause_blocks_dispatch_until_resumed(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)

    panel.pause_requested.emit()
    connector.finish()
    _pump(qt_app)
    assert len(connector.sequences) == 1  # run_1 held back

    panel.resume_requested.emit()
    _pump(qt_app)
    assert len(connector.sequences) == _PAIR


def test_clear_finished_keeps_pending_work(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)
    connector.finish()
    _pump(qt_app)

    panel.clear_finished_requested.emit()
    assert _statuses(panel) == [QueueItemStatus.RUNNING]


# ── Badge / shutdown ─────────────────────────────────────────────────────────


def test_badge_tracks_active_entries(rig, qt_app, db):
    presenter, _service, connector, _panel, _projects = rig
    seen: list[tuple[int, str]] = []
    presenter.badge_changed.connect(lambda n, s: seen.append((n, s)))

    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)
    assert seen[-1] == (2, str(QueueState.RUNNING))

    connector.finish()
    _pump(qt_app)
    assert seen[-1] == (1, str(QueueState.RUNNING))

    connector.finish()
    _pump(qt_app)
    assert seen[-1] == (0, str(QueueState.IDLE))


def test_shutdown_stops_any_further_dispatch(rig, qt_app, db):
    presenter, _service, connector, panel, _projects = rig
    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    presenter.enqueue(_add_setup(db, "s1"), "s1", "run_1")
    _pump(qt_app)

    presenter.shutdown()
    connector.finish()
    _pump(qt_app)

    assert panel.closed is True
    assert presenter.has_active_work() is False
    # No new sequence may start while the GPIB pool is being drained.
    assert len(connector.sequences) == 1


def test_panel_is_an_independent_top_level_window(qt_app):
    """It must behave like the documentation window, not like a dialog.

    A top-level widget that still has a parent is a *secondary* window: the
    window manager pins it above its owner, gives it no taskbar entry, and
    generally no independent minimise button.  Parentless is what makes it a
    real window — and it must never be the thing keeping the app alive.
    """
    panel = QueuePanelDialog()
    try:
        assert panel.parent() is None
        assert panel.isWindow()
        assert not panel.isModal()
        assert not panel.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)
        # The caption doubles as the taskbar label, so it names the app.
        assert "Wizard" in panel.windowTitle()
    finally:
        panel.close()
        panel.deleteLater()


def test_present_restores_a_minimised_window(qt_app):
    """Clicking Queue while the window is minimised must bring it back.

    ``show()`` alone leaves an already-visible-but-minimised window in the
    taskbar, so the button would look dead.
    """
    panel = QueuePanelDialog()
    try:
        panel.present()
        qt_app.processEvents()
        panel.showMinimized()
        qt_app.processEvents()
        assert panel.isMinimized()

        panel.present()
        qt_app.processEvents()
        assert not panel.isMinimized()
        assert panel.isVisible()
    finally:
        panel.close()
        panel.deleteLater()


def test_panel_rows_never_create_stray_top_level_windows(qt_app):
    """Regression: rebuilding rows must not flash windows on screen.

    ``setVisible(True)`` on a *parentless* widget makes it a real top-level
    window.  The row action buttons are created, shown, and only then added to
    the row layout, so building them without a parent flashed one stray window
    per visible button — every time the panel refreshed, which is on every
    connector event.  Empty queues were unaffected (no rows, no buttons),
    which is exactly how the bug presented.
    """
    rows = [
        QueueRow(
            uid=f"u{i}",
            position=i + 1,
            setup_label=f"setup_{i}",
            run_name=f"run_{i}",
            runtime_label="> 1 s",
            status=QueueItemStatus.WAITING,
            status_text="Waiting",
            can_edit=True,
            can_move_up=i > 0,
            can_move_down=i < _BATCH - 1,
        )
        for i in range(_BATCH)
    ]

    panel = QueuePanelDialog()
    before = set(QApplication.topLevelWidgets())
    offenders: list[str] = []
    original = QToolButton.setVisible

    def guarded(self, visible):
        if visible and self.parent() is None:
            offenders.append(self.text())
        original(self, visible)

    QToolButton.setVisible = guarded
    try:
        panel.display_items(rows)
        qt_app.processEvents()
    finally:
        QToolButton.setVisible = original

    assert offenders == []
    stray = [
        w
        for w in set(QApplication.topLevelWidgets()) - before
        if w is not panel
    ]
    assert stray == []
    panel.close()
    panel.deleteLater()


def test_rows_are_selectable_and_selection_survives_a_rebuild(qt_app):
    """Clicking a queued setup must select it, as on the Runs page.

    The presenter rebuilds the list on every pump and status tick, so a
    selection that did not survive ``display_items`` would flicker away on its
    own a fraction of a second after the click.
    """
    rows = [
        QueueRow(
            uid=f"uid-{i}",
            position=i + 1,
            setup_label=f"setup-{i}",
            run_name=f"run-{i}",
            runtime_label="> 1 s",
            status=QueueItemStatus.WAITING,
            status_text="Waiting",
            can_edit=True,
            can_move_up=i > 0,
            can_move_down=i < _BATCH - 1,
        )
        for i in range(_BATCH)
    ]
    panel = QueuePanelDialog()
    try:
        panel.display_items(rows)
        qt_app.processEvents()

        first = panel._list.item(0)
        assert first.data(Qt.ItemDataRole.UserRole) == "uid-0"
        # A real press on the row widget: the widget covers its item, so the
        # click never reaches the viewport and the row has to forward it.
        second = panel._list.itemWidget(panel._list.item(1))
        QTest.mouseClick(second, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert panel._list.currentItem().data(Qt.ItemDataRole.UserRole) == (
            "uid-1"
        )

        panel.display_items(rows)
        qt_app.processEvents()
        assert panel._list.currentItem().data(Qt.ItemDataRole.UserRole) == (
            "uid-1"
        )

        # An entry that left the queue simply drops out of the selection.
        panel.display_items(rows[:1])
        qt_app.processEvents()
        current = panel._list.currentItem()
        assert current is None or current.data(Qt.ItemDataRole.UserRole) != (
            "uid-1"
        )
    finally:
        panel.close()
        panel.deleteLater()


def test_run_button_queues_instead_of_greying_out_while_busy(qt_app, db):
    """The single run control has three states, not two.

    Disconnected it is dead; connected and idle it runs; connected but *busy*
    it becomes "Add to Queue" — scheduling is exactly what the user wants at
    the moment the instrument is unavailable, so the button changes job rather
    than switching off.
    """
    page = RunsPageView()
    fired: list[tuple[str, int]] = []
    page.apply_run_fetch_requested.connect(
        lambda i: fired.append(("run", i))
    )
    page.enqueue_setup_requested.connect(
        lambda i: fired.append(("queue", i))
    )
    try:
        setup_id = _add_setup(db, "s0")
        with db.session() as s:
            page.display_setups(SetupRepository.list_rows(s))
        page.select_setup(setup_id)

        page.set_hardware_state(connected=False, busy=False)
        assert not page._btn_run.isEnabled()
        assert page._btn_run.text() == tr_ui(_T.RUNS_BTN_APPLY_RUN)

        page.set_hardware_state(connected=True, busy=False)
        assert page._btn_run.isEnabled()
        assert page._btn_run.text() == tr_ui(_T.RUNS_BTN_APPLY_RUN)
        page._btn_run.click()

        page.set_hardware_state(connected=True, busy=True)
        assert page._btn_run.isEnabled()
        assert page._btn_run.text() == tr_ui(_T.QUEUE_BTN_ADD)
        # Applying a setup still needs an idle bus; only running is rerouted.
        assert not page._btn_apply.isEnabled()
        page._btn_run.click()

        assert fired == [("run", setup_id), ("queue", setup_id)]
    finally:
        page.deleteLater()


def test_has_active_work_reports_pending_and_running(rig, qt_app, db):
    presenter, _service, connector, _panel, _projects = rig
    assert presenter.has_active_work() is False

    presenter.enqueue(_add_setup(db, "s0"), "s0", "run_0")
    assert presenter.has_active_work() is True

    _pump(qt_app)
    connector.finish()
    _pump(qt_app)
    assert presenter.has_active_work() is False
