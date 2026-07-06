"""
views/widgets/graph_sidebar.py
------------------------------
The collapsible right sidebar of a Graphs-page scene: a QTabWidget with
the four permanent tabs (Data / Plot / Tools / Analysis), each
vertically scrollable.

The tabs are exposed as ``data_tab`` / ``plot_tab`` / ``tools_tab`` /
``analysis_tab``; ``GraphPageView`` chains their signals up to its own
page-level surface.
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
    graph_sidebar_scroll_stylesheet,
    graph_sidebar_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.graph_analysis_tab import (
    GraphAnalysisTab,
)
from wizard_4155_4156.views.widgets.graph_data_tab import GraphDataTab
from wizard_4155_4156.views.widgets.graph_plot_tab import GraphPlotTab
from wizard_4155_4156.views.widgets.graph_tools_tab import GraphToolsTab


def _scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setStyleSheet(graph_sidebar_scroll_stylesheet())
    area.setWidget(widget)
    return area


class GraphSidebar(QWidget):
    """Splitter-resizable tab column configuring the active plot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(P.GRAPH_SIDEBAR_MIN_WIDTH)
        self.setMaximumWidth(P.GRAPH_SIDEBAR_MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.data_tab = GraphDataTab()
        self.plot_tab = GraphPlotTab()
        self.tools_tab = GraphToolsTab()
        self.analysis_tab = GraphAnalysisTab()

        self._tab_accents = (
            P.GRAPH_TAB_DATA,
            P.GRAPH_TAB_PLOT,
            P.GRAPH_TAB_TOOLS,
            P.GRAPH_TAB_ANALYSIS,
        )
        tabs = QTabWidget()
        tabs.setStyleSheet(graph_sidebar_stylesheet(self._tab_accents[0]))
        tabs.addTab(_scrollable(self.data_tab), tr_ui(TXT.GRAPH_TAB_DATA))
        tabs.addTab(_scrollable(self.plot_tab), tr_ui(TXT.GRAPH_TAB_PLOT))
        tabs.addTab(_scrollable(self.tools_tab), tr_ui(TXT.GRAPH_TAB_TOOLS))
        tabs.addTab(
            _scrollable(self.analysis_tab), tr_ui(TXT.GRAPH_TAB_ANALYSIS)
        )
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs
        layout.addWidget(tabs)

    def _on_tab_changed(self, index: int) -> None:
        """Re-tint the selected-tab marker with the active tab's hue."""
        accent = self._tab_accents[index % len(self._tab_accents)]
        self._tabs.setStyleSheet(graph_sidebar_stylesheet(accent))
