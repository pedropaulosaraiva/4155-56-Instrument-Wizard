"""
extra_widgets/settings_dialog.py
--------------------------------
Modal dialog for global application settings.

Edits author / organization / default instrument model.  ASCII-output and
accuracy-tracking toggles are shown but disabled — they are reserved for future
global-settings features (ASCII data collection w/ status flags; per-point
accuracy).  Mirrors the existing connection-wizard modal pattern.

The dialog reads/writes the Qt-free :class:`GlobalSettings` value object; it
performs no persistence itself — MainWindow saves through
``GlobalSettingsManager`` on ``accept``.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.db.global_settings import GlobalSettings
from wizard_4155_4156.models.channels import InstrumentModel
from wizard_4155_4156.styles.stylesheets import settings_dialog_stylesheet


class SettingsDialog(QDialog):
    """Modal editor for :class:`GlobalSettings`."""

    def __init__(
        self, settings: GlobalSettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Global Settings")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(settings_dialog_stylesheet())
        self._build_ui()
        self._load(settings)

    # ── Public API ───────────────────────────────────────────────────────────

    def get_settings(self) -> GlobalSettings:
        """Build a GlobalSettings from the current field values."""
        return GlobalSettings(
            author=self._author.text().strip(),
            organization=self._organization.text().strip(),
            default_instrument_model=self._instrument.currentText(),
            ascii_toggle=self._ascii.isChecked(),
            accuracy_toggle=self._accuracy.isChecked(),
        )

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        title = QLabel("Author & Organization")
        title.setObjectName("section")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self._author = QLineEdit()
        self._author.setPlaceholderText("e.g. Ada Lovelace")
        self._organization = QLineEdit()
        self._organization.setPlaceholderText("e.g. Analytical Engines Ltd")
        form.addRow("Author", self._author)
        form.addRow("Organization", self._organization)

        self._instrument = QComboBox()
        self._instrument.addItems([m.value for m in InstrumentModel])
        form.addRow("Default instrument", self._instrument)
        root.addLayout(form)

        future_title = QLabel("Data acquisition (coming soon)")
        future_title.setObjectName("section")
        root.addWidget(future_title)

        self._ascii = QCheckBox("Collect data as ASCII with status flags")
        self._ascii.setEnabled(False)
        self._ascii.setToolTip("Reserved for a future release.")
        self._accuracy = QCheckBox("Track per-point measurement accuracy")
        self._accuracy.setEnabled(False)
        self._accuracy.setToolTip("Reserved for a future release.")
        root.addWidget(self._ascii)
        root.addWidget(self._accuracy)

        hint = QLabel(
            "Author and organization are stamped onto every saved setup."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_save = QPushButton("Save")
        self._btn_save.setObjectName("primary")
        self._btn_save.clicked.connect(self.accept)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_save)
        root.addLayout(buttons)

    def _load(self, settings: GlobalSettings) -> None:
        self._author.setText(settings.author)
        self._organization.setText(settings.organization)
        idx = self._instrument.findText(settings.default_instrument_model)
        if idx >= 0:
            self._instrument.setCurrentIndex(idx)
        self._ascii.setChecked(settings.ascii_toggle)
        self._accuracy.setChecked(settings.accuracy_toggle)
