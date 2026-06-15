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

from wizard_4155_4156.styles.stylesheets import settings_dialog_stylesheet


class SetupMetadataDialog(QDialog):
    """Collects a setup ``name`` (required) and ``description`` (optional)."""

    def __init__(
        self,
        title: str = "Save setup",
        name: str = "",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
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
        self._name.returnPressed.connect(self._maybe_accept)
        root.addWidget(self._name)

        root.addWidget(QLabel("Description (optional)"))
        self._description = QPlainTextEdit()
        self._description.setPlaceholderText(
            "What this setup measures, notes, conditions…"
        )
        self._description.setFixedHeight(90)
        root.addWidget(self._description)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_save = QPushButton("Save")
        self._btn_save.setObjectName("primary")
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self.accept)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_save)
        root.addLayout(buttons)

    # ── Private ──────────────────────────────────────────────────────────────

    def _update_save_enabled(self) -> None:
        self._btn_save.setEnabled(bool(self._name.text().strip()))

    def _maybe_accept(self) -> None:
        if self._name.text().strip():
            self.accept()
