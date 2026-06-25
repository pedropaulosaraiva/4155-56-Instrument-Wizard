"""
presenters/documentation_presenter.py
--------------------------------------
Presenter for the Documentation window.

Owns the static documentation data (tree + page content from gui_text),
populates the tree once, and renders the selected page.  Pure glue between
``DocumentationWindow`` (view) and ``gui_text/documentation.py`` (content).
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from wizard_4155_4156.gui_text.documentation import (
    DOC_TREE,
    WELCOME_MD,
    DocTopic,
    get_doc_page,
)
from wizard_4155_4156.views.documentation_window import DocumentationWindow


class DocumentationPresenter(QObject):
    def __init__(
        self,
        view: DocumentationWindow,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._view.display_tree(DOC_TREE)
        self._view.topic_selected.connect(self._on_topic_selected)

    # ── Public API (called by MainWindow) ────────────────────────────────────

    def show_topic(self, topic: str, *, collapse: bool) -> None:
        """Select ``topic`` in the tree and render its page."""
        self._view.select_topic(topic, collapse=collapse)
        self._display(topic)

    def show_default(self) -> None:
        """Open with sections expanded on the welcome page."""
        self._view.expand_sections()
        self._view.display_page("Documentation", WELCOME_MD)

    # ── Signal handlers ──────────────────────────────────────────────────────

    def _on_topic_selected(self, topic: str) -> None:
        self._display(topic)

    # ── Private ──────────────────────────────────────────────────────────────

    def _display(self, topic: str) -> None:
        page = get_doc_page(DocTopic(topic))
        self._view.display_page(page.title, page.body)
