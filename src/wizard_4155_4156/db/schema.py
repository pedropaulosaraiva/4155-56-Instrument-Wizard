"""
db/schema.py
------------
Fully-normalized SQLAlchemy 2.0 ORM schema for a project database.

Design notes
------------
* The core "Setup Data" is normalized into explicit tables/columns — there are
  NO JSON blobs anywhere in this schema.  JSON is reserved for the
  recent-projects list and global settings (handled outside the DB).
* ``MeasurementSetup`` uses **joined-table inheritance** with the ``setup_type``
  discriminator (SWEEP / SAMP / QSCV / HYST).  Metadata and the data shared by
  every mode (channels, integration timing, ranges, constants, display vars)
  live on the base table; mode-specific rows live in the subtype tables.
* Channels are stored in ONE generic ``channel`` table keyed by
  (``unit_kind``, ``unit_index``) with kind-specific nullable columns.  This
  mirrors the runtime ``active_channels`` dicts the presenters build and keeps
  the dict<->ORM assembler simple.
* String columns store the canonical SCPI/JSON tokens verbatim (e.g.
  ``"CONS"``, ``"VAR1"``, ``"AUTO"``), so the assembler never has to translate
  enum names.  NULL columns encode "key omitted in the JSON" (e.g. a sweep VAR
  driven by a VSU has no ``compliance``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wizard_4155_4156.db.base import Base


def _now() -> datetime:
    return datetime.now()


# =============================================================================
# Measurement Setup (joined-table inheritance root)
# =============================================================================


class MeasurementSetup(Base):
    """
    A saved measurement setup.  The base table holds metadata and every
    sub-object shared by all measurement modes.  Concrete modes are subclasses
    (``SweepSetup``, ``SamplingSetup``, ``QscvSetup``, ``HysteresisSetup``).
    """

    __tablename__ = "measurement_setup"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(default=None)
    creation_date: Mapped[datetime] = mapped_column(default=_now)
    last_execution_date: Mapped[Optional[datetime]] = mapped_column(default=None)
    author: Mapped[Optional[str]] = mapped_column(default=None)
    organization: Mapped[Optional[str]] = mapped_column(default=None)
    instrument_model: Mapped[str] = mapped_column()
    setup_type: Mapped[str] = mapped_column(index=True)

    # Channel-page level flags (not part of the measurement-config JSON; stored
    # for completeness, defaulted from ChannelsConfig).
    interlock_open: Mapped[bool] = mapped_column(default=True)
    common_to_ground: Mapped[bool] = mapped_column(default=True)

    # ── Shared sub-objects ───────────────────────────────────────────────────
    channels: Mapped[list["Channel"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Channel.unit_kind, Channel.unit_index",
    )
    timing: Mapped[Optional["MeasurementTiming"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    ranges: Mapped[list["RangeSetting"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    constants: Mapped[list["ConstantSource"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    display_vars: Mapped[list["DisplayVar"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DisplayVar.position",
    )
    executions: Mapped[list["MeasurementExecution"]] = relationship(
        back_populates="setup",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MeasurementExecution.execution_date",
    )
    # Ordered child steps — only populated for HYST containers.
    hysteresis_steps: Mapped[list["HysteresisStep"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="HysteresisStep.parent_setup_id",
        order_by="HysteresisStep.position",
    )

    __mapper_args__ = {
        "polymorphic_on": setup_type,
        "polymorphic_identity": "SETUP",
    }

    @property
    def execution_count(self) -> int:
        """Derived count of associated executions (never stored)."""
        return len(self.executions)


class Channel(Base):
    """One physical source/measure unit slot (SMU1-4 / VMU1-2 / VSU1-2)."""

    __tablename__ = "channel"
    __table_args__ = (
        UniqueConstraint("setup_id", "unit_kind", "unit_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    unit_kind: Mapped[str] = mapped_column()  # SMU / VMU / VSU
    unit_index: Mapped[int] = mapped_column()  # 1..4 / 1..2
    disabled: Mapped[bool] = mapped_column(default=False)

    # Kind-gated nullable columns.
    v_name: Mapped[Optional[str]] = mapped_column(default=None)
    i_name: Mapped[Optional[str]] = mapped_column(default=None)  # SMU only
    function: Mapped[Optional[str]] = mapped_column(default=None)  # SMU/VSU
    smu_mode: Mapped[Optional[str]] = mapped_column(default=None)  # SMU
    vmu_mode: Mapped[Optional[str]] = mapped_column(default=None)  # VMU
    standby: Mapped[Optional[bool]] = mapped_column(default=None)  # SMU

    setup: Mapped[MeasurementSetup] = relationship(back_populates="channels")

    @property
    def unit_id(self) -> str:
        return f"{self.unit_kind}{self.unit_index}"


class MeasurementTiming(Base):
    """The shared ``measurement_setup`` integration block (1:1 with a setup)."""

    __tablename__ = "measurement_timing"

    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    integration_mode: Mapped[str] = mapped_column()  # SHOR / MED / LONG
    short_time: Mapped[float] = mapped_column()
    long_time_cycles: Mapped[int] = mapped_column()
    wait_time: Mapped[float] = mapped_column()  # wait multiplier

    setup: Mapped[MeasurementSetup] = relationship(back_populates="timing")


class RangeSetting(Base):
    """Per measurement-unit range entry (``measurement_setup.ranges``)."""

    __tablename__ = "range_setting"
    __table_args__ = (UniqueConstraint("setup_id", "unit_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[str] = mapped_column()  # e.g. "SMU1", "VMU1"
    mode: Mapped[str] = mapped_column()  # AUTO / FIX / LIM
    value: Mapped[Optional[float]] = mapped_column(default=None)  # NULL for AUTO

    setup: Mapped[MeasurementSetup] = relationship(back_populates="ranges")


class ConstantSource(Base):
    """Per-unit constant source entry (CONST units, non-COMM)."""

    __tablename__ = "constant_source"
    __table_args__ = (UniqueConstraint("setup_id", "unit_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    unit_id: Mapped[str] = mapped_column()
    source: Mapped[Optional[float]] = mapped_column(default=None)
    compliance: Mapped[Optional[float]] = mapped_column(default=None)  # VSU=NULL

    setup: Mapped[MeasurementSetup] = relationship(back_populates="constants")


class DisplayVar(Base):
    """One of up to eight ordered display variables for a setup."""

    __tablename__ = "display_var"
    __table_args__ = (UniqueConstraint("setup_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column()
    var_name: Mapped[str] = mapped_column()

    setup: Mapped[MeasurementSetup] = relationship(back_populates="display_vars")


# =============================================================================
# Sweep subtype
# =============================================================================


class SweepSetup(MeasurementSetup):
    """Native staircase-sweep measurement (``mode == "SWEEP"``)."""

    __tablename__ = "sweep_setup"

    id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"),
        primary_key=True,
    )
    delay: Mapped[float] = mapped_column(default=0.0)
    hold_time: Mapped[float] = mapped_column(default=0.0)
    sweep_stop: Mapped[str] = mapped_column(default="COMPLIANCE")

    var1: Mapped[Optional["SweepVar1"]] = relationship(
        back_populates="sweep",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    var2: Mapped[Optional["SweepVar2"]] = relationship(
        back_populates="sweep",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    vard: Mapped[Optional["SweepVard"]] = relationship(
        back_populates="sweep",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    __mapper_args__ = {"polymorphic_identity": "SWEEP"}


class SweepVar1(Base):
    """Primary sweep variable (VAR1)."""

    __tablename__ = "sweep_var1"

    id: Mapped[int] = mapped_column(primary_key=True)
    sweep_id: Mapped[int] = mapped_column(
        ForeignKey("sweep_setup.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    mode: Mapped[str] = mapped_column()  # SINGLE / DOUBLE
    spacing: Mapped[str] = mapped_column()  # LINEAR / L10 / L25 / L50
    start: Mapped[float] = mapped_column()
    stop: Mapped[float] = mapped_column()
    step: Mapped[float] = mapped_column()
    compliance: Mapped[Optional[float]] = mapped_column(default=None)
    pcompliance: Mapped[Optional[float]] = mapped_column(default=None)

    sweep: Mapped[SweepSetup] = relationship(back_populates="var1")


class SweepVar2(Base):
    """Secondary sweep variable (VAR2)."""

    __tablename__ = "sweep_var2"

    id: Mapped[int] = mapped_column(primary_key=True)
    sweep_id: Mapped[int] = mapped_column(
        ForeignKey("sweep_setup.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    start: Mapped[float] = mapped_column()
    step: Mapped[float] = mapped_column()
    points: Mapped[int] = mapped_column()
    compliance: Mapped[Optional[float]] = mapped_column(default=None)
    pcompliance: Mapped[Optional[float]] = mapped_column(default=None)

    sweep: Mapped[SweepSetup] = relationship(back_populates="var2")


class SweepVard(Base):
    """Synchronized sweep variable (VAR1' / VARD)."""

    __tablename__ = "sweep_vard"

    id: Mapped[int] = mapped_column(primary_key=True)
    sweep_id: Mapped[int] = mapped_column(
        ForeignKey("sweep_setup.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    offset: Mapped[float] = mapped_column()
    ratio: Mapped[float] = mapped_column()
    compliance: Mapped[Optional[float]] = mapped_column(default=None)
    pcompliance: Mapped[Optional[float]] = mapped_column(default=None)

    sweep: Mapped[SweepSetup] = relationship(back_populates="vard")


# =============================================================================
# Sampling subtype
# =============================================================================


class SamplingSetup(MeasurementSetup):
    """Native time-sampling measurement (``mode == "SAMP"``)."""

    __tablename__ = "sampling_setup"

    id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mode: Mapped[str] = mapped_column(default="LINEAR")
    initial_interval: Mapped[float] = mapped_column(default=2e-3)
    points: Mapped[int] = mapped_column(default=11)
    hold_time: Mapped[float] = mapped_column(default=0.0)
    filter_on: Mapped[bool] = mapped_column(default=True)
    # period encoding: AUTO / NO_LIMIT / NUMERIC / NA (log modes -> NA)
    period_mode: Mapped[str] = mapped_column(default="AUTO")
    period_value: Mapped[Optional[float]] = mapped_column(default=None)

    stop_condition: Mapped[Optional["StopCondition"]] = relationship(
        back_populates="sampling",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    __mapper_args__ = {"polymorphic_identity": "SAMP"}


class StopCondition(Base):
    """Sampling stop condition (row present == enabled / ``scon.state == ON``)."""

    __tablename__ = "stop_condition"

    id: Mapped[int] = mapped_column(primary_key=True)
    sampling_id: Mapped[int] = mapped_column(
        ForeignKey("sampling_setup.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column()
    threshold: Mapped[float] = mapped_column()
    event: Mapped[str] = mapped_column()  # HIGH / LOW / ABSHIGH / ABSLOW
    event_count: Mapped[int] = mapped_column()
    enable_delay: Mapped[float] = mapped_column()

    sampling: Mapped[SamplingSetup] = relationship(
        back_populates="stop_condition"
    )


# =============================================================================
# QSCV subtype (placeholder for future quasi-static C-V)
# =============================================================================


class QscvSetup(MeasurementSetup):
    """Quasi-static C-V measurement — reserved placeholder."""

    __tablename__ = "qscv_setup"

    id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ac_level: Mapped[Optional[float]] = mapped_column(default=None)
    frequency: Mapped[Optional[float]] = mapped_column(default=None)

    __mapper_args__ = {"polymorphic_identity": "QSCV"}


# =============================================================================
# Hysteresis / emulated multi-step subtype (placeholder)
# =============================================================================


class HysteresisSetup(MeasurementSetup):
    """
    Emulated hysteresis container — reserved placeholder.

    A hysteresis run is a *series* of child setups (e.g. a 0->1->0 V sweep plus
    a 0->-1->0 V sweep) defined together.  The ordered children are modelled by
    ``HysteresisStep`` association rows; no presenter produces these yet.
    """

    __tablename__ = "hysteresis_setup"

    id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __mapper_args__ = {"polymorphic_identity": "HYST"}


class HysteresisStep(Base):
    """Ordered link from a hysteresis container to one child sub-setup."""

    __tablename__ = "hysteresis_step"
    __table_args__ = (UniqueConstraint("parent_setup_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    child_setup_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_setup.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column()
    label: Mapped[Optional[str]] = mapped_column(default=None)

    parent: Mapped[MeasurementSetup] = relationship(
        back_populates="hysteresis_steps",
        foreign_keys=[parent_setup_id],
    )
    child: Mapped[MeasurementSetup] = relationship(
        foreign_keys=[child_setup_id]
    )


# =============================================================================
# Executions (captured datasets)
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
    value: Mapped[float] = mapped_column()
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
