"""
presenters/home_presenter.py
-----------------------------
Presenter for the home page in the MVP triad.

Responsibilities
----------------
- Subscribe to HomePageView signals (user intents).
- Mutate RecentProjectsManager (model) in response.
- Push updated state back to HomePageView via display_* methods.
- Emit project_file_opened so MainWindow can react (load editor, etc.).

The presenter holds references to both model and view but owns neither —
lifetime is managed by MainWindow.
"""
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from wizard_4155_4156.models.project import RecentProjectsManager
from wizard_4155_4156.views.pages.home_page import HomePageView


class HomePresenter(QObject):
    """
    Wires HomePageView ↔ RecentProjectsManager.

    Signals
    -------
    project_file_opened(str)
        Emitted after a project path is confirmed (card click or file dialog).
        MainWindow connects this to its own open-project logic.
    new_project_triggered()
        Emitted when the user requests a new project.
        MainWindow connects this to switch to the editor page.
    """

    project_file_opened = Signal(str)
    new_project_triggered = Signal()

    def __init__(
        self,
        view: HomePageView,
        model: RecentProjectsManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._model = model
        self._connect_signals()
        self._refresh_view()

    # ── Public API ───────────────────────────────────────────────────────────

    def register_opened_file(self, path: str, name: str | None = None) -> None:
        """
        Call after MainWindow successfully opens a project file so the
        model and view stay in sync.
        """
        self._model.add_project(path, name)
        self._refresh_view()

    # ── Private ──────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.new_project_requested.connect(self._on_new_project)
        self._view.open_project_requested.connect(self._on_open_project)
        self._view.project_opened.connect(self._on_project_opened)
        self._view.project_remove_requested.connect(self._on_remove_project)
        self._view.clear_history_requested.connect(self._on_clear_history)

    def _refresh_view(self) -> None:
        self._view.display_recent_projects(self._model.get_projects())

    # ── Signal handlers ──────────────────────────────────────────────────────

    def _on_new_project(self) -> None:
        self.new_project_triggered.emit()

    def _on_open_project(self) -> None:
        """Show OS file dialog; if a file is chosen treat it as opened."""
        path, _ = QFileDialog.getOpenFileName(
            self._view,
            "Open Project",
            "",
            "Project Files (*.yaml *.yml *.json);;All Files (*.*)",
        )
        if path:
            self._on_project_opened(path)

    def _on_project_opened(self, path: str) -> None:
        self._model.add_project(path)
        self._refresh_view()
        self.project_file_opened.emit(path)

    def _on_remove_project(self, path: str) -> None:
        self._model.remove_project(path)
        self._refresh_view()

    def _on_clear_history(self) -> None:
        self._model.clear_all()
        self._refresh_view()
