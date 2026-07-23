"""
test/db/test_persistence.py
---------------------------
Unit tests for the SQLite/SQLAlchemy persistence layer.

Pure persistence layer (no PySide6).  Each test gets a real temp-file
``.wiz4155`` database, so the per-file engine and the ``PRAGMA
foreign_keys=ON`` cascade behavior are genuinely exercised — covering the
sweep/sampling dict<->ORM round-trip, multi-variable executions, non-finite
data points, log messages, cascade delete and the unique-name constraints.
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from wizard_4155_4156.db.assembler import (
    config_dict_to_setup,
    execution_to_data_dict,
    fetch_result_to_execution,
    setup_to_config_dict,
)
from wizard_4155_4156.db.engine import PROJECT_EXTENSION, ProjectDatabase
from wizard_4155_4156.db.schema import (
    DataPoint,
    ExecutionVariable,
    LogMessage,
    MeasurementExecution,
    MeasurementSetup,
)

# ── Fixtures: full canonical config dicts ────────────────────────────────────

SWEEP_CFG = {
    "mode": "SWEEP",
    "channels": {
        "SMU1": {
            "v_name": "V1",
            "i_name": "I1",
            "function": "VAR1",
            "smu_mode": "V",
            "standby": "OFF",
        },
        "SMU2": {
            "v_name": "V2",
            "i_name": "I2",
            "function": "VAR2",
            "smu_mode": "I",
            "standby": "ON",
        },
        "SMU3": {
            "v_name": "V3",
            "i_name": "I3",
            "function": "CONS",
            "smu_mode": "V",
            "standby": "OFF",
        },
        "SMU4": {"disable": 1},
        "VMU1": {"v_name": "VMU1", "vmu_mode": "V"},
        "VMU2": {"disable": 1},
        "VSU1": {"v_name": "VSU1", "function": "VARD"},
        "VSU2": {"disable": 1},
    },
    "measurement_setup": {
        "integration_mode": "MED",
        "short_time": 0.0002,
        "long_time_cycles": 50,
        "wait_time": 1.0,
        "ranges": {
            "SMU1": {"mode": "AUTO"},
            "SMU2": {"mode": "FIX", "value": 0.01},
            "VMU1": {"mode": "LIM", "value": 2.0},
        },
    },
    "sweep_setup": {
        "delay": 0.1,
        "hold_time": 0.5,
        "sweep_stop": "COMPLIANCE",
        # VAR1: SMU voltage source, compliance + power compliance ON.
        "var1": {
            "mode": "SINGLE",
            "spacing": "LINEAR",
            "start": 0.0,
            "stop": 1.0,
            "step": 0.1,
            "compliance": 0.01,
            "pcompliance": 1.0,
        },
        # VAR2: SMU current source, compliance only (pcomp OFF).
        "var2": {
            "start": 0.0,
            "step": 0.1,
            "n_of_steps": 3,
            "compliance": 0.01,
        },
        # VARD: VSU-driven -> no compliance / pcompliance keys.
        "vard": {"offset": 0.0, "ratio": 1.0},
        "constants": {"SMU3": {"source": 5.0, "compliance": 0.01}},
    },
    "display_vars": ["V1", "I1", "V2", "I2", "V3", "I3", "VMU1", "VSU1"],
}

SAMP_CFG = {
    "mode": "SAMP",
    "channels": {
        "SMU1": {
            "v_name": "V1",
            "i_name": "I1",
            "function": "CONS",
            "smu_mode": "V",
            "standby": "OFF",
        },
        "SMU2": {"disable": 1},
        "SMU3": {"disable": 1},
        "SMU4": {"disable": 1},
        "VMU1": {"v_name": "VMU1", "vmu_mode": "DVOL"},
        "VMU2": {"disable": 1},
        "VSU1": {"v_name": "VSU1", "function": "CONS"},
        "VSU2": {"disable": 1},
    },
    "measurement_setup": {
        "integration_mode": "SHORT",
        "short_time": 8e-5,
        "long_time_cycles": 2,
        "wait_time": 0.0,
        "ranges": {
            "SMU1": {"mode": "AUTO"},
            "VMU1": {"mode": "FIX", "value": 2.0},
        },
    },
    "sampling_setup": {
        "mode": "THINNEDOUT",
        "hold_time": 0.0,
        "initial_interval": 0.00072,
        "points": 100,
        "filter": "ON",
        "period": 10.0,
        "period_auto": "OFF",
        "scon": {
            "state": "ON",
            "name": "I1",
            "threshold": 0.01,
            "event": "ABSHIGH",
            "event_count": 5,
            "enable_delay": 0.0,
        },
        "constants": {
            "SMU1": {"source": 0.0, "compliance": 0.01},
            "VSU1": {"source": 1.0},
        },
    },
    "display_vars": ["@TIME", "@INDEX", "I1", "VMU1"],
}

# Sampling variants exercising the remaining period branches.
SAMP_AUTO = {
    **{k: v for k, v in SAMP_CFG.items() if k != "sampling_setup"},
    "sampling_setup": {
        "mode": "LINEAR",
        "hold_time": 0.0,
        "initial_interval": 0.002,
        "points": 11,
        "filter": "OFF",
        "period_auto": "ON",
        "scon": {"state": "OFF"},
    },
}
SAMP_NOLIMIT = {
    **{k: v for k, v in SAMP_CFG.items() if k != "sampling_setup"},
    "sampling_setup": {
        "mode": "LINEAR",
        "hold_time": 0.0,
        "initial_interval": 0.002,
        "points": 11,
        "filter": "ON",
        "period": "INFINITY",
        "period_auto": "OFF",
        "scon": {"state": "OFF"},
    },
}
SAMP_LOG = {
    **{k: v for k, v in SAMP_CFG.items() if k != "sampling_setup"},
    "sampling_setup": {
        # Log mode -> no period keys at all.
        "mode": "L10",
        "hold_time": 0.0,
        "initial_interval": 0.00056,
        "points": 11,
        "filter": "ON",
        "scon": {"state": "OFF"},
    },
}

_SWEEP_NAME = "sweep_full"

EXPECTED_VARIABLE_COUNT = 3
EXPECTED_LAST_POINT_VALUE = 1.5
EXPECTED_LOG_MESSAGE_COUNT = 2

_RESULTS = {
    "V1": [0.0, 0.5, 1.0],
    "I1": [1e-3, 2e-3, 3e-3],
    "VMU1": [0.1, 0.2, 0.3, 0.4],
}


@pytest.fixture
def db(tmp_path):
    database = ProjectDatabase.create_new(
        tmp_path / f"project{PROJECT_EXTENSION}"
    )
    yield database
    database.close()


@pytest.fixture
def sweep_db(db):
    """A database holding the canonical sweep setup, ready for executions."""
    _add_setup(db, SWEEP_CFG, _SWEEP_NAME)
    return db


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def _add_setup(db, cfg, name) -> None:
    with db.session() as s:
        s.add(config_dict_to_setup(cfg, name=name, instrument_model="4156C"))


def _get_setup(session, name) -> MeasurementSetup:
    return session.scalars(
        select(MeasurementSetup).where(MeasurementSetup.name == name)
    ).one()


def _get_execution(session, name) -> MeasurementExecution:
    return session.scalars(
        select(MeasurementExecution).where(MeasurementExecution.name == name)
    ).one()


def _add_execution(
    db, results, *, name, setup_name=_SWEEP_NAME, model="4156C", **kwargs
) -> None:
    with db.session() as s:
        s.add(
            fetch_result_to_execution(
                results,
                setup=_get_setup(s, setup_name),
                name=name,
                instrument_model=model,
                **kwargs,
            )
        )


def test_create_new_builds_schema_with_queryable_tables(db, tmp_path):
    assert (tmp_path / f"project{PROJECT_EXTENSION}").exists()
    with db.session() as s:
        assert _count(s, MeasurementSetup) == 0


@pytest.mark.parametrize(
    ("name", "cfg"),
    [
        ("sweep_full", SWEEP_CFG),
        ("samp_numeric", SAMP_CFG),
        ("samp_auto", SAMP_AUTO),
        ("samp_nolimit", SAMP_NOLIMIT),
        ("samp_log", SAMP_LOG),
    ],
)
def test_config_dict_round_trips_through_the_orm(db, name, cfg):
    """Persist a config dict, reload from disk, assert exact dict equality."""
    _add_setup(db, cfg, name)

    with db.session() as s:
        assert setup_to_config_dict(_get_setup(s, name)) == cfg


def test_multi_variable_execution_round_trips(sweep_db):
    _add_execution(sweep_db, _RESULTS, name="run_001", model="4155C")

    with sweep_db.session() as s:
        execution = _get_execution(s, "run_001")
        assert len(execution.variables) == EXPECTED_VARIABLE_COUNT
        assert execution_to_data_dict(execution) == _RESULTS
        assert execution.instrument_model == "4155C"


def test_execution_stamps_the_setup_last_execution_date(sweep_db):
    with sweep_db.session() as s:
        assert _get_setup(s, _SWEEP_NAME).last_execution_date is None

    _add_execution(sweep_db, _RESULTS, name="run_001")

    with sweep_db.session() as s:
        assert _get_execution(s, "run_001").setup.last_execution_date


def test_non_finite_data_points_persist_as_null(sweep_db):
    _add_execution(
        sweep_db,
        {"V1": [0.0, float("nan"), float("inf"), 1.5]},
        name="run_nan",
    )

    with sweep_db.session() as s:
        execution = _get_execution(s, "run_nan")
        points = execution.variables[0].data_points
        assert points[0].value == 0.0
        assert points[1].value is None, "NaN should store as NULL"
        assert points[2].value is None, "inf should store as NULL"
        assert points[3].value == EXPECTED_LAST_POINT_VALUE

        recon = execution_to_data_dict(execution)["V1"]
        assert math.isnan(recon[1])
        assert math.isnan(recon[2])


def test_log_messages_link_to_an_execution_or_the_project(sweep_db):
    _add_execution(sweep_db, _RESULTS, name="run_001")

    with sweep_db.session() as s:
        execution = _get_execution(s, "run_001")
        s.add(LogMessage(message="run finished", execution_id=execution.id))
        s.add(LogMessage(message="project opened"))  # execution_id is NULL

    with sweep_db.session() as s:
        assert _count(s, LogMessage) == EXPECTED_LOG_MESSAGE_COUNT
        linked = s.scalars(
            select(LogMessage).where(LogMessage.execution_id.is_not(None))
        ).all()
        unlinked = s.scalars(
            select(LogMessage).where(LogMessage.execution_id.is_(None))
        ).all()
        assert len(linked) == 1
        assert len(unlinked) == 1


def test_execution_count_derives_from_associated_executions(sweep_db):
    with sweep_db.session() as s:
        assert _get_setup(s, _SWEEP_NAME).execution_count == 0

    _add_execution(sweep_db, {"V1": [0.0]}, name="run_002", is_synthetic=True)

    with sweep_db.session() as s:
        assert _get_setup(s, _SWEEP_NAME).execution_count == 1


def test_deleting_a_setup_cascades_to_executions_and_data(sweep_db):
    """Relies on PRAGMA foreign_keys=ON + passive_deletes."""
    _add_execution(sweep_db, _RESULTS, name="run_001")
    with sweep_db.session() as s:
        execution = _get_execution(s, "run_001")
        s.add(LogMessage(message="run finished", execution_id=execution.id))
        s.add(LogMessage(message="project opened"))

    with sweep_db.session() as s:
        s.delete(_get_setup(s, _SWEEP_NAME))

    with sweep_db.session() as s:
        assert _count(s, MeasurementExecution) == 0, "executions not cascaded"
        assert _count(s, ExecutionVariable) == 0, "variables not cascaded"
        assert _count(s, DataPoint) == 0, "data points not cascaded"
        # The execution-linked log message cascaded; the project log remains.
        assert _count(s, LogMessage) == 1, "execution log not cascaded"


def test_duplicate_setup_name_is_rejected(db):
    _add_setup(db, SAMP_CFG, "samp_numeric")

    with pytest.raises(IntegrityError):
        _add_setup(db, SAMP_AUTO, "samp_numeric")


def test_duplicate_execution_name_is_rejected(sweep_db):
    _add_setup(sweep_db, SAMP_CFG, "samp_numeric")
    _add_execution(sweep_db, {"I1": [0.0]}, name="dup_run")

    with pytest.raises(IntegrityError):
        _add_execution(
            sweep_db,
            {"I1": [0.0]},
            name="dup_run",
            setup_name="samp_numeric",
        )
