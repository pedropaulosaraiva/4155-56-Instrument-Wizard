"""
test/models/test_measurement_queue.py
-------------------------------------
Unit tests for the pure measurement-queue model.

No Qt, no database — ``MeasurementQueue`` is deliberately a plain Python
container so the ordering rules and the state machine can be pinned down here,
leaving the presenter tests free to focus on dispatch.
"""

from __future__ import annotations

import pytest

from wizard_4155_4156.models.measurement_queue import (
    MeasurementQueue,
    QueueItem,
    QueueItemStatus,
    QueueState,
    positions,
)

#: Size of the shared ``three`` fixture, and the counts derived from it.
_N_ITEMS = 3
_N_WAITING_AFTER_RUN = _N_ITEMS - 1


def _item(setup_id: int = 1, run_name: str = "") -> QueueItem:
    return QueueItem(
        setup_id=setup_id,
        setup_name=f"setup_{setup_id}",
        run_name=run_name or f"setup_{setup_id}-run-1",
    )


@pytest.fixture
def queue() -> MeasurementQueue:
    return MeasurementQueue()


@pytest.fixture
def three(queue: MeasurementQueue) -> list[QueueItem]:
    """A queue holding three waiting entries, in order."""
    return [queue.add(_item(n, f"run_{n}")) for n in (1, 2, 3)]


# ── Identity & ordering ──────────────────────────────────────────────────────


def test_items_are_dispatched_in_insertion_order(queue, three):
    assert [i.uid for i in queue.items()] == [i.uid for i in three]
    assert queue.next_waiting().uid == three[0].uid


def test_each_item_gets_a_distinct_uid(queue):
    first, second = queue.add(_item()), queue.add(_item())
    assert first.uid != second.uid
    assert queue.get(first.uid) is first


def test_get_unknown_uid_returns_none(queue, three):
    assert queue.get("not-a-uid") is None


# ── Counters ─────────────────────────────────────────────────────────────────


def test_counters_track_status_transitions(queue, three):
    assert (queue.waiting_count, queue.active_count) == (3, 3)

    queue.mark_running(three[0].uid)
    assert (queue.waiting_count, queue.active_count) == (2, 3)

    queue.mark_done(three[0].uid, execution_id=7)
    assert (queue.waiting_count, queue.active_count) == (2, 2)
    assert (queue.done_count, queue.finished_count) == (1, 1)

    queue.mark_running(three[1].uid)
    queue.mark_failed(three[1].uid, "boom")
    assert (queue.done_count, queue.finished_count) == (1, 2)
    assert queue.active_count == 1


# ── State ────────────────────────────────────────────────────────────────────


def test_state_reflects_the_queue_contents(queue):
    assert queue.state() is QueueState.IDLE

    item = queue.add(_item())
    assert queue.state() is QueueState.PENDING

    queue.mark_running(item.uid)
    assert queue.state() is QueueState.RUNNING

    # Paused wins over everything — it is the reason nothing is advancing.
    assert queue.state(paused=True) is QueueState.PAUSED

    queue.mark_done(item.uid)
    assert queue.state() is QueueState.IDLE


# ── Single-runner invariant ──────────────────────────────────────────────────


def test_only_one_item_can_run_at_a_time(queue, three):
    assert queue.mark_running(three[0].uid) is True
    # The whole design rests on this: the connector's trigger_full_sequence is
    # not re-entrant, so a second runner must be impossible.
    assert queue.mark_running(three[1].uid) is False
    assert queue.running.uid == three[0].uid
    assert three[1].status is QueueItemStatus.WAITING


def test_mark_running_stamps_the_start_time(queue, three):
    queue.mark_running(three[0].uid)
    assert three[0].started_at is not None


def test_finished_items_do_not_transition_again(queue, three):
    queue.mark_running(three[0].uid)
    queue.mark_done(three[0].uid, execution_id=1)
    assert queue.mark_failed(three[0].uid, "late error") is False
    assert three[0].status is QueueItemStatus.DONE
    assert three[0].execution_id == 1


def test_next_waiting_skips_running_and_finished(queue, three):
    queue.mark_running(three[0].uid)
    queue.mark_done(three[0].uid)
    queue.mark_running(three[1].uid)
    queue.mark_failed(three[1].uid, "boom")
    assert queue.next_waiting().uid == three[2].uid

    queue.mark_running(three[2].uid)
    queue.mark_done(three[2].uid)
    assert queue.next_waiting() is None


# ── Removal ──────────────────────────────────────────────────────────────────


