"""
extra_widgets/measurement_status_dialog.py
-------------------------------------------
Modal detail view for the measurement-config status widget: three columns,
Critical (blocking errors), Warnings (non-blocking), and Information (stats).

Each column is a rounded card carrying a colored top accent stripe (red /
yellow / blue), echoing the VAR1/VAR2 section-card visual language. Critical
and Warnings render as bullet rows; Information renders as label-left /
bold-value-right rows.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import (
    settings_dialog_stylesheet,
    status_column_title_stylesheet,
    status_modal_card_stylesheet,
    status_modal_empty_stylesheet,
    status_modal_info_label_stylesheet,
    status_modal_info_value_stylesheet,
    status_modal_item_stylesheet,
)

_T = CommandWizardText


class MeasurementStatusDialog(QDialog):
    """Read-only three-column breakdown of the current setup's status."""

    def __init__(
        self,
        criticals: List[str],
        warnings: List[str],
        info_lines: List[Tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr_ui(_T.CFG_MODAL_TITLE))
        self.setModal(True)
        self.setMinimumWidth(720)
        self.setStyleSheet(settings_dialog_stylesheet())
        self._build(criticals, warnings, info_lines)

    def _build(
        self,
        criticals: List[str],
        warnings: List[str],
        info_lines: List[Tuple[str, str]],
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(
            self._message_column(
                "critical",
                tr_ui(_T.CFG_COL_CRITICAL),
                criticals,
                tr_ui(_T.CFG_NO_CRITICAL),
            ),
            1,
        )
        columns.addWidget(
            self._message_column(
                "warning",
                tr_ui(_T.CFG_COL_WARNINGS),
                warnings,
                tr_ui(_T.CFG_NO_WARNINGS),
            ),
            1,
        )
        columns.addWidget(
            self._info_column(tr_ui(_T.CFG_COL_INFO), info_lines),
            1,
        )
        root.addLayout(columns)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

    # ── Column factories ─────────────────────────────────────────────────────

    @staticmethod
    def _card(kind: str, title: str) -> Tuple[QFrame, QVBoxLayout]:
        """Titled card with a top accent stripe; returns (card, body)."""
        card = QFrame()
        card.setObjectName("status_modal_card")
        card.setStyleSheet(status_modal_card_stylesheet(kind))
        body = QVBoxLayout(card)
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(10)

        heading = QLabel(title)
        heading.setStyleSheet(status_column_title_stylesheet(kind))
        body.addWidget(heading)
        return card, body

    @classmethod
    def _message_column(
        cls, kind: str, title: str, items: List[str], empty_text: str
    ) -> QFrame:
        """Critical/Warnings column: bullet rows, or a muted-italic empty."""
        card, body = cls._card(kind, title)
        if items:
            for text in items:
                item = QLabel(f"•  {text}")
                item.setWordWrap(True)
                item.setStyleSheet(status_modal_item_stylesheet(kind))
                body.addWidget(item)
        else:
            empty = QLabel(empty_text)
            empty.setWordWrap(True)
            empty.setStyleSheet(status_modal_empty_stylesheet())
            body.addWidget(empty)
        body.addStretch()
        return card

    @classmethod
    def _info_column(
        cls, title: str, info_lines: List[Tuple[str, str]]
    ) -> QFrame:
        """Information column: label-left / bold-value-right rows."""
        card, body = cls._card("info", title)
        for label, value in info_lines:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(12)
            lbl = QLabel(label)
            lbl.setStyleSheet(status_modal_info_label_stylesheet())
            val = QLabel(value)
            val.setStyleSheet(status_modal_info_value_stylesheet())
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            body.addLayout(row)
        body.addStretch()
        return card
