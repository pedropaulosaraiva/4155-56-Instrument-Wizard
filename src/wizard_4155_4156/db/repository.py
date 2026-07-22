"""
db/repository.py
----------------
Thin CRUD service layer over the ORM, plus small Qt-free row DTOs.

The DTOs (``SetupRow`` / ``ExecRow``) let the Runs page *view* render setup and
execution lists without ever importing ORM classes — preserving the
passive-view contract (views never touch the model layer directly).  All
methods take an open ``Session`` so the presenter controls the transaction
boundary.  No PySide6 imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from wizard_4155_4156.db.schema import (
    ExecutionVariable,
    GraphScene,
    MeasurementExecution,
    MeasurementSetup,
)
from wizard_4155_4156.models.execution_time import format_execution_interval

#: Friendly labels for the ``setup_type`` discriminator.
SETUP_TYPE_LABELS: dict[str, str] = {
    "SWEEP": "Sweep",
    "SAMP": "Sampling",
    "QSCV": "QSCV",
    "HYST": "Hysteresis",
    "IMPORT": "Imported",
}


@dataclass(frozen=True)
class SetupRow:
    """Flat, detached snapshot of a setup for list display."""

    id: int
    name: str
    setup_type: str
    type_label: str
    instrument_model: str
    creation_date: datetime
    last_execution_date: Optional[datetime]
    execution_count: int
    description: str
    author: str
    organization: str
    #: Preformatted minimum-runtime label, e.g. "> 1.08 - 2.89 s" / "> 10 h" /
    #: "> indeterminate" (also shown for setups saved before runtime capture).
    runtime_label: str


@dataclass(frozen=True)
class ExecRow:
    """Flat, detached snapshot of an execution for list display."""

    id: int
    name: str
    execution_date: datetime
    instrument_model: str
    is_synthetic: bool
    variable_count: int
    description: str


@dataclass(frozen=True)
class GraphSceneRow:
    """Flat, detached snapshot of a persisted Graphs-page scene."""

    id: int
    name: str
    position: int
    scene_data: dict


def _to_setup_row(setup: MeasurementSetup) -> SetupRow:
    # Both bounds present ⇒ a real interval; otherwise indeterminate (also the
    # case for setups saved before runtime capture existed).
    runtime = (
        (setup.runtime_min, setup.runtime_max)
        if setup.runtime_min is not None and setup.runtime_max is not None
        else None
    )
    return SetupRow(
        id=setup.id,
        name=setup.name,
        setup_type=setup.setup_type,
        type_label=SETUP_TYPE_LABELS.get(setup.setup_type, setup.setup_type),
        instrument_model=setup.instrument_model,
        creation_date=setup.creation_date,
        last_execution_date=setup.last_execution_date,
        execution_count=len(setup.executions),
        description=setup.description or "",
        author=setup.author or "",
        organization=setup.organization or "",
        runtime_label=format_execution_interval(runtime),
    )


def _to_exec_row(execution: MeasurementExecution) -> ExecRow:
    return ExecRow(
        id=execution.id,
        name=execution.name,
        execution_date=execution.execution_date,
        instrument_model=execution.instrument_model,
        is_synthetic=execution.is_synthetic,
        variable_count=len(execution.variables),
        description=execution.description or "",
    )


class SetupRepository:
    """CRUD operations for measurement setups."""

    @staticmethod
    def list_rows(session: Session) -> list[SetupRow]:
        setups = session.scalars(
            select(MeasurementSetup).order_by(
                MeasurementSetup.creation_date.desc()
            )
        ).all()
        return [_to_setup_row(s) for s in setups]

    @staticmethod
    def get(session: Session, setup_id: int) -> Optional[MeasurementSetup]:
        return session.get(MeasurementSetup, setup_id)

    @staticmethod
    def add(session: Session, setup: MeasurementSetup) -> MeasurementSetup:
        session.add(setup)
        session.flush()
        return setup

    @staticmethod
    def name_exists(session: Session, name: str) -> bool:
        return (
            session.scalar(
                select(MeasurementSetup.id).where(
                    MeasurementSetup.name == name
                )
            )
            is not None
        )

    @staticmethod
    def update_metadata(
        session: Session,
        setup_id: int,
        name: str,
        description: Optional[str],
    ) -> None:
        setup = session.get(MeasurementSetup, setup_id)
        if setup is not None:
            setup.name = name
            setup.description = description

    @staticmethod
    def delete(session: Session, setup_id: int) -> None:
        setup = session.get(MeasurementSetup, setup_id)
        if setup is not None:
            session.delete(setup)


class ExecutionRepository:
    """CRUD operations for measurement executions."""

    @staticmethod
    def list_rows(session: Session, setup_id: int) -> list[ExecRow]:
        executions = session.scalars(
            select(MeasurementExecution)
            .where(MeasurementExecution.setup_id == setup_id)
            .order_by(MeasurementExecution.execution_date.desc())
        ).all()
        return [_to_exec_row(e) for e in executions]

    @staticmethod
    def get(
        session: Session, execution_id: int
    ) -> Optional[MeasurementExecution]:
        return session.get(MeasurementExecution, execution_id)

    @staticmethod
    def add(
        session: Session, execution: MeasurementExecution
    ) -> MeasurementExecution:
        session.add(execution)
        session.flush()
        return execution

    @staticmethod
    def name_exists(session: Session, name: str) -> bool:
        return (
            session.scalar(
                select(MeasurementExecution.id).where(
                    MeasurementExecution.name == name
                )
            )
            is not None
        )

    @staticmethod
    def delete(session: Session, execution_id: int) -> None:
        execution = session.get(MeasurementExecution, execution_id)
        if execution is not None:
            session.delete(execution)

    @staticmethod
    def delete_all(session: Session) -> int:
        """Delete every execution; return how many were removed.

        Children (variables, data points, log messages) are removed by the
        ``ON DELETE CASCADE`` foreign keys (``PRAGMA foreign_keys=ON`` is set
        per-connection).  Setups and graph scenes are left untouched; each
        setup's stale ``last_execution_date`` is cleared so the Runs page does
        not show a run timestamp for a setup that now has no runs.
        """
        count = session.scalar(
            select(func.count()).select_from(MeasurementExecution)
        )
        session.execute(delete(MeasurementExecution))
        session.execute(
            update(MeasurementSetup).values(last_execution_date=None)
        )
        return int(count or 0)

    @staticmethod
    def list_variable_names(session: Session, execution_id: int) -> list[str]:
        """Variable names of one execution, in captured order.

        Queries ``execution_variable`` only — never loads data points —
        so the Graphs page can run dataset-compatibility checks cheaply.
        """
        return list(
            session.scalars(
                select(ExecutionVariable.var_name)
                .where(ExecutionVariable.execution_id == execution_id)
                .order_by(ExecutionVariable.position)
            )
        )


class GraphSceneRepository:
    """Persistence of the Graphs-page scene list (one JSON row per scene).

    The scene list is small and fully presenter-owned, so the sync
    strategy is the simplest correct one: ``replace_all`` rewrites every
    row inside the caller's transaction.
    """

    @staticmethod
    def list_rows(session: Session) -> list[GraphSceneRow]:
        scenes = session.scalars(
            select(GraphScene).order_by(GraphScene.position)
        ).all()
        return [
            GraphSceneRow(
                id=s.id,
                name=s.name,
                position=s.position,
                scene_data=dict(s.scene_data),
            )
            for s in scenes
        ]

    @staticmethod
    def replace_all(session: Session, scenes: list[tuple[str, dict]]) -> None:
        """Overwrite the stored list with ``(name, scene_data)`` pairs."""
        for row in session.scalars(select(GraphScene)).all():
            session.delete(row)
        for position, (name, scene_data) in enumerate(scenes):
            session.add(
                GraphScene(name=name, position=position, scene_data=scene_data)
            )
