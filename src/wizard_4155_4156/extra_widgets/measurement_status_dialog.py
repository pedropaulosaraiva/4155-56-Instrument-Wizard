"""
extra_widgets/measurement_status_dialog.py
-------------------------------------------
Modal detail view for the measurement-config status widget: three columns —
Critical (blocking errors), Warnings (non-blocking), and Information (stats).
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
            self._column(
                "critical",
                tr_ui(_T.CFG_COL_CRITICAL),
                criticals or [tr_ui(_T.CFG_NO_CRITICAL)],
                "critical" if criticals else "muted",
            ),
            1,
        )
        columns.addWidget(
            self._column(
                "warning",
                tr_ui(_T.CFG_COL_WARNINGS),
                warnings or [tr_ui(_T.CFG_NO_WARNINGS)],
                "warning" if warnings else "muted",
            ),
            1,
        )
        columns.addWidget(
            self._column(
                "info",
                tr_ui(_T.CFG_COL_INFO),
                [f"{label}: {value}" for label, value in info_lines],
                "info",
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

    @staticmethod
    def _column(
        kind: str, title: str, items: List[str], item_kind: str
    ) -> QFrame:
        col = QFrame()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)

        heading = QLabel(title)
        heading.setStyleSheet(status_column_title_stylesheet(kind))
        lay.addWidget(heading)

        for text in items:
            item = QLabel(text)
            item.setWordWrap(True)
            item.setStyleSheet(status_modal_item_stylesheet(item_kind))
            lay.addWidget(item)
        lay.addStretch()
        return col
