"""
extra_widgets/setup_metadata_dialog.py
--------------------------------------
Single modal for entering a setup's name + description.

Used both when saving the current measurement config as a setup and when
editing an existing setup's metadata — replacing the previous pair of
sequential ``QInputDialog`` prompts with one styled dialog matching the rest of
the application (same fonts / widgets as the settings dialog).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.styles.stylesheets import (
    error_bar_stylesheet,
    settings_dialog_stylesheet,
)


class SetupMetadataDialog(QDialog):
    """Collects a setup ``name`` (required) and ``description`` (optional).

    When an ``on_submit`` callback is supplied it is invoked on Save with
    ``(name, description)``; returning an error string keeps the modal open and
    shows the message in red, returning ``None`` accepts/closes the dialog.
    Without a callback, Save accepts unconditionally (legacy behaviour).
    """

    def __init__(
        self,
        title: str = "Save setup",
        name: str = "",
        description: str = "",
        parent: QWidget | None = None,
        on_submit: Optional[Callable[[str, str], Optional[str]]] = None,
    ) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(settings_dialog_stylesheet())
        self._build_ui(title)
        self._name.setText(name)
        self._description.setPlainText(description)
        self._update_save_enabled()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_name(self) -> str:
        return self._name.text().strip()

    def get_description(self) -> str:
        return self._description.toPlainText().strip()

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self, title: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("section")
        root.addWidget(heading)

        root.addWidget(QLabel("Name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("Unique setup name")
        self._name.textChanged.connect(self._update_save_enabled)
        self._name.textChanged.connect(self._clear_error)
        self._name.returnPressed.connect(self._handle_submit)
        root.addWidget(self._name)

        root.addWidget(QLabel("Description (optional)"))
        self._description = QPlainTextEdit()
        self._description.setPlaceholderText(
            "What this setup measures, notes, conditions…"
        )
        self._description.setFixedHeight(90)
        root.addWidget(self._description)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.setStyleSheet(error_bar_stylesheet())
        self._error.setVisible(False)
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_save = QPushButton("Save")
        self._btn_save.setObjectName("primary")
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self._handle_submit)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_save)
        root.addLayout(buttons)

    # ── Private ──────────────────────────────────────────────────────────────

    def _update_save_enabled(self) -> None:
        self._btn_save.setEnabled(bool(self._name.text().strip()))

    def _handle_submit(self) -> None:
        name = self.get_name()
        if not name:
            return
        self._clear_error()
        if self._on_submit is None:
            self.accept()
            return
        error = self._on_submit(name, self.get_description())
        if error:
            self._show_error(error)
            return
        self.accept()

    def _show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)

    def _clear_error(self) -> None:
        self._error.clear()
        self._error.setVisible(False)
