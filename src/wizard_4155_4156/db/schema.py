"""
db/schema.py
------------
SQLAlchemy 2.0 ORM schema for a project database.

Design
------
* A measurement **setup**'s configuration is stored verbatim as a single JSON
  column (``setup_data``).  The whole application already works with this data
  as a JSON dict (the config pages produce it via ``_build_json``, the
  directors consume it, and ``models/config_loader.py`` reloads it), so there
  is nothing to gain from shredding it into tables — and a lot of translation
  code to lose.  Emulated modes (hysteresis) and QSCV, when implemented, also
  live inside this JSON structure.
* Captured **execution** results stay normalized:
  ``measurement_execution`` → ``execution_variable`` → ``data_point`` — so
  individual points (with future ``status``/``accuracy`` flags) remain
  first-class rows.

No PySide6 imports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wizard_4155_4156.db.base import Base


def _now() -> datetime:
    return datetime.now()


# =============================================================================
# Measurement Setup (config stored as JSON)
# =============================================================================


class MeasurementSetup(Base):
    """A saved measurement setup: metadata columns + the config dict as JSON."""

    __tablename__ = "measurement_setup"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(default=None)
    creation_date: Mapped[datetime] = mapped_column(default=_now)
    last_execution_date: Mapped[Optional[datetime]] = mapped_column(default=None)
    author: Mapped[Optional[str]] = mapped_column(default=None)
    organization: Mapped[Optional[str]] = mapped_column(default=None)
    instrument_model: Mapped[str] = mapped_column()
    # SWEEP / SAMP / QSCV / HYST — set from the config dict's "mode"; a plain
    # column (not a polymorphic discriminator) for cheap list filtering.
    setup_type: Mapped[str] = mapped_column(index=True)

    # Channel-page flags (not part of the measurement-config JSON; kept for the
    # "copy to configuration" reconstruction).
    interlock_open: Mapped[bool] = mapped_column(default=True)
    common_to_ground: Mapped[bool] = mapped_column(default=True)

    # The canonical measurement-config dict, stored verbatim.
    setup_data: Mapped[dict] = mapped_column(JSON, default=dict)

    executions: Mapped[list["MeasurementExecution"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MeasurementExecution.execution_date",
    )

    @property
    def execution_count(self) -> int:
        """Derived count of associated executions (never stored)."""
        return len(self.executions)


# =============================================================================
# Executions (captured datasets — normalized)
# =============================================================================


class MeasurementExecution(Base):
    """A dataset captured by running a ``MeasurementSetup``."""

    __tablename__ = "measurement_execution"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(default=None)
    setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    execution_date: Mapped[datetime] = mapped_column(default=_now)
    instrument_model: Mapped[str] = mapped_column()  # may differ from setup
    is_synthetic: Mapped[bool] = mapped_column(default=False)

    setup: Mapped[MeasurementSetup] = relationship(back_populates="executions")
    variables: Mapped[list["ExecutionVariable"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExecutionVariable.position",
    )
    log_messages: Mapped[list["LogMessage"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LogMessage.timestamp",
    )


class ExecutionVariable(Base):
    """One measured variable inside an execution (up to eight per execution)."""

    __tablename__ = "execution_variable"
    __table_args__ = (UniqueConstraint("execution_id", "var_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_execution.id", ondelete="CASCADE"), index=True
    )
    var_name: Mapped[str] = mapped_column()
    position: Mapped[int] = mapped_column()

    execution: Mapped[MeasurementExecution] = relationship(
        back_populates="variables"
    )
    data_points: Mapped[list["DataPoint"]] = relationship(
        back_populates="variable",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DataPoint.point_index",
    )


class DataPoint(Base):
    """A single captured value for an execution variable."""

    __tablename__ = "data_point"
    __table_args__ = (UniqueConstraint("variable_id", "point_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    variable_id: Mapped[int] = mapped_column(
        ForeignKey("execution_variable.id", ondelete="CASCADE"), index=True
    )
    point_index: Mapped[int] = mapped_column()
    # Nullable: instruments may return non-finite points (overflow/oscillation),
    # and SQLite stores NaN/inf as NULL — so a missing/non-finite reading is NULL.
    value: Mapped[Optional[float]] = mapped_column(default=None)
    # Future fields (raw binary today carries no status/accuracy flags).
    status: Mapped[Optional[str]] = mapped_column(default=None)
    accuracy: Mapped[Optional[float]] = mapped_column(default=None)

    variable: Mapped[ExecutionVariable] = relationship(
        back_populates="data_points"
    )


class LogMessage(Base):
    """A log entry, optionally linked to a specific execution."""

    __tablename__ = "log_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column()
    timestamp: Mapped[datetime] = mapped_column(default=_now, index=True)
    execution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("measurement_execution.id", ondelete="CASCADE"),
        default=None,
        index=True,
    )

    execution: Mapped[Optional[MeasurementExecution]] = relationship(
        back_populates="log_messages"
    )


# =============================================================================
# Graphics info (future placeholder)
# =============================================================================


class GraphicsInfo(Base):
    """
    Reserved placeholder for saved dynamic graph configurations.

    Future updates will persist the dynamic graph settings used to display an
    execution (rather than static image files).  Kept intentionally minimal.
    """

    __tablename__ = "graphics_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("measurement_execution.id", ondelete="CASCADE"),
        default=None,
        index=True,
    )
    setup_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"),
        default=None,
        index=True,
    )
    x_var: Mapped[Optional[str]] = mapped_column(default=None)
    y_var: Mapped[Optional[str]] = mapped_column(default=None)
    axis_config: Mapped[Optional[str]] = mapped_column(default=None)
