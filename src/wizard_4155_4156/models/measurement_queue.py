"""
models/measurement_queue.py
---------------------------
Ordered batch of measurement setups waiting to be executed.

Layer contract
--------------
- No Qt imports.  Pure Python dataclasses + list manipulation, unit-testable
  without a graphical context (see ``test/models/test_measurement_queue.py``).
- No database access either: an item references a setup only by ``setup_id``,
  plus a *snapshot* of its name taken at enqueue time.  The setup itself is
  re-read from the project database at dispatch time, so a setup renamed or
  deleted after being queued can never leave a stale object graph behind.

Ordering rules
--------------
Items are held in a single list in execution order.  Exactly one item may be
RUNNING at a time (enforced by ``mark_running``), and it always sits ahead of
every WAITING item because ``next_waiting`` consumes the list front-to-back.
``move`` reorders inside the WAITING block only — a running measurement cannot
be displaced (it cannot be aborted either; the pool thread is parked inside a
blocking ``*OPC?`` read for its whole duration).

Finished items (DONE / FAILED) are kept so the panel can show the outcome of a
batch; ``clear_finished`` drops them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import List, Optional, Sequence, Set, Tuple


class QueueItemStatus(StrEnum):
    """Lifecycle of a single queued setup."""

    WAITING = "WAITING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class QueueState(StrEnum):
    """Lifecycle of the queue as a whole (drives the badge + state chip)."""

    IDLE = "IDLE"  # nothing running, nothing waiting
    RUNNING = "RUNNING"  # an item is executing
    PENDING = "PENDING"  # items waiting, none executing yet
    PAUSED = "PAUSED"  # halted after a hardware failure / disconnect


#: Statuses that still consume queue capacity (counted by the toolbar badge).
_ACTIVE = (QueueItemStatus.WAITING, QueueItemStatus.RUNNING)
#: Statuses that are terminal.
_FINISHED = (QueueItemStatus.DONE, QueueItemStatus.FAILED)


def new_uid() -> str:
    """Stable identity for one queue entry (survives reordering)."""
    return uuid.uuid4().hex


@dataclass
class QueueItem:
    """One scheduled execution of a saved project setup."""

    setup_id: int
    #: Setup name captured at enqueue time — a display fallback only, used
    #: when the setup has since been deleted from the project.
    setup_name: str
    #: Execution name the user asked for.  Resolved against the database at
    #: dispatch time, so a collision is corrected rather than rejected.
    run_name: str = ""
    description: str = ""
    #: (min, max) estimated runtime in seconds, or None when indeterminate.
    runtime_bounds: Optional[Tuple[float, float]] = None
    #: The instrument-model mismatch warning was accepted at enqueue time, so
    #: no modal is ever raised mid-batch.
    allow_mismatch: bool = False
    status: QueueItemStatus = QueueItemStatus.WAITING
    error: str = ""
    started_at: Optional[datetime] = None
    execution_id: Optional[int] = None
    uid: str = field(default_factory=new_uid)

    @property
    def is_waiting(self) -> bool:
        return self.status is QueueItemStatus.WAITING

    @property
    def is_active(self) -> bool:
        return self.status in _ACTIVE


@dataclass(frozen=True)
class QueueRow:
    """Flat, detached snapshot of a queue entry for list display.

    Mirrors ``db.repository.SetupRow``: the view renders these and never sees
    a ``QueueItem`` (let alone the database), preserving the passive-view
    contract.  ``setup_label`` is resolved by the presenter against the live
    database, so a renamed setup shows its current name and a deleted one is
    marked as such.
    """

    uid: str
    position: int  # 1-based position shown in the panel
    setup_label: str
    run_name: str
    runtime_label: str
    status: QueueItemStatus
    status_text: str
    #: Remove / reorder are offered for WAITING items only.
    can_edit: bool
    can_move_up: bool
    can_move_down: bool


class MeasurementQueue:
    """Ordered list of :class:`QueueItem` with explicit state transitions.

    Every mutator is idempotent-safe on an unknown ``uid`` (returns ``False`` /
    ``0`` rather than raising), because the panel renders asynchronously and a
    row the user clicks may already have been consumed by the pump.
    """

    def __init__(self) -> None:
        self._items: List[QueueItem] = []

    # ── Reads ────────────────────────────────────────────────────────────────

    def items(self) -> List[QueueItem]:
        """Shallow copy of the entries in execution order."""
        return list(self._items)

    def get(self, uid: str) -> Optional[QueueItem]:
        return next((i for i in self._items if i.uid == uid), None)

    @property
    def running(self) -> Optional[QueueItem]:
        return next(
            (i for i in self._items if i.status is QueueItemStatus.RUNNING),
            None,
        )

    @property
    def waiting_count(self) -> int:
        return sum(1 for i in self._items if i.is_waiting)

    @property
    def active_count(self) -> int:
        """Waiting + running — the number shown on the toolbar badge."""
        return sum(1 for i in self._items if i.is_active)

    @property
    def finished_count(self) -> int:
        return sum(1 for i in self._items if i.status in _FINISHED)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self._items if i.status is QueueItemStatus.DONE)

    def next_waiting(self) -> Optional[QueueItem]:
        """The next item to dispatch, or None when nothing is waiting."""
        return next((i for i in self._items if i.is_waiting), None)

    def reserved_names(self) -> Set[str]:
        """Run names already claimed by items that have not executed yet.

        These names do not exist in the database, so a proposed name must
        avoid them as well as the persisted ones to keep every execution of a
        repeatedly-queued setup distinct.
        """
        return {i.run_name for i in self._items if i.is_active and i.run_name}

    def state(self, *, paused: bool = False) -> QueueState:
        if paused:
            return QueueState.PAUSED
        if self.running is not None:
            return QueueState.RUNNING
        if self.waiting_count:
            return QueueState.PENDING
        return QueueState.IDLE

    # ── Mutations ────────────────────────────────────────────────────────────

    def add(self, item: QueueItem) -> QueueItem:
        """Append to the back of the queue."""
        self._items.append(item)
        return item

    def remove(self, uid: str) -> bool:
        """Drop a WAITING entry.  A running/finished one is left alone."""
        item = self.get(uid)
        if item is None or not item.is_waiting:
            return False
        self._items.remove(item)
        return True

    def clear_waiting(self) -> int:
        """Drop every WAITING entry; returns how many were removed."""
        waiting = [i for i in self._items if i.is_waiting]
        self._items = [i for i in self._items if not i.is_waiting]
        return len(waiting)

    def clear_finished(self) -> int:
        """Drop every DONE/FAILED entry; returns how many were removed."""
        finished = [i for i in self._items if i.status in _FINISHED]
        self._items = [i for i in self._items if i.status not in _FINISHED]
        return len(finished)

    def clear_all(self) -> int:
        """Drop everything, including a running entry (project switch/exit).

        The instrument keeps executing whatever is already on the bus — that
        cannot be recalled — but the queue no longer references it, and the
        caller is responsible for discarding the eventual result.
        """
        count = len(self._items)
        self._items = []
        return count

    def move(self, uid: str, delta: int) -> bool:
        """Shift a WAITING entry by ``delta`` positions within the queue.

        Movement is confined to the WAITING block: the target index is clamped
        between the first and last waiting position, so a running item can
        never be displaced and a waiting item can never jump ahead of it.
        Returns True when the order actually changed.
        """
        item = self.get(uid)
        if item is None or not item.is_waiting or delta == 0:
            return False
        waiting_indexes = [
            idx for idx, i in enumerate(self._items) if i.is_waiting
        ]
        current = self._items.index(item)
        # Move by `delta` *waiting* slots, so a finished row sitting between
        # two waiting rows is stepped over rather than counting as a position.
        slot = waiting_indexes.index(current) + delta
        slot = max(0, min(len(waiting_indexes) - 1, slot))
        target = waiting_indexes[slot]
        if target == current:
            return False
        self._items.pop(current)
        self._items.insert(target, item)
        return True

    def mark_running(self, uid: str) -> bool:
        """Promote a WAITING entry to RUNNING.

        Refuses when another item is already running — the single-measurement
        invariant is enforced here rather than trusted to the caller.
        """
        item = self.get(uid)
        if item is None or not item.is_waiting or self.running is not None:
            return False
        item.status = QueueItemStatus.RUNNING
        item.started_at = datetime.now()
        item.error = ""
        return True

    def mark_done(self, uid: str, execution_id: Optional[int] = None) -> bool:
        item = self.get(uid)
        if item is None or item.status in _FINISHED:
            return False
        item.status = QueueItemStatus.DONE
        item.execution_id = execution_id
        item.error = ""
        return True

    def mark_failed(self, uid: str, error: str = "") -> bool:
        item = self.get(uid)
        if item is None or item.status in _FINISHED:
            return False
        item.status = QueueItemStatus.FAILED
        item.error = error
        return True


def positions(items: Sequence[QueueItem]) -> List[int]:
    """1-based display positions for ``items`` (unfinished entries only).

    Finished rows keep their place in the list but carry no position number,
    so the numbering the user sees always reads 1..N over the work that is
    still ahead of them.
    """
    out: List[int] = []
    counter = 0
    for item in items:
        if item.is_active:
            counter += 1
            out.append(counter)
        else:
            out.append(0)
    return out
