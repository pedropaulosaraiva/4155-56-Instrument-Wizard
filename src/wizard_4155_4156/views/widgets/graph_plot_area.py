"""
views/widgets/graph_plot_area.py
--------------------------------
The multi-plot grid of one Graphs-page scene (all pyqtgraph mechanics).

Passive view: the presenter translates its domain state into the render
DTOs defined here (``PlotRenderSpec`` / ``TraceRenderSpec``) and calls
``display_scene``; user gestures come back out as Qt signals.  The DTOs
live on the view side so this module never imports from ``models/``
(presenters may import views — never the reverse).

Stateful rendering (zoom/pan/cursors survive repaints)
------------------------------------------------------
``display_scene`` does NOT rebuild the grid on every call.  Plots are
updated **in place** (titles, labels, scales, traces, cursors…) so the
user's zoom/pan state and cursor positions are untouched by style or
config edits.  A full rebuild happens only when the grid geometry or
the scene changes — and even then each scene's per-plot view state
(``ViewBox.getState`` + cursor positions) is stashed by scene token and
restored when the scene comes back.

Engineering multipliers
-----------------------
pyqtgraph's automatic SI prefixing is disabled on every axis
(``enableAutoSIPrefix(False)``).  The user-selected multiplier arrives
as a pre-computed ``AxisItem.setScale`` factor, so only the tick *text*
is rescaled — the plotted data is never touched.

Cursors are plain movable vertical lines (they slide freely — no
snapping on the canvas); a drag emits ``cursor_dragged`` and the
presenter shows the nearest real data point in the View tab readout.
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
    cursors: list[float] = field(default_factory=list)  # default x's


@dataclass
class _SlotState:
    """Runtime registry of one rendered grid cell."""

    plot: pg.PlotItem
    spec: PlotRenderSpec
    legend: pg.LegendItem
    curves: list = field(default_factory=list)
    cursor_lines: list = field(default_factory=list)
    roi_item: pg.LinearRegionItem | None = None


# =============================================================================
# Widget
# =============================================================================


class GraphPlotArea(QWidget):
    """pg.GraphicsLayoutWidget wrapper rendering one scene's plot grid."""

    plot_activated = Signal(int)  # slot index clicked
    roi_region_changed = Signal(int, float, float)  # (slot, lo, hi)
    cursor_dragged = Signal(int, int, float)  # (slot, cursor, linear x)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _configure_pyqtgraph()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)

        self._slots: dict[int, _SlotState] = {}
        self._plots: dict[int, pg.PlotItem] = {}  # slot → PlotItem
        self._scene_token: int | None = None
        self._layout_key: tuple | None = None
        #: (scene token, slot) → (ViewBox state, cursor linear x's).
        self._view_stash: dict[tuple, tuple[dict, list[float]]] = {}

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
        scene_token: int,
    ) -> None:
        """Render the scene — in place when the geometry is unchanged."""
        layout_key = (
            rows,
            cols,
            maximized,
            active_index if maximized else None,
        )
        if scene_token != self._scene_token or layout_key != self._layout_key:
            self._rebuild(
                specs,
                rows,
                cols,
                active_index,
                maximized,
                scene_token,
                layout_key,
            )
            return
        for spec in specs:
            state = self._slots.get(spec.index)
            if state is not None:
                self._update_slot(state, spec)

    def reset_view(self, slot_index: int) -> None:
        state = self._slots.get(slot_index)
        if state is not None:
            state.plot.autoRange()

    def export_plot_png(self, slot_index: int, path: str) -> bool:
        """Render one plot to a PNG file (pyqtgraph ImageExporter)."""
        state = self._slots.get(slot_index)
        if state is None:
            return False
        ImageExporter(state.plot).export(path)
        return True

    # =========================================================================
    # Full rebuild (geometry / scene change) with view-state stash
    # =========================================================================

    def _rebuild(
        self,
        specs: list[PlotRenderSpec],
        rows: int,
        cols: int,
        active_index: int,
        maximized: bool,
        scene_token: int,
        layout_key: tuple,
    ) -> None:
        self._stash_view_states()
        self._glw.clear()
        self._slots.clear()
        self._plots.clear()
        self._scene_token = scene_token
        self._layout_key = layout_key

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
            legend = plot.addLegend(
                offset=(10, 10),
                labelTextColor=P.TEXT_SECONDARY,
                brush=pg.mkBrush(P.BG_PANEL),
                pen=pg.mkPen(P.BORDER),
            )
            state = _SlotState(plot=plot, spec=spec, legend=legend)
            self._slots[slot] = state
            self._plots[slot] = plot
            self._apply_full(state)
            self._restore_view_state(state)

    def _stash_view_states(self) -> None:
        """Remember each slot's zoom/pan + cursor positions by token."""
        if self._scene_token is None:
            return
        for slot, state in self._slots.items():
            vb_state = state.plot.getViewBox().getState(copy=True)
            cursor_xs = [
                self._from_axis(float(line.value()), state.spec.x_log)
                for line in state.cursor_lines
            ]
            self._view_stash[(self._scene_token, slot)] = (
                vb_state,
                cursor_xs,
            )

    def _restore_view_state(self, state: _SlotState) -> None:
        entry = self._view_stash.get((self._scene_token, state.spec.index))
        if entry is None:
            return
        vb_state, cursor_xs = entry
        state.plot.getViewBox().setState(vb_state)
        for line, x in zip(state.cursor_lines, cursor_xs):
            line.blockSignals(True)
            line.setPos(self._to_axis(x, state.spec.x_log))
            line.blockSignals(False)

    # =========================================================================
    # Full apply (fresh plot)
    # =========================================================================

    def _apply_full(self, state: _SlotState) -> None:
        spec = state.spec
        plot = state.plot
        self._apply_axes(state)
        plot.setLogMode(x=spec.x_log, y=spec.y_log)
        plot.showGrid(x=True, y=True, alpha=P.GRAPH_GRID_ALPHA)
        self._draw_curves(state)
        self._apply_range(state, "x", spec.x_range)
        self._apply_range(state, "y", spec.y_range)
        self._apply_interaction(state)
        self._sync_roi(state, spec.roi, force=True)
        self._sync_cursors(state, spec.cursors, force=True)

    def _apply_axes(self, state: _SlotState) -> None:
        spec = state.spec
        plot = state.plot
        for side, scale in (
            ("bottom", spec.x_scale),
            ("left", spec.y_scale),
        ):
            axis = plot.getAxis(side)
            axis.enableAutoSIPrefix(False)  # multiplier is user-owned
            axis.setScale(scale)
        plot.setLabel("bottom", spec.x_label or None)
        plot.setLabel("left", spec.y_label or None)
        plot.setTitle(spec.title or None)

    def _apply_range(
        self,
        state: _SlotState,
        axis: str,
        bounds: tuple[float, float] | None,
    ) -> None:
        vb = state.plot.getViewBox()
        log = state.spec.x_log if axis == "x" else state.spec.y_log
        if bounds is None:
            vb.enableAutoRange(
                axis=pg.ViewBox.XAxis if axis == "x" else pg.ViewBox.YAxis
            )
            return
        lo, hi = self._axis_bounds(bounds, log)
        if axis == "x":
            vb.setXRange(lo, hi, padding=0)
        else:
            vb.setYRange(lo, hi, padding=0)

    def _apply_interaction(self, state: _SlotState) -> None:
        vb = state.plot.getViewBox()
        vb.setMouseMode(
            pg.ViewBox.RectMode
            if state.spec.mouse_mode == "zoom"
            else pg.ViewBox.PanMode
        )
        vb.setBorder(
            pg.mkPen(P.ACCENT, width=2)
            if state.spec.active
            else pg.mkPen(P.BORDER, width=1)
        )

    # =========================================================================
    # In-place update (no zoom/pan/cursor loss)
    # =========================================================================

    def _update_slot(self, state: _SlotState, spec: PlotRenderSpec) -> None:
        old = state.spec
        state.spec = spec
        plot = state.plot

        if (
            spec.title != old.title
            or spec.x_label != old.x_label
            or spec.y_label != old.y_label
            or spec.x_scale != old.x_scale
            or spec.y_scale != old.y_scale
        ):
            self._apply_axes(state)

        log_changed = spec.x_log != old.x_log or spec.y_log != old.y_log
        if log_changed:
            plot.setLogMode(x=spec.x_log, y=spec.y_log)

        # Ranges are only touched when their *configuration* changed —
        # a plain repaint never clobbers the user's zoom/pan.
        if log_changed or spec.x_range != old.x_range:
            self._apply_range(state, "x", spec.x_range)
        if log_changed or spec.y_range != old.y_range:
            self._apply_range(state, "y", spec.y_range)

        if spec.mouse_mode != old.mouse_mode or spec.active != old.active:
            self._apply_interaction(state)

        if spec.traces != old.traces:
            self._draw_curves(state)

        self._sync_roi(state, spec.roi)
        self._sync_cursors(state, spec.cursors)

    # =========================================================================
    # Curves
    # =========================================================================

    def _draw_curves(self, state: _SlotState) -> None:
        for curve in state.curves:
            state.plot.removeItem(curve)  # also drops its legend entry
        state.curves.clear()
        for trace in state.spec.traces:
            if not trace.visible:
                continue
            pen = self._make_pen(trace)
            symbol = _MARKERS.get(trace.marker)
            item = state.plot.plot(
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
            state.curves.append(item)

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

    # =========================================================================
    # ROI (kept across repaints; recreated only on enable/disable)
    # =========================================================================

    def _sync_roi(
        self,
        state: _SlotState,
        roi: tuple[float, float] | None,
        force: bool = False,
    ) -> None:
        if roi is None:
            if state.roi_item is not None:
                state.plot.removeItem(state.roi_item)
                state.roi_item = None
            return
        bounds = self._axis_bounds(roi, state.spec.x_log)
        if state.roi_item is None or force:
            if state.roi_item is not None:
                state.plot.removeItem(state.roi_item)
            item = pg.LinearRegionItem(
                values=bounds,
                orientation="vertical",
                brush=pg.mkBrush(self._roi_brush_color()),
                pen=pg.mkPen(P.ACCENT),
            )
            item.setZValue(-10)
            state.plot.addItem(item)
            slot = state.spec.index
            item.sigRegionChangeFinished.connect(
                lambda _item, s=slot: self._on_roi_changed(s)
            )
            state.roi_item = item
            return
        # Same item — only nudge it when the stored region differs
        # (e.g. restored from persistence), signals blocked.
        current = state.roi_item.getRegion()
        if not all(
            math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
            for a, b in zip(current, bounds)
        ):
            state.roi_item.blockSignals(True)
            state.roi_item.setRegion(bounds)
            state.roi_item.blockSignals(False)

    @staticmethod
    def _roi_brush_color():
        color = pg.mkColor(P.GRAPH_ROI)
        color.setAlphaF(0.35)
        return color

    # =========================================================================
    # Cursors (plain movable lines — positions persist across repaints)
    # =========================================================================

    def _sync_cursors(
        self,
        state: _SlotState,
        defaults: list[float],
        force: bool = False,
    ) -> None:
        wanted = len(defaults)
        if force:
            for line in state.cursor_lines:
                state.plot.removeItem(line)
            state.cursor_lines.clear()
        while len(state.cursor_lines) > wanted:
            state.plot.removeItem(state.cursor_lines.pop())
        while len(state.cursor_lines) < wanted:
            index = len(state.cursor_lines)
            state.cursor_lines.append(
                self._create_cursor(state, index, defaults[index])
            )

    def _create_cursor(self, state: _SlotState, cursor_index: int, x: float):
        colors = (P.GRAPH_CURSOR, P.GRAPH_CURSOR_ALT)
        color = colors[cursor_index % len(colors)]
        line = pg.InfiniteLine(
            pos=self._to_axis(x, state.spec.x_log),
            angle=90,
            movable=True,
            pen=pg.mkPen(color, width=2),
            hoverPen=pg.mkPen(P.ACCENT_HOVER, width=3),
        )
        state.plot.addItem(line)
        slot = state.spec.index
        line.sigPositionChanged.connect(
            lambda _line, s=slot, i=cursor_index: self._on_cursor_moved(s, i)
        )
        return line

    # =========================================================================
    # Log-coordinate conversions (pyqtgraph items live in log10 space
    # when the axis is in log mode; signals always carry linear values)
    # =========================================================================

    @staticmethod
    def _to_axis(x: float, log: bool) -> float:
        if log:
            return math.log10(x) if x > 0 else 0.0
        return x

    @staticmethod
    def _from_axis(pos: float, log: bool) -> float:
        return 10.0**pos if log else pos

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

    # =========================================================================
    # Internal event handlers → signals
    # =========================================================================

    def _on_scene_clicked(self, event) -> None:
        pos = event.scenePos()
        for slot, state in self._slots.items():
            if state.plot.sceneBoundingRect().contains(pos):
                self.plot_activated.emit(slot)
                return

    def _on_roi_changed(self, slot: int) -> None:
        state = self._slots.get(slot)
        if state is None or state.roi_item is None:
            return
        lo, hi = state.roi_item.getRegion()
        self.roi_region_changed.emit(
            slot,
            self._from_axis(float(lo), state.spec.x_log),
            self._from_axis(float(hi), state.spec.x_log),
        )

    def _on_cursor_moved(self, slot: int, cursor_index: int) -> None:
        state = self._slots.get(slot)
        if state is None or cursor_index >= len(state.cursor_lines):
            return
        line = state.cursor_lines[cursor_index]
        self.cursor_dragged.emit(
            slot,
            cursor_index,
            self._from_axis(float(line.value()), state.spec.x_log),
        )
