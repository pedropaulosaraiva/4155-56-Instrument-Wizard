"""
db/base.py
----------
SQLAlchemy 2.0 declarative base for the per-project SQLite database.

Layer contract
--------------
The whole ``db/`` package is framework-agnostic (SQLAlchemy + stdlib only) —
no PySide6 imports.  It is the persistence sibling of ``models/`` and stays
unit-testable without a graphical context.  ORM classes live here (not in
``models/``) so that the pure value-object modules in ``models/`` remain free
of ``Base.metadata`` import-time state, and so the existing
``models.sweep_config.MeasurementSetup`` dataclass does not collide with the
ORM root of the same conceptual name.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every ORM table in the project database."""
