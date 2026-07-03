"""
views/widgets/measurement_status.py
------------------------------------
Shared top bar for the three measurement-config pages (Sweep/Sampling/QSCV).

Left:   mode name + documentation button.
Centre: a clickable, compact status card (Critical / Warning / Info chips) that
        opens a three-column detail modal.
Right:  a Save Setup button and a ⋮ menu aggregating the JSON actions.

The widget is a passive view: the presenter pushes state via ``display_status``
and ``flash_saved``; user intent leaves through the signals below.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)

from wizard_4155_4156.extra_widgets.measurement_status_dialog import (
    MeasurementStatusDialog,
)
from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import (
    export_btn_stylesheet,
    measurement_status_card_stylesheet,
    measurement_topbar_stylesheet,
    measurement_topbar_title_stylesheet,
    runs_menu_button_stylesheet,
    status_chip_stylesheet,
)
from wizard_4155_4156.views.widgets.action_menu import ActionMenu
from wizard_4155_4156.views.widgets.doc_tooltip import DocTooltipButton

_T = CommandWizardText


class _ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MeasurementTopBar(QWidget):
    """Top bar hosting the Measurement Status Widget and save/JSON actions."""

    documentation_requested = Signal(str)  # DocTopic value
    save_setup_requested = Signal()
    save_json_requested = Signal()
    export_requested = Signal()

    def __init__(
        self,
        mode_name: str,
        doc_topic: DocTopic,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._criticals: List[str] = []
        self._warnings: List[str] = []
        self._info_lines: List[Tuple[str, str]] = []
        self._status_text: str = ""
        self._savable: bool = False

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(3000)
        self._toast_timer.timeout.connect(self._render)

        self._build(mode_name, doc_topic)
        self._render()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self, mode_name: str, doc_topic: DocTopic) -> None:
        # Object name + styled background so the scoped stylesheet paints the
        # bar and keeps its border-bottom off the child text labels.
        self.setObjectName("measurement_topbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(measurement_topbar_stylesheet())
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 10, 24, 10)
        row.setSpacing(16)

        title = QLabel(mode_name)
        title.setStyleSheet(measurement_topbar_title_stylesheet())
        row.addWidget(title)
        doc = DocTooltipButton(doc_topic, size=18)
        doc.requested.connect(self.documentation_requested)
        row.addWidget(doc)

        self._card = _ClickableFrame()
        self._card.setObjectName("status_card")
        self._card.setStyleSheet(measurement_status_card_stylesheet())
        self._card.setCursor(Qt.CursorShape.PointingHandCursor)
        self._card.clicked.connect(self._open_modal)
        card_row = QHBoxLayout(self._card)
        card_row.setContentsMargins(14, 8, 14, 8)
        card_row.setSpacing(18)
        self._critical_lbl = QLabel()
        self._warning_lbl = QLabel()
        self._info_lbl = QLabel()
        for lbl in (self._critical_lbl, self._warning_lbl, self._info_lbl):
            card_row.addWidget(lbl)
        card_row.addStretch()
        row.addWidget(self._card, stretch=1)

        self._save_btn = QPushButton(tr_ui(_T.CFG_BTN_SAVE_SETUP))
        self._save_btn.setStyleSheet(export_btn_stylesheet())
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self.save_setup_requested)
        row.addWidget(self._save_btn)

        self._menu_btn = QToolButton()
        self._menu_btn.setText("⋮")
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._menu_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self._menu_btn.setStyleSheet(runs_menu_button_stylesheet())
        self._menu_btn.clicked.connect(self._show_menu)
        row.addWidget(self._menu_btn)

    # ── Public API (pushed by the presenter) ─────────────────────────────────

    def display_status(
        self,
        criticals: List[str],
        warnings: List[str],
        indexes: str,
        points: str,
        exec_time: str,
    ) -> None:
        self._criticals = list(criticals)
        self._warnings = list(warnings)
        self._savable = not self._criticals
        self._status_text = (
            tr_ui(_T.CFG_STATUS_READY)
            if self._savable
            else tr_ui(_T.CFG_STATUS_NOT_READY)
        )
        self._info_lines = [
            (tr_ui(_T.CFG_INFO_INDEXES), indexes),
            (tr_ui(_T.CFG_INFO_POINTS), points),
            (tr_ui(_T.CFG_INFO_EXEC_TIME), exec_time),
            (tr_ui(_T.CFG_INFO_STATUS), self._status_text),
        ]
        self._toast_timer.stop()
        self._render()

    def flash_saved(self, name: str) -> None:
        """Briefly show a save confirmation, then restore the status."""
        self._critical_lbl.setText(tr_ui(_T.CFG_SAVED_TOAST).format(name=name))
        self._critical_lbl.setStyleSheet(status_chip_stylesheet("ok"))
        self._warning_lbl.clear()
        self._info_lbl.clear()
        self._toast_timer.start()

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render(self) -> None:
        n_c = len(self._criticals)
        n_w = len(self._warnings)
        top = "critical" if n_c else ("warning" if n_w else "info")

        if n_c:
            text = f"❌ {self._criticals[0]}"
            if n_c > 1:
                text += f"  +{n_c - 1}"
            self._critical_lbl.setText(text)
            self._critical_lbl.setStyleSheet(status_chip_stylesheet("critical"))
        else:
            self._critical_lbl.setText("❌ 0")
            self._critical_lbl.setStyleSheet(status_chip_stylesheet("muted"))

        if top == "warning":
            text = f"⚠️ {self._warnings[0]}"
            if n_w > 1:
                text += f"  +{n_w - 1}"
            self._warning_lbl.setText(text)
        else:
            self._warning_lbl.setText(f"⚠️ {n_w}")
        self._warning_lbl.setStyleSheet(
            status_chip_stylesheet("warning" if n_w else "muted")
        )

        if top == "info":
            self._info_lbl.setText(f"ℹ️ {self._status_text}")
        else:
            self._info_lbl.setText("ℹ️")
        self._info_lbl.setStyleSheet(
            status_chip_stylesheet("ok" if self._savable else "info")
        )

        self._save_btn.setEnabled(self._savable)
        self._menu_btn.setEnabled(self._savable)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _open_modal(self) -> None:
        MeasurementStatusDialog(
            self._criticals, self._warnings, self._info_lines, self
        ).exec()

    def _show_menu(self) -> None:
        menu = ActionMenu(self)
        menu.add_item(
            tr_ui(_T.CFG_MENU_SAVE_JSON),
            callback=self.save_json_requested.emit,
            available=self._savable,
        )
        menu.add_item(
            tr_ui(_T.CFG_MENU_GENERATE_JSON),
            callback=self.export_requested.emit,
            available=self._savable,
        )
        menu.popup_under(self._menu_btn)
