"""
db/engine.py
------------
Per-project SQLite engine + session lifecycle.

Each project is a single standalone SQLite database file (custom ``.wiz4155``
extension).  ``ProjectDatabase`` wraps one engine; ``ProjectManager`` owns the
*currently open* project and swaps engines when the user opens/creates another.

Layer contract: no PySide6 imports — this is pure persistence infrastructure.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Importing schema registers every table on Base.metadata.
from wizard_4155_4156.db import schema  # noqa: F401
from wizard_4155_4156.db.base import Base

#: Canonical project-file extension (SQLite under the hood).
PROJECT_EXTENSION: str = ".wiz4155"


def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    """
    Enable SQLite foreign-key enforcement for every new connection.

    SQLite leaves ``PRAGMA foreign_keys`` OFF by default and the setting is
    per-connection, so without this hook ``ondelete="CASCADE"`` would silently
    no-op.  This is the single most important correctness detail of the layer.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class ProjectDatabase:
    """A single open project database (one SQLite file)."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(Path(db_path))
        self._engine: Engine = create_engine(
            f"sqlite:///{self._path}", future=True
        )
        event.listen(self._engine, "connect", _enable_sqlite_fk)
        # Idempotent — creates any missing tables, tolerant of existing files.
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(
            bind=self._engine, expire_on_commit=False, future=True
        )

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return Path(self._path).stem

    @property
    def engine(self) -> Engine:
        return self._engine

    # ── Session access ───────────────────────────────────────────────────────

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Context-managed session: commits on success, rolls back on error."""
        sess = self._Session()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def new_session(self) -> Session:
        """A bare session the caller is responsible for closing."""
        return self._Session()

    def close(self) -> None:
        self._engine.dispose()

    # ── Constructors ─────────────────────────────────────────────────────────

    @classmethod
    def create_new(cls, db_path: str | Path) -> "ProjectDatabase":
        """Create a fresh project file (parent dirs created as needed)."""
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(path)

    @classmethod
    def open_existing(cls, db_path: str | Path) -> "ProjectDatabase":
        """Open an existing project file; raises if it is missing."""
        path = Path(db_path)
        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")
        return cls(path)


class ProjectManager:
    """
    Holds the *currently open* project database.

    Qt-free, mirroring ``RecentProjectsManager`` in ``models/project.py`` — the
    presenter/MainWindow layer owns one instance and swaps projects through it.
    """

    def __init__(self) -> None:
        self._current: Optional[ProjectDatabase] = None

    @property
    def current_db(self) -> Optional[ProjectDatabase]:
        return self._current

    @property
    def is_open(self) -> bool:
        return self._current is not None

    @property
    def current_name(self) -> Optional[str]:
        return self._current.name if self._current else None

    def create(self, db_path: str | Path) -> ProjectDatabase:
        """Create a new project and make it current."""
        self.close()
        self._current = ProjectDatabase.create_new(db_path)
        return self._current

    def open(self, db_path: str | Path) -> ProjectDatabase:
        """Open an existing project and make it current."""
        self.close()
        self._current = ProjectDatabase.open_existing(db_path)
        return self._current

    def close(self) -> None:
        """Dispose the current project engine, if any."""
        if self._current is not None:
            self._current.close()
            self._current = None
