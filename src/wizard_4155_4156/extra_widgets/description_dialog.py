"""
extra_widgets/description_dialog.py
-----------------------------------
Read-only modal showing a setup's or run's name + description, styled like
the rest of the application (shares ``settings_dialog_stylesheet`` with the
metadata dialog) instead of a generic ``QMessageBox``.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import settings_dialog_stylesheet

_T = CommandWizardText


class DescriptionDialog(QDialog):
    """Shows ``name`` as a heading and ``description`` as read-only text."""

    def __init__(
        self,
        name: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr_ui(_T.RUNS_DESC_TITLE))
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(settings_dialog_stylesheet())
        self._build_ui(name, description)

    def _build_ui(self, name: str, description: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        heading = QLabel(name or tr_ui(_T.RUNS_DESC_TITLE))
        heading.setObjectName("section")
        heading.setWordWrap(True)
        root.addWidget(heading)

        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setFixedHeight(140)
        text = (description or "").strip()
        if text:
            body.setPlainText(text)
        else:
            body.setPlaceholderText(tr_ui(_T.RUNS_NO_DESC))
        root.addWidget(body)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("primary")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        root.addLayout(buttons)
