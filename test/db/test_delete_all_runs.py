"""
test/db/test_delete_all_runs.py
-------------------------------
Unit test for ``ExecutionRepository.delete_all`` — the bulk deletion behind the
Preferences "Delete All Measurement Runs…" advanced option.

Pure persistence layer (no PySide6), so it runs as a normal pytest module.
Verifies that every execution (and its cascaded children) is removed while
measurement setups and graph scenes are preserved and each setup's stale
``last_execution_date`` is cleared.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select

from wizard_4155_4156.db.engine import PROJECT_EXTENSION, ProjectDatabase
from wizard_4155_4156.db.repository import ExecutionRepository
from wizard_4155_4156.db.schema import (
    DataPoint,
    ExecutionVariable,
    GraphScene,
    LogMessage,
    MeasurementExecution,
    MeasurementSetup,
)

_N_RUNS = 2
_N_POINTS = _N_RUNS * 2  # two data points per run


@pytest.fixture
def db():
    tmp = Path(tempfile.mkdtemp(prefix="wiz_delall_"))
    database = ProjectDatabase.create_new(tmp / f"demo{PROJECT_EXTENSION}")
    yield database
    database.close()


def _seed(db) -> tuple[int, int]:
    """Seed 2 setups (one with 2 runs, one with 0) + a graph scene.

    Returns (setup_with_runs_id, graph_scene_id).
    """
    with db.session() as s:
        setup_a = MeasurementSetup(
            name="setup_a",
            instrument_model="4156C",
            setup_type="SWEEP",
            last_execution_date=datetime(2020, 1, 1),
        )
        setup_b = MeasurementSetup(
            name="setup_b",
            instrument_model="4156C",
            setup_type="SAMP",
        )
        s.add_all([setup_a, setup_b])
        s.flush()

        for n in range(_N_RUNS):
            var = ExecutionVariable(var_name="V1", position=0)
            var.data_points = [
                DataPoint(point_index=0, value=0.0),
                DataPoint(point_index=1, value=1.0),
            ]
            execution = MeasurementExecution(
                name=f"run_{n}",
                setup_id=setup_a.id,
                instrument_model="4156C",
            )
            execution.variables = [var]
            execution.log_messages = [
                LogMessage(message="ok", timestamp=datetime(2021, 1, 1))
            ]
            s.add(execution)

        scene = GraphScene(name="scene_1", position=0, scene_data={"grid": 1})
        s.add(scene)
        s.flush()
        return setup_a.id, scene.id


def test_delete_all_removes_runs_and_preserves_setups(db):
    setup_a_id, scene_id = _seed(db)

    # Sanity: 2 executions, children, and 1 scene exist.
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(MeasurementExecution))
        assert (
            s.scalar(select(func.count()).select_from(DataPoint)) == _N_POINTS
        )

    with db.session() as s:
        deleted = ExecutionRepository.delete_all(s)

    assert deleted == _N_RUNS

    with db.session() as s:
        # Executions and every cascaded child are gone.
        assert (
            s.scalar(select(func.count()).select_from(MeasurementExecution))
            == 0
        )
        assert (
            s.scalar(select(func.count()).select_from(ExecutionVariable)) == 0
        )
        assert s.scalar(select(func.count()).select_from(DataPoint)) == 0
        assert s.scalar(select(func.count()).select_from(LogMessage)) == 0

        # Both setups survive; the stale last_execution_date is cleared.
        setups = s.scalars(select(MeasurementSetup)).all()
        assert {su.name for su in setups} == {"setup_a", "setup_b"}
        assert all(su.last_execution_date is None for su in setups)

        # The graph scene is untouched.
        scene = s.get(GraphScene, scene_id)
        assert scene is not None
        assert scene.scene_data == {"grid": 1}


def test_delete_all_on_empty_project_returns_zero(db):
    with db.session() as s:
        assert ExecutionRepository.delete_all(s) == 0
