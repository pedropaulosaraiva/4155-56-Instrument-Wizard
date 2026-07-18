"""
views/widgets/graph_data_tab.py
-------------------------------
"Data" sidebar tab — selects WHICH executions feed the ACTIVE plot of
the current scene (setups → executions tree with checkboxes).

Axis configuration lives on the Plot tab (``graph_plot_tab.py``); the
scene-level grid controls live in the scene bar (``graph_page.py``).

Passive view: emits ``execution_check_changed``; state arrives through
``display_datasets``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.stylesheets import (
    graph_dataset_tree_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.config_sections import SectionFrame

_EXEC_ID_ROLE = Qt.ItemDataRole.UserRole


class GraphDataTab(QWidget):
    """Dataset (execution) selection for the active plot."""

    execution_check_changed = Signal(int, bool)  # (exec_id, checked)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_cache: dict[str, QIcon] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        root.addWidget(self._build_datasets_section(), stretch=1)

    # ── Build helpers ───────────────────────────────────────────────────────

    def _build_datasets_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_DATASETS),
            flat=True,
            accent=P.GRAPH_TAB_DATA,
        )
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet(graph_dataset_tree_stylesheet())
        self._tree.setIndentation(12)  # default ~20px wastes row width
        self._tree.setMinimumHeight(150)
        self._tree.itemChanged.connect(self._on_item_changed)
        section.body().addWidget(self._tree)
        return section

    # ── Public display API ──────────────────────────────────────────────────

    def display_datasets(
        self,
        groups: list[
            tuple[
                str,
                list[tuple[int, str, bool, bool, str | None, str | None]],
            ]
        ],
    ) -> None:
        """Rebuild the tree: (setup label, [(id, label, checked, enabled,
        trace color, disabled reason)])."""
        self._tree.blockSignals(True)
        self._tree.clear()
        for setup_label, executions in groups:
            top = QTreeWidgetItem([setup_label])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            top.setToolTip(0, setup_label)
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            top.setForeground(0, QBrush(QColor(P.TEXT_PRIMARY)))
            self._tree.addTopLevelItem(top)
            for exec_id, label, checked, enabled, color, reason in executions:
                child = QTreeWidgetItem([label])
                child.setData(0, _EXEC_ID_ROLE, exec_id)
                flags = (
                    Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                if enabled:
                    flags |= Qt.ItemFlag.ItemIsEnabled
                    child.setToolTip(0, label)  # full name when elided
                else:
                    child.setToolTip(0, reason or "")
                child.setFlags(flags)
                child.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if checked
                    else Qt.CheckState.Unchecked,
                )
                if color:
                    child.setIcon(0, self._color_icon(color))
                top.addChild(child)
            top.setExpanded(True)
        self._tree.blockSignals(False)

    # ── Internals ───────────────────────────────────────────────────────────

    def _color_icon(self, color: str) -> QIcon:
        """Small rounded swatch linking a plotted run to its trace color."""
        icon = self._icon_cache.get(color)
        if icon is None:
            pm = QPixmap(12, 12)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 12, 12, 3, 3)
            painter.end()
            icon = self._icon_cache[color] = QIcon(pm)
        return icon

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        exec_id = item.data(column, _EXEC_ID_ROLE)
        if exec_id is None:
            return
        self.execution_check_changed.emit(
            int(exec_id), item.checkState(column) == Qt.CheckState.Checked
        )
