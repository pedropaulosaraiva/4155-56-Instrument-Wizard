"""
views/documentation_window.py
-----------------------------
Standalone Documentation window — pure View layer.

A non-modal window with a collapsible navigation tree on the left and a
Markdown content panel (``QTextBrowser``) on the right.  All content and tree
data is pushed in by ``DocumentationPresenter`` via the ``display_*`` API; the
view only emits ``topic_selected`` when the user clicks a tree entry.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocSection, DocTopic
from wizard_4155_4156.styles.stylesheets import (
    documentation_document_css,
    documentation_tree_stylesheet,
    documentation_viewer_stylesheet,
    documentation_window_stylesheet,
)

_TOPIC_ROLE = Qt.ItemDataRole.UserRole
_LABEL_ROLE = Qt.ItemDataRole.UserRole + 1

# Disclosure glyphs prefixed to the top-level section labels.
_ARROW_OPEN = "▾"  # subtopics shown
_ARROW_CLOSED = "▸"  # subtopics hidden


class DocumentationWindow(QMainWindow):
    """Tree (left) + Markdown viewer (right)."""

    topic_selected = Signal(str)  # DocTopic value

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Documentation — Wizard 4155/4156")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(documentation_window_stylesheet())
        # topic value → first tree item carrying it (shared topics map once).
        self._items: dict[str, QTreeWidgetItem] = {}
        self._build_ui()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        # Native branch arrows are replaced by glyphs in the section labels.
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(18)
        self._tree.setAnimated(True)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setStyleSheet(documentation_tree_stylesheet())
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemExpanded.connect(self._on_branch_toggled)
        self._tree.itemCollapsed.connect(self._on_branch_toggled)
        splitter.addWidget(self._tree)

        self._viewer = QTextBrowser()
        self._viewer.setOpenExternalLinks(True)
        self._viewer.setStyleSheet(documentation_viewer_stylesheet())
        splitter.addWidget(self._viewer)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 680])
        self.setCentralWidget(splitter)

    # ── Display API (called by presenter) ────────────────────────────────────

    def display_tree(self, sections: tuple[DocSection, ...]) -> None:
        self._tree.clear()
        self._items.clear()
        bold = QFont()
        bold.setBold(True)
        for section in sections:
            sect_item = QTreeWidgetItem(self._tree, [section.label])
            sect_item.setData(0, _TOPIC_ROLE, str(section.topic))
            sect_item.setData(0, _LABEL_ROLE, section.label)
            sect_item.setFont(0, bold)
            self._register(section.topic, sect_item)
            for node in section.children:
                child = QTreeWidgetItem(sect_item, [node.label])
                child.setData(0, _TOPIC_ROLE, str(node.topic))
                self._register(node.topic, child)
        self._refresh_section_arrows()

    def display_page(self, title: str, markdown: str) -> None:
        self.setWindowTitle(f"Documentation — {title}")
        # Set the document CSS before each render so headings/links/tables
        # follow the dark theme (QTextBrowser converts Markdown → HTML).
        self._viewer.document().setDefaultStyleSheet(
            documentation_document_css()
        )
        self._viewer.setMarkdown(markdown)
        self._viewer.verticalScrollBar().setValue(0)

    def select_topic(self, topic: str, *, collapse: bool) -> None:
        """Programmatically select ``topic``; collapse all but its path."""
        if collapse:
            self._tree.collapseAll()
        else:
            self.expand_sections()
        self._refresh_section_arrows()

        item = self._items.get(topic)
        if item is None:
            return
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        # Selecting must not echo back as a user click.
        self._tree.blockSignals(True)
        self._tree.setCurrentItem(item)
        self._tree.blockSignals(False)
        self._tree.scrollToItem(item)

    def expand_sections(self) -> None:
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setExpanded(True)
        self._refresh_section_arrows()

    # ── Private ──────────────────────────────────────────────────────────────

    def _register(self, topic: DocTopic, item: QTreeWidgetItem) -> None:
        self._items.setdefault(str(topic), item)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        # Top-level sections toggle their subtopics when clicked.
        if item.parent() is None and item.childCount() > 0:
            item.setExpanded(not item.isExpanded())
        topic = item.data(0, _TOPIC_ROLE)
        if topic:
            self.topic_selected.emit(str(topic))

    def _on_branch_toggled(self, _item: QTreeWidgetItem) -> None:
        self._refresh_section_arrows()

    def _refresh_section_arrows(self) -> None:
        """Prefix each section label with ▾ (open) or ▸ (collapsed)."""
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            label = item.data(0, _LABEL_ROLE)
            if label is None:
                continue
            arrow = _ARROW_OPEN if item.isExpanded() else _ARROW_CLOSED
            item.setText(0, f"{arrow}  {label}")
