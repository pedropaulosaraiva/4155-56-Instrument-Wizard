"""
views/widgets/setup_detail_panel.py
-----------------------------------
The "Setup detail" pane of the Runs page — pure View layer.

A header with a **Summary / Raw** segmented toggle sits over a stacked area:

* **Summary** — a curated, card-based digest of the most important parameters
  for the setup's mode (e.g. VAR1 / VAR2 / VARD for a sweep), colour-coded with
  the VARx colour language and the display-variable pills.
* **Raw** — the full configuration JSON rendered as a two-column tree (field
  names sized to fit, so nothing is truncated).

The owner pushes state via :meth:`display`; the widget keeps no business logic.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.sweep_config import SweepConstraints
from wizard_4155_4156.styles.stylesheets import (
    config_preview_tree_stylesheet,
    meas_status_label_stylesheet,
    runs_panel_title_stylesheet,
    setup_summary_chip_stylesheet,
    setup_summary_empty_stylesheet,
    setup_summary_key_stylesheet,
    setup_summary_scroll_stylesheet,
    setup_summary_value_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.config_sections import (
    SectionFrame,
    SegmentedGroup,
)
from wizard_4155_4156.views.widgets.flow_layout import flow_host

_T = CommandWizardText


class SetupDetailPanel(QWidget):
    """Summary/Raw view of a setup's stored configuration dict."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config: Optional[dict] = None
        self._build_ui()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel(tr_ui(_T.RUNS_DETAIL_TITLE))
        title.setStyleSheet(runs_panel_title_stylesheet())
        head.addWidget(title)
        head.addStretch()
        self._toggle = SegmentedGroup(
            [tr_ui(_T.RUNS_DETAIL_SUMMARY), tr_ui(_T.RUNS_DETAIL_RAW)],
            default=tr_ui(_T.RUNS_DETAIL_SUMMARY),
        )
        self._toggle.setFixedWidth(180)
        self._toggle.selection_changed.connect(self._on_toggle)
        head.addWidget(self._toggle)
        root.addLayout(head)

        self._summary_line = QLabel("")
        self._summary_line.setStyleSheet(meas_status_label_stylesheet())
        self._summary_line.setWordWrap(True)
        self._summary_line.setVisible(False)
        root.addWidget(self._summary_line)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_summary_view())  # index 0
        self._stack.addWidget(self._build_raw_view())  # index 1
        root.addWidget(self._stack, stretch=1)

    def _build_summary_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(setup_summary_scroll_stylesheet())
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        container = QWidget()
        self._summary_layout = QVBoxLayout(container)
        self._summary_layout.setContentsMargins(0, 0, 6, 0)
        self._summary_layout.setSpacing(12)
        scroll.setWidget(container)
        return scroll

    def _build_raw_view(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setStyleSheet(config_preview_tree_stylesheet())
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Field", "Value"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(True)
        header = tree.header()
        # Field column sized to fit its content (incl. indentation) so names
        # are never truncated; the value column takes the remaining width.
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tree = tree
        return tree

    # ── Public API ───────────────────────────────────────────────────────────

    def display(self, config: Optional[dict], summary: str) -> None:
        self._config = config
        self._summary_line.setText(summary)
        self._summary_line.setVisible(bool(summary))
        self._rebuild_summary()
        self._rebuild_raw()

    def clear(self) -> None:
        self.display(None, "")

    # ── Toggle ───────────────────────────────────────────────────────────────

    def _on_toggle(self, value: str) -> None:
        is_raw = value == tr_ui(_T.RUNS_DETAIL_RAW)
        self._stack.setCurrentIndex(1 if is_raw else 0)

    # ── Raw (JSON tree) ──────────────────────────────────────────────────────

    def _rebuild_raw(self) -> None:
        self._tree.clear()
        if self._config:
            self._populate_tree(self._tree, self._config)
            self._tree.expandToDepth(0)

    def _populate_tree(
        self, parent: Any, data: Any, key: Optional[str] = None
    ) -> None:
        if isinstance(data, dict):
            container = (
                parent if key is None else QTreeWidgetItem(parent, [key, ""])
            )
            for k, v in data.items():
                self._populate_tree(container, v, str(k))
        elif isinstance(data, (list, tuple)):
            node = QTreeWidgetItem(parent, [key or "", f"[{len(data)}]"])
            for i, v in enumerate(data):
                self._populate_tree(node, v, str(i))
        else:
            QTreeWidgetItem(parent, [key or "", str(data)])

    # ── Summary (curated cards) ──────────────────────────────────────────────

    def _rebuild_summary(self) -> None:
        self._clear_summary()
        if not self._config:
            empty = QLabel(tr_ui(_T.RUNS_DETAIL_EMPTY))
            empty.setStyleSheet(setup_summary_empty_stylesheet())
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            self._summary_layout.addWidget(empty)
            self._summary_layout.addStretch()
            return

        mode = str(self._config.get("mode", "")).upper()
        if mode == "SWEEP":
            self._build_sweep_summary()
        elif mode == "SAMP":
            self._build_sampling_summary()
        elif mode == "QSCV":
            self._build_qscv_summary()
        else:
            self._build_generic_summary()
        self._summary_layout.addStretch()

    def _build_sweep_summary(self) -> None:
        cfg = self._config
        channels = cfg.get("channels", {})
        ms = cfg.get("measurement_setup", {})
        sweep = cfg.get("sweep_setup", {})

        if "var1" in sweep:
            self._add_var_card(
                P.FUNC_VAR1, "VAR1", channels, sweep["var1"], "VAR1"
            )
        if "var2" in sweep:
            self._add_var_card(
                P.FUNC_VAR2, "VAR2", channels, sweep["var2"], "VAR2"
            )
        if "vard" in sweep:
            self._add_var_card(
                P.FUNC_VARD, "VARD", channels, sweep["vard"], "VARD"
            )

        self._add_display_vars_card(channels, cfg.get("display_vars", []))
        self._add_units_card(channels)

        self._add_card(
            P.ACCENT,
            tr_ui(_T.RUNS_SUM_TIMING),
            [
                *self._integration_rows(ms),
                ("Hold time", f"{_num(sweep.get('hold_time'))} s"),
                ("Delay", f"{_num(sweep.get('delay'))} s"),
                ("Sweep stop", _txt(sweep.get("sweep_stop"))),
            ],
        )

    def _build_sampling_summary(self) -> None:
        cfg = self._config
        channels = cfg.get("channels", {})
        ms = cfg.get("measurement_setup", {})
        samp = cfg.get("sampling_setup", {})

        rows = [
            ("Mode", _txt(samp.get("mode"))),
            ("Initial interval", f"{_num(samp.get('initial_interval'))} s"),
            ("Points", _txt(samp.get("points"))),
            ("Filter", _txt(samp.get("filter"))),
        ]
        if "period_auto" in samp or "period" in samp:
            rows.append(("Period", self._period_text(samp)))
        scon = samp.get("scon", {})
        rows.append(("Stop condition", self._scon_text(scon)))
        self._add_card(P.STATUS_INFO, tr_ui(_T.RUNS_SUM_SAMPLING), rows)

        self._add_display_vars_card(channels, cfg.get("display_vars", []))
        self._add_units_card(channels)

        self._add_card(
            P.ACCENT,
            tr_ui(_T.RUNS_SUM_TIMING),
            [
                *self._integration_rows(ms),
                ("Hold time", f"{_num(samp.get('hold_time'))} s"),
            ],
        )

    def _build_qscv_summary(self) -> None:
        cfg = self._config
        channels = cfg.get("channels", {})
        q = cfg.get("qscv_setup", {})

        self._add_card(
            P.STATUS_INFO,
            tr_ui(_T.RUNS_SUM_MEASUREMENT),
            [
                ("Range", _txt(q.get("range"))),
                ("Unit", _txt(q.get("unit"))),
                ("Sweep stop", _txt(q.get("sweep_stop"))),
                ("Leak cancel", _txt(q.get("leak_cancel"))),
                ("Zero cancel", _txt(q.get("zero_cancel"))),
            ],
        )
        if "var1" in q:
            self._add_var_card(
                P.FUNC_VAR1, "VAR1", channels, q["var1"], "VAR1"
            )
        # Capacitance and leakage current are the measured variables in QSCV.
        measured = {q.get("cap_name"), q.get("leak_name")} - {None, ""}
        self._add_display_vars_card(
            channels, cfg.get("display_vars", []), measured
        )
        self._add_units_card(channels)

        self._add_card(
            P.ACCENT,
            tr_ui(_T.RUNS_SUM_TIMING),
            [
                (
                    "Cap. integration",
                    f"{_num(q.get('cap_integration_time'))} s",
                ),
                (
                    "Leak integration",
                    f"{_num(q.get('leak_integration_time'))} s",
                ),
                ("Hold time", f"{_num(q.get('hold_time'))} s"),
                ("Delay", f"{_num(q.get('delay'))} s"),
            ],
        )

    def _build_generic_summary(self) -> None:
        cfg = self._config
        rows = [
            (str(k), _txt(v))
            for k, v in cfg.items()
            if not isinstance(v, (dict, list, tuple))
        ]
        if rows:
            self._add_card(P.ACCENT, tr_ui(_T.RUNS_SUM_MEASUREMENT), rows)
        self._add_display_vars_card(
            cfg.get("channels", {}), cfg.get("display_vars", [])
        )

    # ── Card builders ────────────────────────────────────────────────────────

    def _add_card(
        self, accent: str, title: str, rows: list[tuple[str, str]]
    ) -> SectionFrame:
        card = SectionFrame(title, accent=accent)
        for key, value in rows:
            card.body().addWidget(self._kv_row(key, value))
        self._summary_layout.addWidget(card)
        return card

    def _add_var_card(
        self,
        accent: str,
        label: str,
        channels: dict,
        var: dict,
        function: str,
    ) -> None:
        cid, ch = _find_function_channel(channels, function)
        src_u, comp_u = _source_units(ch)
        title = f"{label} · {cid}" if cid else label

        rows: list[tuple[str, str]] = []
        if "mode" in var:
            rows.append(("Mode", _txt(var.get("mode"))))
        if "spacing" in var:
            rows.append(("Spacing", _txt(var.get("spacing"))))
        if "start" in var and "stop" in var:
            rows.append(
                (
                    "Sweep",
                    f"{_num(var['start'])} → {_num(var['stop'])} "
                    f"{src_u}".strip(),
                )
            )
        elif "start" in var:
            rows.append(("Start", f"{_num(var['start'])} {src_u}".strip()))
        if "step" in var:
            rows.append(("Step", f"{_num(var['step'])} {src_u}".strip()))
        if "n_of_steps" in var:
            rows.append(("Steps", _txt(var.get("n_of_steps"))))
            last = _last_var2_value(var)
            if last is not None:
                rows.append(("Last value", f"{_num(last)} {src_u}".strip()))
        points = _var1_points(var)
        if points is not None:
            rows.append(("Points", str(points)))
        if "ratio" in var:
            rows.append(("Ratio", _num(var.get("ratio"))))
        if "offset" in var:
            rows.append(("Offset", f"{_num(var['offset'])} {src_u}".strip()))
        if "cstep" in var:
            rows.append(("Cap. step", _num(var.get("cstep"))))
        if "compliance" in var:
            rows.append(
                (
                    "Compliance",
                    f"{_num(var['compliance'])} {comp_u}".strip(),
                )
            )
        if "pcompliance" in var:
            rows.append(("Power compliance", f"{_num(var['pcompliance'])} W"))

        self._add_card(accent, title, rows)

    def _add_display_vars_card(
        self,
        channels: dict,
        names: list,
        extra_measured: set[str] = frozenset(),
    ) -> None:
        if not names:
            return
        measured = _measured_var_names(channels) | set(extra_measured)
        card = SectionFrame(
            tr_ui(_T.RUNS_SUM_DISPLAY_VARS), accent=P.STATUS_OK
        )
        host = flow_host(h_spacing=6, v_spacing=6)
        host.setStyleSheet("background: transparent;")
        for name in names:
            chip = QLabel(str(name))
            chip.setStyleSheet(setup_summary_chip_stylesheet(name in measured))
            host.layout().addWidget(chip)
        card.body().addWidget(host)
        self._summary_layout.addWidget(card)

    def _add_units_card(self, channels: dict) -> None:
        rows: list[tuple[str, str]] = []
        for cid, ch in channels.items():
            if not isinstance(ch, dict) or ch.get("disable"):
                continue
            rows.append((cid, _unit_descriptor(ch)))
        if rows:
            self._add_card(P.UNIT_SMU, tr_ui(_T.RUNS_SUM_UNITS), rows)

    # ── Row / helpers ────────────────────────────────────────────────────────

    def _kv_row(self, key: str, value: str) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        k = QLabel(key)
        k.setStyleSheet(setup_summary_key_stylesheet())
        v = QLabel(value)
        v.setStyleSheet(setup_summary_value_stylesheet())
        v.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(k)
        lay.addStretch()
        lay.addWidget(v)
        return row

    def _integration_rows(self, ms: dict) -> list[tuple[str, str]]:
        rows = [("Integration", _txt(ms.get("integration_mode")))]
        if "short_time" in ms:
            rows.append(("Aperture", f"{_num(ms['short_time'])} s"))
        if "long_time_cycles" in ms:
            rows.append(("Cycles", f"{_txt(ms['long_time_cycles'])} PLC"))
        if "wait_time" in ms:
            rows.append(("Wait multiplier", _num(ms.get("wait_time"))))
        return rows

    @staticmethod
    def _period_text(samp: dict) -> str:
        if samp.get("period_auto") == "ON":
            return "Auto"
        period = samp.get("period")
        if period == "INFINITY":
            return "No limit"
        return f"{_num(period)} s" if period is not None else "—"

    @staticmethod
    def _scon_text(scon: dict) -> str:
        if not scon or scon.get("state") != "ON":
            return "Off"
        parts = [scon.get("name", ""), scon.get("event", "")]
        thr = scon.get("threshold")
        label = " ".join(p for p in parts if p)
        if thr is not None:
            label = f"{label} @ {_num(thr)}".strip()
        return label or "On"

    def _clear_summary(self) -> None:
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


# ── Module-level pure helpers ────────────────────────────────────────────────


def _num(value: Any) -> str:
    """Compact numeric formatting (keeps strings/None readable)."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "On" if value else "Off"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def _txt(value: Any) -> str:
    return "—" if value is None or value == "" else str(value)


def _find_function_channel(channels: dict, fn: str):
    for cid, ch in channels.items():
        if (
            isinstance(ch, dict)
            and not ch.get("disable")
            and ch.get("function") == fn
        ):
            return cid, ch
    return None, None


def _source_units(ch: Optional[dict]) -> tuple[str, str]:
    """(source unit, compliance unit) for a VARx channel dict."""
    if not ch or "smu_mode" not in ch:
        return "V", ""  # VSU (or unknown) — voltage source, no compliance
    mode = str(ch.get("smu_mode", "")).upper()
    if mode.startswith("I"):
        return "A", "V"
    return "V", "A"


def _last_var2_value(var: dict) -> Optional[float]:
    try:
        return var["start"] + (var["n_of_steps"] - 1) * var["step"]
    except (KeyError, TypeError):
        return None


def _var1_points(var: dict) -> Optional[int]:
    if "start" not in var or "stop" not in var:
        return None
    try:
        return SweepConstraints.var1_step_count(
            var["start"],
            var["stop"],
            var.get("step", 0.0),
            var.get("spacing", "LINEAR"),
        )
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _measured_var_names(channels: dict) -> set[str]:
    """Variable names actually measured by the active units."""
    names: set[str] = set()
    for ch in channels.values():
        if not isinstance(ch, dict) or ch.get("disable"):
            continue
        if "smu_mode" in ch:
            mode = str(ch.get("smu_mode", "")).upper()
            name = (
                ch.get("v_name") if mode.startswith("I") else ch.get("i_name")
            )
            if name:
                names.add(name)
        elif "vmu_mode" in ch:
            if ch.get("v_name"):
                names.add(ch["v_name"])
    return names


def _unit_descriptor(ch: dict) -> str:
    if "smu_mode" in ch:
        parts = [ch.get("function", ""), ch.get("smu_mode", "")]
    elif "vmu_mode" in ch:
        parts = ["VMU", ch.get("vmu_mode", "")]
    else:
        parts = [ch.get("function", ""), "V"]
    return " · ".join(p for p in parts if p) or "—"
