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

Each cursor is a freely sliding vertical line plus a marker and an x/y
label pinned to the NEAREST real data point (never interpolated): any
line movement — user drag, creation, scene restore — emits
``cursor_dragged`` and the presenter answers with ``display_cursor``
(canvas marker + label) and the View-tab readout, so neither can ever
show stale values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
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


class _StableAxisItem(pg.AxisItem):
    """AxisItem whose tick scale is exactly the ``setScale`` factor.

    Stock ``enableAutoSIPrefix(False)`` still recomputes
    ``autoSIPrefixScale`` from the current range while the label is
    visible, silently multiplying the tick text — pin it to 1 instead."""

    def updateAutoSIPrefix(self) -> None:
        if self.autoSIPrefix:
            super().updateAutoSIPrefix()
            return
        self.autoSIPrefixScale = 1.0
        self.labelUnitPrefix = ""
        self._updateLabel()  # invalidates the tick picture + repaints


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
class _Cursor:
    """One cursor: draggable line + snapped marker + x/y label.

    The line slides freely; the marker/label are placed by the
    presenter (``display_cursor``) on the NEAREST real data point."""

    line: pg.InfiniteLine
    marker: pg.TargetItem
    label: pg.TextItem


@dataclass
class _SlotState:
    """Runtime registry of one rendered grid cell."""

    plot: pg.PlotItem
    spec: PlotRenderSpec
    legend: pg.LegendItem
    curves: list = field(default_factory=list)
    cursors: list[_Cursor] = field(default_factory=list)
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

    # PNG-export background choices (export-only — the on-screen theme
    # background is never touched).  "theme" keeps the exporter default.
    _EXPORT_BG_COLORS = {
        "white": "#ffffff",
        "black": "#000000",
        "transparent": (0, 0, 0, 0),
    }
    # Foreground (axis / title / legend text) paired with each background;
    # "transparent" keeps the theme text since the final backdrop is unknown.
    _EXPORT_FG_COLORS = {
        "white": "#000000",
        "black": "#ffffff",
    }

    def _make_exporter(self, item, background: str) -> ImageExporter:
        exporter = ImageExporter(item)
        color = self._export_bg_qcolor(background)
        if color is not None:
            exporter.parameters()["background"] = color
        return exporter

    def _export_bg_qcolor(self, background: str) -> QColor | None:
        bg = self._EXPORT_BG_COLORS.get(background)
        if bg is None:
            return None
        return QColor(*bg) if isinstance(bg, tuple) else QColor(bg)

    @staticmethod
    def _set_legend_label_colors(legend: pg.LegendItem, color) -> None:
        """Recolor existing legend labels.

        ``LegendItem.setLabelTextColor`` only stores the color — the label
        HTML is generated at ``setText`` time, so each label must be re-set
        for the change to actually render.
        """
        legend.opts["labelTextColor"] = pg.mkColor(color)
        for _sample, label in legend.items:
            label.setText(label.text, color=color)

    def _style_for_export(
        self, state: _SlotState, bg_color: QColor, fg: str | None
    ) -> None:
        """Restyle one plot's text/legend/cursor readouts for ``bg_color``.

        ``fg=None`` (transparent background) keeps the theme text colors and
        only clears the boxes behind the legend and cursor readouts.
        """
        plot = state.plot
        if fg is not None:
            for side in ("bottom", "left"):
                axis = plot.getAxis(side)
                axis.setPen(pg.mkPen(fg))
                axis.setTextPen(pg.mkPen(fg))
            if state.spec.title:
                plot.setTitle(state.spec.title, color=fg)
            self._set_legend_label_colors(state.legend, fg)
        state.legend.setBrush(pg.mkBrush(bg_color))
        state.legend.setPen(pg.mkPen(fg if fg else P.BORDER))
        for cursor in state.cursors:
            if fg is not None:
                cursor.label.setColor(fg)
            cursor.label.fill = pg.mkBrush(bg_color)
            cursor.label.border = pg.mkPen(fg if fg else P.BORDER)
            cursor.label.update()

    def _apply_export_style(
        self, states: list[_SlotState], background: str
    ) -> None:
        """Restyle text/legend so they read on the chosen export background."""
        bg_color = self._export_bg_qcolor(background)
        if bg_color is None:
            return
        fg = self._EXPORT_FG_COLORS.get(background)
        for state in states:
            self._style_for_export(state, bg_color, fg)

    def _restore_theme_style(self, states: list[_SlotState]) -> None:
        label_fill = pg.mkColor(P.BG_PANEL)
        label_fill.setAlphaF(0.85)
        for state in states:
            plot = state.plot
            for side in ("bottom", "left"):
                axis = plot.getAxis(side)
                axis.setPen(pg.mkPen(P.TEXT_SECONDARY))
                axis.setTextPen(pg.mkPen(P.TEXT_SECONDARY))
            if state.spec.title:
                plot.setTitle(state.spec.title, color=P.TEXT_SECONDARY)
            state.legend.setBrush(pg.mkBrush(P.BG_PANEL))
            state.legend.setPen(pg.mkPen(P.BORDER))
            self._set_legend_label_colors(state.legend, P.TEXT_SECONDARY)
            for cursor in state.cursors:
                cursor.label.setColor(P.TEXT_PRIMARY)
                cursor.label.fill = pg.mkBrush(label_fill)
                cursor.label.border = pg.mkPen(P.BORDER)
                cursor.label.update()

    def export_plot_png(
        self, slot_index: int, path: str, background: str = "theme"
    ) -> bool:
        """Render one plot to a PNG file (pyqtgraph ImageExporter)."""
        state = self._slots.get(slot_index)
        if state is None:
            return False
        self._apply_export_style([state], background)
        try:
            self._make_exporter(state.plot, background).export(path)
        finally:
            self._restore_theme_style([state])
        return True

    def export_scene_png(self, path: str, background: str = "theme") -> bool:
        """Render the whole plot grid (all visible plots) to a PNG file."""
        states = list(self._slots.values())
        self._apply_export_style(states, background)
        try:
            self._make_exporter(self._glw.scene(), background).export(path)
        finally:
            self._restore_theme_style(states)
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
            plot = self._glw.addPlot(
                row=row,
                col=col,
                axisItems={
                    "bottom": _StableAxisItem("bottom"),
                    "left": _StableAxisItem("left"),
                },
            )
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
            # Let the presenter recompute snapped markers/labels and
            # the View-tab readout for the (re)created cursors.
            self._notify_cursors(state)

    def _stash_view_states(self) -> None:
        """Remember each slot's zoom/pan + cursor positions by token."""
        if self._scene_token is None:
            return
        for slot, state in self._slots.items():
            vb_state = state.plot.getViewBox().getState(copy=True)
            cursor_xs = [
                self._from_axis(float(c.line.value()), state.spec.x_log)
                for c in state.cursors
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
        for cursor, x in zip(state.cursors, cursor_xs):
            cursor.line.blockSignals(True)
            cursor.line.setPos(self._to_axis(x, state.spec.x_log))
            cursor.line.blockSignals(False)

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
            # Cursor lines live in axis coordinates — re-place them so
            # they keep their *linear* position across the log switch.
            for cursor in state.cursors:
                linear = self._from_axis(float(cursor.line.value()), old.x_log)
                cursor.line.blockSignals(True)
                cursor.line.setPos(self._to_axis(linear, spec.x_log))
                cursor.line.blockSignals(False)

        # Ranges are only touched when their *configuration* changed —
        # a plain repaint never clobbers the user's zoom/pan.
        if log_changed or spec.x_range != old.x_range:
            self._apply_range(state, "x", spec.x_range)
        if log_changed or spec.y_range != old.y_range:
            self._apply_range(state, "y", spec.y_range)

        if spec.mouse_mode != old.mouse_mode or spec.active != old.active:
            self._apply_interaction(state)

        traces_changed = spec.traces != old.traces
        if traces_changed:
            self._draw_curves(state)

        self._sync_roi(state, spec.roi)
        cursors_changed = self._sync_cursors(state, spec.cursors)
        if cursors_changed or traces_changed or log_changed:
            # Stale snapped text is refreshed for EVERY cursor (e.g.
            # adding a second cursor also recomputes the Δ readout).
            self._notify_cursors(state)

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
        color.setAlphaF(P.GRAPH_ROI_ALPHA)
        return color

    # =========================================================================
    # Cursors (line + snapped marker + x/y label; positions persist
    # across repaints, labels recomputed by the presenter)
    # =========================================================================

    def display_cursor(
        self,
        slot: int,
        cursor_index: int,
        x: float,
        y: float,
        text: str,
    ) -> None:
        """Place a cursor's marker + label on the snapped data point
        the presenter resolved (the line itself is never moved)."""
        state = self._slots.get(slot)
        if state is None or cursor_index >= len(state.cursors):
            return
        cursor = state.cursors[cursor_index]
        px = self._to_axis(x, state.spec.x_log)
        py = self._to_axis(y, state.spec.y_log)
        cursor.marker.setPos(px, py)
        cursor.label.setText(text)
        cursor.label.setPos(px, py)

    def _sync_cursors(
        self,
        state: _SlotState,
        defaults: list[float],
        force: bool = False,
    ) -> bool:
        """Match cursor count to the spec; True when items changed."""
        wanted = len(defaults)
        changed = False
        if force:
            for cursor in state.cursors:
                self._remove_cursor(state, cursor)
            state.cursors.clear()
            changed = True
        while len(state.cursors) > wanted:
            self._remove_cursor(state, state.cursors.pop())
            changed = True
        while len(state.cursors) < wanted:
            index = len(state.cursors)
            state.cursors.append(
                self._create_cursor(state, index, defaults[index])
            )
            changed = True
        return changed

    @staticmethod
    def _remove_cursor(state: _SlotState, cursor: _Cursor) -> None:
        for item in (cursor.line, cursor.marker, cursor.label):
            state.plot.removeItem(item)

    def _create_cursor(
        self, state: _SlotState, cursor_index: int, x: float
    ) -> _Cursor:
        colors = (P.GRAPH_CURSOR, P.GRAPH_CURSOR_ALT)
        color = colors[cursor_index % len(colors)]
        pos = self._to_axis(x, state.spec.x_log)
        line = pg.InfiniteLine(
            pos=pos,
            angle=90,
            movable=True,
            pen=pg.mkPen(color, width=2),
            hoverPen=pg.mkPen(P.ACCENT_HOVER, width=3),
        )
        marker = pg.TargetItem(
            pos=(pos, 0.0),
            size=9,
            movable=False,
            pen=pg.mkPen(color),
        )
        # Filled + bordered so the readout stays legible over curves.
        label_fill = pg.mkColor(P.BG_PANEL)
        label_fill.setAlphaF(0.85)
        label = pg.TextItem(
            color=P.TEXT_PRIMARY,
            anchor=(0, 1.2),
            fill=pg.mkBrush(label_fill),
            border=pg.mkPen(P.BORDER),
        )
        for item in (line, marker, label):
            state.plot.addItem(item)
        slot = state.spec.index
        line.sigPositionChanged.connect(
            lambda _line, s=slot, i=cursor_index: self._on_cursor_moved(s, i)
        )
        return _Cursor(line=line, marker=marker, label=label)

    def _notify_cursors(self, state: _SlotState) -> None:
        """Report every cursor's line position so the presenter can
        recompute the snapped markers/labels and the tab readout."""
        for index, cursor in enumerate(state.cursors):
            self.cursor_dragged.emit(
                state.spec.index,
                index,
                self._from_axis(float(cursor.line.value()), state.spec.x_log),
            )

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
        if state is None or cursor_index >= len(state.cursors):
            return
        line = state.cursors[cursor_index].line
        self.cursor_dragged.emit(
            slot,
            cursor_index,
            self._from_axis(float(line.value()), state.spec.x_log),
        )
