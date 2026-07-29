"""
test/models/test_file_dialogs.py
--------------------------------
Directory-resolution logic behind the shared file dialogs.

Only the Qt-free half of ``extra_widgets/file_dialogs.py`` is exercised — the
home-directory fallback chain and the per-purpose session memory.  The three
``get_*_path`` wrappers open native modal dialogs and are left to manual
verification.
"""

from pathlib import Path

import pytest

from wizard_4155_4156.extra_widgets.file_dialogs import (
    DialogPurpose,
    _initial_selection,
    remember_directory,
    reset_directories,
    start_directory,
    user_home_directory,
)


@pytest.fixture(autouse=True)
def _clean_session():
    """Every test starts and ends with no remembered folders."""
    reset_directories()
    yield
    reset_directories()


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect ``Path.home()`` at a real temporary directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    return home


# ── Home directory ───────────────────────────────────────────────────────────


def test_home_is_used_when_nothing_remembered(fake_home):
    assert user_home_directory() == str(fake_home)
    assert start_directory(DialogPurpose.PROJECT) == str(fake_home)


def test_home_never_falls_back_to_the_working_directory(fake_home):
    """The bug being fixed: dialogs must not open in the CWD."""
    assert start_directory(DialogPurpose.GRAPH_EXPORT) != str(Path.cwd())


def test_unresolvable_home_does_not_raise(monkeypatch):
    def _boom(_cls):
        raise RuntimeError("no home directory")

    monkeypatch.setattr(Path, "home", classmethod(_boom))
    # Qt's HomeLocation or "" — either way, never an exception and never a
    # path that does not exist.
    result = user_home_directory()
    assert result == "" or Path(result).is_dir()


def test_missing_home_directory_is_not_returned(tmp_path, monkeypatch):
    ghost = tmp_path / "deleted-home"  # never created
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: ghost))
    assert user_home_directory() != str(ghost)


# ── Session memory ───────────────────────────────────────────────────────────


def test_remembers_the_folder_of_the_last_file(fake_home, tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()

    remember_directory(DialogPurpose.TABLE_EXPORT, str(exports / "data.csv"))

    assert start_directory(DialogPurpose.TABLE_EXPORT) == str(exports)


def test_purposes_do_not_leak_into_each_other(fake_home, tmp_path):
    graphs = tmp_path / "graphs"
    graphs.mkdir()

    remember_directory(DialogPurpose.GRAPH_EXPORT, str(graphs / "plot.png"))

    assert start_directory(DialogPurpose.GRAPH_EXPORT) == str(graphs)
    for other in (
        DialogPurpose.PROJECT,
        DialogPurpose.IMPORT,
        DialogPurpose.TABLE_EXPORT,
    ):
        assert start_directory(other) == str(fake_home)


def test_cancelled_dialog_changes_nothing(fake_home):
    remember_directory(DialogPurpose.IMPORT, "")
    assert start_directory(DialogPurpose.IMPORT) == str(fake_home)


def test_deleted_folder_falls_back_to_home(fake_home, tmp_path):
    gone = tmp_path / "removable-drive"
    gone.mkdir()
    remember_directory(DialogPurpose.PROJECT, str(gone / "study.wiz4155"))
    assert start_directory(DialogPurpose.PROJECT) == str(gone)

    gone.rmdir()  # drive unmounted / folder deleted mid-session

    assert start_directory(DialogPurpose.PROJECT) == str(fake_home)


def test_reset_clears_every_purpose(fake_home, tmp_path):
    for purpose in DialogPurpose:
        remember_directory(purpose, str(tmp_path / "x.txt"))

    reset_directories()

    for purpose in DialogPurpose:
        assert start_directory(purpose) == str(fake_home)


# ── Suggested filename ───────────────────────────────────────────────────────


def test_suggested_name_is_joined_onto_the_start_directory(fake_home):
    selection = _initial_selection(DialogPurpose.GRAPH_EXPORT, "plot.png")
    assert selection == str(fake_home / "plot.png")


def test_no_suggested_name_yields_the_bare_directory(fake_home):
    assert _initial_selection(DialogPurpose.PROJECT, "") == str(fake_home)


def test_suggested_name_survives_an_unresolvable_home(monkeypatch):
    monkeypatch.setattr(
        "wizard_4155_4156.extra_widgets.file_dialogs.start_directory",
        lambda _purpose: "",
    )
    assert _initial_selection(DialogPurpose.PROJECT, "new.wiz4155") == (
        "new.wiz4155"
    )
