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

from sqlalchemy import select
from sqlalchemy.orm import Session

from wizard_4155_4156.db.schema import (
    MeasurementExecution,
    MeasurementSetup,
)

#: Friendly labels for the ``setup_type`` discriminator.
SETUP_TYPE_LABELS: dict[str, str] = {
    "SWEEP": "Sweep",
    "SAMP": "Sampling",
    "QSCV": "QSCV",
    "HYST": "Hysteresis",
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


def _to_setup_row(setup: MeasurementSetup) -> SetupRow:
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
