"""
views/widgets/graph_sidebar.py
------------------------------
The collapsible right sidebar of a Graphs-page scene: a QTabWidget with
the three permanent tabs (Data / View / Analysis), each vertically
scrollable.

The tabs are exposed as ``data_tab`` / ``view_tab`` / ``analysis_tab``;
``GraphPageView`` chains their signals up to its own page-level surface.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.stylesheets import (
    graph_sidebar_stylesheet,
    units_scroll_area_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.graph_analysis_tab import (
    GraphAnalysisTab,
)
from wizard_4155_4156.views.widgets.graph_data_tab import GraphDataTab
from wizard_4155_4156.views.widgets.graph_view_tab import GraphViewTab


def _scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setStyleSheet(units_scroll_area_stylesheet())
    area.setWidget(widget)
    return area


class GraphSidebar(QWidget):
    """Fixed-width tab column configuring the active plot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(P.GRAPH_SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.data_tab = GraphDataTab()
        self.view_tab = GraphViewTab()
        self.analysis_tab = GraphAnalysisTab()

        tabs = QTabWidget()
        tabs.setStyleSheet(graph_sidebar_stylesheet())
        tabs.addTab(_scrollable(self.data_tab), tr_ui(TXT.GRAPH_TAB_DATA))
        tabs.addTab(_scrollable(self.view_tab), tr_ui(TXT.GRAPH_TAB_VIEW))
        tabs.addTab(
            _scrollable(self.analysis_tab), tr_ui(TXT.GRAPH_TAB_ANALYSIS)
        )
        layout.addWidget(tabs)