def test_remove_drops_a_waiting_entry(queue, three):
    assert queue.remove(three[1].uid) is True
    assert [i.uid for i in queue.items()] == [three[0].uid, three[2].uid]


def test_remove_refuses_a_running_entry(queue, three):
    queue.mark_running(three[0].uid)
    # A measurement on the bus cannot be recalled, so it cannot be removed.
    assert queue.remove(three[0].uid) is False
    assert queue.running is not None


def test_remove_unknown_uid_is_a_no_op(queue, three):
    assert queue.remove("not-a-uid") is False
    assert len(queue.items()) == _N_ITEMS


def test_clear_waiting_spares_the_running_entry(queue, three):
    queue.mark_running(three[0].uid)
    assert queue.clear_waiting() == _N_WAITING_AFTER_RUN
    assert [i.uid for i in queue.items()] == [three[0].uid]


def test_clear_finished_keeps_active_entries(queue, three):
    queue.mark_running(three[0].uid)
    queue.mark_done(three[0].uid)
    queue.mark_running(three[1].uid)
    assert queue.clear_finished() == 1
    assert [i.uid for i in queue.items()] == [three[1].uid, three[2].uid]


def test_clear_all_drops_everything_including_the_runner(queue, three):
    queue.mark_running(three[0].uid)
    assert queue.clear_all() == _N_ITEMS
    assert queue.items() == []
    assert queue.running is None


# ── Reordering ───────────────────────────────────────────────────────────────


def test_move_reorders_waiting_entries(queue, three):
    assert queue.move(three[2].uid, -1) is True
    assert [i.uid for i in queue.items()] == [
        three[0].uid,
        three[2].uid,
        three[1].uid,
    ]
    assert queue.move(three[2].uid, 1) is True
    assert [i.uid for i in queue.items()] == [i.uid for i in three]


def test_move_is_clamped_at_the_ends(queue, three):
    assert queue.move(three[0].uid, -1) is False
    assert queue.move(three[2].uid, 1) is False
    assert [i.uid for i in queue.items()] == [i.uid for i in three]


def test_move_cannot_displace_the_running_entry(queue, three):
    queue.mark_running(three[0].uid)
    # The first *waiting* slot is index 1 — three[1] is already there.
    assert queue.move(three[1].uid, -1) is False
    assert queue.move(three[2].uid, -1) is True
    assert [i.uid for i in queue.items()] == [
        three[0].uid,
        three[2].uid,
        three[1].uid,
    ]
    assert queue.running.uid == three[0].uid


def test_move_refuses_a_non_waiting_entry(queue, three):
    queue.mark_running(three[0].uid)
    assert queue.move(three[0].uid, 1) is False
    queue.mark_done(three[0].uid)
    assert queue.move(three[0].uid, 1) is False


def test_move_by_zero_changes_nothing(queue, three):
    assert queue.move(three[1].uid, 0) is False


def test_move_steps_over_a_finished_entry(queue):
    first, second, third = (queue.add(_item(n)) for n in (1, 2, 3))
    queue.mark_running(second.uid)
    queue.mark_failed(second.uid, "boom")
    # Waiting slots are [first, third]; one step up must move `third` a whole
    # waiting position — past the failed row *and* past `first` — rather than
    # merely swapping it with the finished row sitting in between.
    assert queue.move(third.uid, -1) is True
    waiting = [i.uid for i in queue.items() if i.is_waiting]
    assert waiting == [third.uid, first.uid]
    assert queue.next_waiting().uid == third.uid


# ── Name reservation ─────────────────────────────────────────────────────────


def test_reserved_names_cover_active_entries_only(queue):
    waiting = queue.add(_item(1, "run_a"))
    running = queue.add(_item(2, "run_b"))
    finished = queue.add(_item(3, "run_c"))
    queue.mark_running(running.uid)
    queue.mark_done(finished.uid)

    # Only names that have not been written to the database yet need to be
    # avoided; a finished entry's name already exists as an execution.
    assert queue.reserved_names() == {"run_a", "run_b"}
    assert waiting.run_name in queue.reserved_names()


def test_reserved_names_ignores_blank_names(queue):
    queue.add(_item(1, "run_a"))
    queue.add(QueueItem(setup_id=2, setup_name="s2", run_name=""))
    assert queue.reserved_names() == {"run_a"}


# ── Display positions ────────────────────────────────────────────────────────


def test_positions_number_only_the_pending_work(queue, three):
    queue.mark_running(three[0].uid)
    queue.mark_done(three[0].uid)
    # The finished row keeps its place but carries no number, so what the user
    # sees always reads 1..N over the work still ahead of them.
    assert positions(queue.items()) == [0, 1, 2]
