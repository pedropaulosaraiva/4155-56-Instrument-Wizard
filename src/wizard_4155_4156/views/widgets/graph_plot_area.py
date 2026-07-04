"""
views/widgets/graph_plot_area.py
--------------------------------
The multi-plot grid of one Graphs-page scene (all pyqtgraph mechanics).

Passive view: the presenter translates its domain state into the render
DTOs defined here (``PlotRenderSpec`` / ``TraceRenderSpec``) and calls
``display_scene``; user gestures come back out as Qt signals.  The DTOs
live on the view side so this module never imports from ``models/``
(presenters may import views — never the reverse).

Engineering multipliers
-----------------------
pyqtgraph's automatic SI prefixing is disabled on every axis
(``enableAutoSIPrefix(False)``).  The user-selected multiplier arrives
as a pre-computed ``AxisItem.setScale`` factor, so only the tick *text*
is rescaled — the plotted data is never touched.

Cursors snap: a drag emits ``cursor_dragged`` and the presenter answers
with ``display_cursor`` positioned on the nearest real data point —
never interpolated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from wizard_4155_4156.styles.theme import PALETTE as P

_PG_CONFIGURED = False


def _configure_pyqtgraph() -> None:
    """One-time global pyqtgraph theming from the app palette."""
    global _PG_CONFIGURED  # noqa: PLW0603 — process-wide pg config
    if _PG_CONFIGURED:
        return
    pg.setConfigOptions(
        background=P.BG_DEEP,
        foreground=P.TEXT_SECONDARY,
        antialias=True,
    )
    _PG_CONFIGURED = True


_LINE_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
}

_MARKERS = {
    "circle": "o",
    "square": "s",
    "triangle": "t",
    "cross": "+",
}


# =============================================================================
# Render DTOs (built by the presenter)
# =============================================================================


@dataclass(frozen=True)
class TraceRenderSpec:
    """Everything needed to draw one curve."""

    trace_id: str
    name: str
    x: list[float]
    y: list[float]
    color: str
    visible: bool = True
    line_style: str = "solid"
    marker: str = "none"
    width: float = 1.5
    marker_size: float = 6.0
    opacity: float = 1.0


@dataclass(frozen=True)
class PlotRenderSpec:
    """Everything needed to render one grid cell."""

    index: int  # slot index (row * 3 + col)
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    x_log: bool = False
    y_log: bool = False
    x_scale: float = 1.0  # AxisItem.setScale value (multiplier)
    y_scale: float = 1.0
    x_range: tuple[float, float] | None = None  # None → autoscale
    y_range: tuple[float, float] | None = None
    mouse_mode: str = "pan"  # "pan" | "zoom"
    active: bool = False
    traces: list[TraceRenderSpec] = field(default_factory=list)
    roi: tuple[float, float] | None = None  # visible when not None
    cursors: list[float] = field(default_factory=list)  # initial x's


# =============================================================================
# Widget
# =============================================================================


class GraphPlotArea(QWidget):
    """pg.GraphicsLayoutWidget wrapper rendering one scene's plot grid."""

    plot_activated = Signal(int)  # slot index clicked
    roi_region_changed = Signal(float, float)  # linear-domain (lo, hi)
    cursor_dragged = Signal(int, float)  # (cursor_index, linear x)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_pyqtgraph()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)

        self._plots: dict[int, pg.PlotItem] = {}
        self._cursors: dict[int, tuple] = {}  # cursor idx → (line, marker)
        self._cursor_label: pg.TextItem | None = None
        self._roi_item: pg.LinearRegionItem | None = None
        self._active_index = 0
        self._active_log_x = False

        self._glw.scene().sigMouseClicked.connect(self._on_scene_clicked)

    # =========================================================================
    # Public display API (called by the presenter)
    # =========================================================================

    def display_scene(
        self,
        specs: list[PlotRenderSpec],
        rows: int,
        cols: int,
        active_index: int,
        maximized: bool,
    ) -> None:
        """Full rebuild of the grid from the render specs."""
        self._glw.clear()
        self._plots.clear()
        self._cursors.clear()
        self._cursor_label = None
        self._roi_item = None
        self._active_index = active_index

        by_index = {spec.index: spec for spec in specs}
        if maximized and active_index in by_index:
            placements = [(active_index, 0, 0)]
        else:
            placements = [
                (row * 3 + col, row, col)
                for row in range(rows)
                for col in range(cols)
            ]

        for slot, row, col in placements:
            spec = by_index.get(slot)
            if spec is None:
                continue
            plot = self._glw.addPlot(row=row, col=col)
            self._plots[slot] = plot
            self._render_plot(plot, spec)

    def display_cursor(
        self,
        cursor_index: int,
        x: float,
        y: float,
        text: str,
    ) -> None:
        """Snap a cursor onto the data point the presenter resolved."""
        entry = self._cursors.get(cursor_index)
        if entry is None:
            return
        line, marker = entry
        pos_x = self._to_axis_x(x)
        line.blockSignals(True)
        line.setPos(pos_x)
        line.blockSignals(False)
        plot = self._plots.get(self._active_index)
        marker.setPos(pos_x, self._to_axis_y(y))
        if self._cursor_label is not None and plot is not None:
            self._cursor_label.setText(text)
            self._cursor_label.setPos(pos_x, self._to_axis_y(y))

    def reset_view(self, slot_index: int) -> None:
        plot = self._plots.get(slot_index)
        if plot is not None:
            plot.autoRange()

    def export_plot_png(self, slot_index: int, path: str) -> bool:
        """Render one plot to a PNG file (pyqtgraph ImageExporter)."""
        plot = self._plots.get(slot_index)
        if plot is None:
            return False
        ImageExporter(plot).export(path)
        return True

    # =========================================================================
    # Rendering helpers
    # =========================================================================

    def _render_plot(self, plot: pg.PlotItem, spec: PlotRenderSpec) -> None:
        self._setup_axes(plot, spec)
        self._draw_traces(plot, spec)
        self._apply_ranges(plot, spec)
        self._apply_interaction(plot, spec)
        if spec.active:
            self._attach_roi(plot, spec)
            self._attach_cursors(plot, spec)

    def _setup_axes(self, plot: pg.PlotItem, spec: PlotRenderSpec) -> None:
        for side, scale in (
            ("bottom", spec.x_scale),
            ("left", spec.y_scale),
        ):
            axis = plot.getAxis(side)
            axis.enableAutoSIPrefix(False)  # multiplier is user-owned
            axis.setScale(scale)
        plot.setLabel("bottom", spec.x_label or None)
        plot.setLabel("left", spec.y_label or None)
        if spec.title:
            plot.setTitle(spec.title)
        plot.setLogMode(x=spec.x_log, y=spec.y_log)
        plot.showGrid(x=True, y=True, alpha=P.GRAPH_GRID_ALPHA)

    def _draw_traces(self, plot: pg.PlotItem, spec: PlotRenderSpec) -> None:
        visible = [t for t in spec.traces if t.visible]
        if len(visible) > 1:
            plot.addLegend(
                offset=(10, 10),
                labelTextColor=P.TEXT_SECONDARY,
                brush=pg.mkBrush(P.BG_PANEL),
                pen=pg.mkPen(P.BORDER),
            )
        for trace in visible:
            pen = self._make_pen(trace)
            symbol = _MARKERS.get(trace.marker)
            plot.plot(
                trace.x,
                trace.y,
                pen=pen,
                name=trace.name,
                symbol=symbol,
                symbolSize=trace.marker_size,
                symbolPen=pg.mkPen(self._color(trace)),
                symbolBrush=pg.mkBrush(self._color(trace)),
                connect="finite",  # break lines at nan — never bridge
            )

    @staticmethod
    def _color(trace: TraceRenderSpec):
        color = pg.mkColor(trace.color)
        color.setAlphaF(max(0.0, min(1.0, trace.opacity)))
        return color

    def _make_pen(self, trace: TraceRenderSpec):
        style = _LINE_STYLES.get(trace.line_style)
        if style is None:  # "none" → markers only
            return None
        return pg.mkPen(self._color(trace), width=trace.width, style=style)

    def _apply_ranges(self, plot: pg.PlotItem, spec: PlotRenderSpec) -> None:
        vb = plot.getViewBox()
        if spec.x_range is None:
            vb.enableAutoRange(axis=pg.ViewBox.XAxis)
        else:
            lo, hi = self._axis_bounds(spec.x_range, spec.x_log)
            vb.setXRange(lo, hi, padding=0)
        if spec.y_range is None:
            vb.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            lo, hi = self._axis_bounds(spec.y_range, spec.y_log)
            vb.setYRange(lo, hi, padding=0)

    def _apply_interaction(
        self, plot: pg.PlotItem, spec: PlotRenderSpec
    ) -> None:
        vb = plot.getViewBox()
        vb.setMouseMode(
            pg.ViewBox.RectMode
            if spec.mouse_mode == "zoom"
            else pg.ViewBox.PanMode
        )
        vb.setBorder(
            pg.mkPen(P.ACCENT, width=2)
            if spec.active
            else pg.mkPen(P.BORDER, width=1)
        )
        if spec.active:
            self._active_log_x = spec.x_log

    def _attach_roi(self, plot: pg.PlotItem, spec: PlotRenderSpec) -> None:
        if spec.roi is None:
            return
        lo, hi = self._axis_bounds(spec.roi, spec.x_log)
        roi = pg.LinearRegionItem(
            values=(lo, hi),
            orientation="vertical",
            brush=pg.mkBrush(self._roi_brush_color()),
            pen=pg.mkPen(P.ACCENT),
        )
        roi.setZValue(-10)
        plot.addItem(roi)
        roi.sigRegionChangeFinished.connect(self._on_roi_changed)
        self._roi_item = roi

    def _attach_cursors(self, plot: pg.PlotItem, spec: PlotRenderSpec) -> None:
        colors = (P.GRAPH_CURSOR, P.GRAPH_CURSOR_ALT)
        for cursor_index, x in enumerate(spec.cursors):
            pen = pg.mkPen(colors[cursor_index % len(colors)], width=1)
            line = pg.InfiniteLine(
                pos=self._to_axis_x(x),
                angle=90,
                movable=True,
                pen=pen,
                hoverPen=pg.mkPen(P.ACCENT_HOVER, width=2),
            )
            marker = pg.TargetItem(
                pos=(self._to_axis_x(x), 0.0),
                size=9,
                movable=False,
                pen=pen,
            )
            plot.addItem(line)
            plot.addItem(marker)
            line.sigPositionChanged.connect(
                lambda _line, idx=cursor_index: self._on_cursor_moved(idx)
            )
            self._cursors[cursor_index] = (line, marker)
        if spec.cursors:
            self._cursor_label = pg.TextItem(
                color=P.TEXT_PRIMARY, anchor=(0, 1.2)
            )
            plot.addItem(self._cursor_label)

    @staticmethod
    def _axis_bounds(
        bounds: tuple[float, float], log: bool
    ) -> tuple[float, float]:
        """Linear-domain (lo, hi) → axis coordinates (log10 when log)."""
        lo, hi = min(bounds), max(bounds)
        if not log:
            return lo, hi
        safe_lo = math.log10(lo) if lo > 0 else -12.0
        safe_hi = math.log10(hi) if hi > 0 else 0.0
        return safe_lo, safe_hi

    @staticmethod
    def _roi_brush_color():
        color = pg.mkColor(P.GRAPH_ROI)
        color.setAlphaF(0.35)
        return color

    # =========================================================================
    # Log-coordinate conversions (pyqtgraph items live in log10 space
    # when the axis is in log mode; signals always carry linear values)
    # =========================================================================

    def _to_axis_x(self, x: float) -> float:
        if self._active_log_x:
            return math.log10(x) if x > 0 else 0.0
        return x

    def _to_axis_y(self, y: float) -> float:
        plot = self._plots.get(self._active_index)
        if plot is not None and plot.getAxis("left").logMode:
            return math.log10(y) if y > 0 else 0.0
        return y

    def _from_axis_x(self, pos: float) -> float:
        return 10.0**pos if self._active_log_x else pos

    # =========================================================================
    # Internal event handlers → signals
    # =========================================================================

    def _on_scene_clicked(self, event) -> None:
        pos = event.scenePos()
        for slot, plot in self._plots.items():
            if plot.sceneBoundingRect().contains(pos):
                self.plot_activated.emit(slot)
                return

    def _on_roi_changed(self) -> None:
        if self._roi_item is None:
            return
        lo, hi = self._roi_item.getRegion()
        self.roi_region_changed.emit(
            self._from_axis_x(float(lo)), self._from_axis_x(float(hi))
        )

    def _on_cursor_moved(self, cursor_index: int) -> None:
        entry = self._cursors.get(cursor_index)
        if entry is None:
            return
        line, _marker = entry
        self.cursor_dragged.emit(
            cursor_index, self._from_axis_x(float(line.value()))
        )
