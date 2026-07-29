"""
extra_widgets/file_dialogs.py
-----------------------------
Single entry point for every native file dialog in the application.

Two problems this solves:

1. **Default directory.**  A bare ``QFileDialog.getSaveFileName(parent, title,
   "", filter)`` leaves Qt to fall back on the *process working directory* —
   the repo root when running from source, the folder holding the ``.exe``
   under a Nuitka build.  Neither is where a user keeps measurement data.
   Every dialog here starts in the **user home directory**, resolved through
   ``Path.home()`` (``%USERPROFILE%`` on Windows, ``$HOME`` on Linux) so the
   behaviour is identical from source and from a compiled executable — nothing
   is derived from ``__file__`` or ``sys.executable``.

2. **Session memory.**  Each *purpose* (roughly, each page) remembers the
   folder its last confirmed dialog used, so a second export lands beside it.
   The memory is module level and deliberately **not** persisted: it lives only
   as long as the process, matching the ``_QuickMismatchState`` precedent in
   ``presenters/live_run_helper.py``.  Persisted preferences belong in
   ``db/global_settings.py``; this is not one of them.

Cancelled dialogs never update the memory.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QWidget


class DialogPurpose(StrEnum):
    """A group of dialogs sharing one remembered directory."""

    PROJECT = "project"  # New Project · Open Project
    IMPORT = "import"  # Import Setup · Import Run
    GRAPH_EXPORT = "graph_export"  # Plot PNG · Scene PNG · CSV · XLSX
    TABLE_EXPORT = "table_export"  # Save Execution · Save All (.zip)


#: Last confirmed directory per purpose — session only, never written to disk.
_last_directory: dict[DialogPurpose, str] = {}


# =============================================================================
# Directory resolution
# =============================================================================


def user_home_directory() -> str:
    """The user's home folder, or the best available substitute.

    ``Path.home()`` raises ``RuntimeError`` when neither ``HOME`` nor the
    Windows profile variables resolve; Qt's own lookup is tried next, and an
    empty string (Qt picks its default) is the final fallback so a dialog is
    never opened on a non-existent path.
    """
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    if home is not None and home.is_dir():
        return str(home)

    qt_home = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.HomeLocation
    )
    if qt_home and Path(qt_home).is_dir():
        return qt_home
    return ""


def start_directory(purpose: DialogPurpose) -> str:
    """Folder the next *purpose* dialog should open in.

    The remembered folder is dropped if it no longer exists (deleted or an
    unmounted drive) — otherwise the dialog would open on a dead path.
    """
    remembered = _last_directory.get(purpose)
    if remembered and Path(remembered).is_dir():
        return remembered
    return user_home_directory()


def remember_directory(purpose: DialogPurpose, path: str) -> None:
    """Record the folder containing *path* as the next start point."""
    if not path:
        return
    _last_directory[purpose] = str(Path(path).parent)


def reset_directories() -> None:
    """Forget every remembered folder (test hook)."""
    _last_directory.clear()


def _initial_selection(purpose: DialogPurpose, suggested_name: str) -> str:
    """Qt's ``dir`` argument: a folder, or a full path pre-filling the name."""
    directory = start_directory(purpose)
    if not suggested_name:
        return directory
    if not directory:
        return suggested_name
    return str(Path(directory) / suggested_name)


# =============================================================================
# Dialog wrappers
# =============================================================================


def get_save_path(
    parent: Optional[QWidget],
    purpose: DialogPurpose,
    title: str,
    file_filter: str,
    suggested_name: str = "",
) -> str:
    """Ask where to save.  Returns "" if the user cancelled."""
    path, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        title,
        _initial_selection(purpose, suggested_name),
        file_filter,
    )
    remember_directory(purpose, path)
    return path


def get_open_path(
    parent: Optional[QWidget],
    purpose: DialogPurpose,
    title: str,
    file_filter: str,
) -> str:
    """Ask for one existing file.  Returns "" if the user cancelled."""
    path, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        title,
        start_directory(purpose),
        file_filter,
    )
    remember_directory(purpose, path)
    return path


def get_open_paths(
    parent: Optional[QWidget],
    purpose: DialogPurpose,
    title: str,
    file_filter: str,
) -> list[str]:
    """Ask for one or more existing files.  Returns [] if cancelled."""
    paths, _selected_filter = QFileDialog.getOpenFileNames(
        parent,
        title,
        start_directory(purpose),
        file_filter,
    )
    if paths:
        # A multi-selection is always inside one folder — the first is enough.
        remember_directory(purpose, paths[0])
    return paths
