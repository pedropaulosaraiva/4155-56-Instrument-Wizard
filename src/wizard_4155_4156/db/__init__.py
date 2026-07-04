"""
db/
---
Per-project SQLite persistence layer (SQLAlchemy 2.0).

Public API surface re-exported for convenience.  No PySide6 imports anywhere
in this package — it is the persistence sibling of ``models/``.
"""

from wizard_4155_4156.db.assembler import (
    config_dict_to_setup,
    execution_to_data_dict,
    fetch_result_to_execution,
    setup_to_config_dict,
)
from wizard_4155_4156.db.base import Base
from wizard_4155_4156.db.engine import (
    PROJECT_EXTENSION,
    ProjectDatabase,
    ProjectManager,
)

__all__ = [
    "Base",
    "ProjectDatabase",
    "ProjectManager",
    "PROJECT_EXTENSION",
    "config_dict_to_setup",
    "setup_to_config_dict",
    "fetch_result_to_execution",
    "execution_to_data_dict",
]
