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

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocTopic
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
from wizard_4155_4156.views.widgets.doc_tooltip import DocTooltipButton

_T = CommandWizardText


class MeasurementStatusDialog(QDialog):
    """Read-only three-column breakdown of the current setup's status."""

    documentation_requested = Signal(str)  # DocTopic value

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
                DocTopic.STATUS_CRITICAL,
            ),
            1,
        )
        columns.addWidget(
            self._message_column(
                "warning",
                tr_ui(_T.CFG_COL_WARNINGS),
                warnings,
                tr_ui(_T.CFG_NO_WARNINGS),
                DocTopic.STATUS_WARNING,
            ),
            1,
        )
        columns.addWidget(
            self._info_column(
                tr_ui(_T.CFG_COL_INFO), info_lines, DocTopic.STATUS_INFO
            ),
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

    def _card(
        self, kind: str, title: str, doc_topic: DocTopic
    ) -> Tuple[QFrame, QVBoxLayout]:
        """Titled card with a top accent stripe; returns (card, body).

        The header row carries the column title plus a ``ⓘ`` icon that opens
        the matching documentation page.
        """
        card = QFrame()
        card.setObjectName("status_modal_card")
        card.setStyleSheet(status_modal_card_stylesheet(kind))
        body = QVBoxLayout(card)
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        heading = QLabel(title)
        heading.setStyleSheet(status_column_title_stylesheet(kind))
        header.addWidget(heading)
        header.addStretch()
        doc_btn = DocTooltipButton(doc_topic)
        doc_btn.requested.connect(self._on_doc_requested)
        header.addWidget(doc_btn)
        body.addLayout(header)
        return card, body

    def _message_column(
        self,
        kind: str,
        title: str,
        items: List[str],
        empty_text: str,
        doc_topic: DocTopic,
    ) -> QFrame:
        """Critical/Warnings column: bullet rows, or a muted-italic empty."""
        card, body = self._card(kind, title, doc_topic)
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

    def _info_column(
        self,
        title: str,
        info_lines: List[Tuple[str, str]],
        doc_topic: DocTopic,
    ) -> QFrame:
        """Information column: label-left / bold-value-right rows."""
        card, body = self._card("info", title, doc_topic)
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

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_doc_requested(self, topic: str) -> None:
        """Close the modal, then ask the app to open the documentation page.

        The dialog is application-modal (opened via ``exec``); a documentation
        window shown while it is up would be input-blocked, so accept the
        dialog first and forward the request as it tears down.
        """
        self.accept()
        self.documentation_requested.emit(topic)
