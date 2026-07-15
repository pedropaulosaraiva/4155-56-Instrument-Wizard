"""
extra_widgets/settings_dialog.py
--------------------------------
Modal dialog for global application settings.

Edits author / organization.  ASCII-output and accuracy-tracking toggles are
shown but disabled — they are reserved for future global-settings features
(ASCII data collection w/ status flags; per-point accuracy).  Mirrors the
existing connection-wizard modal pattern.

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

from wizard_4155_4156.db.global_settings import (
    ALLOWED_LINE_FREQUENCIES,
    ALLOWED_THEMES,
    DEFAULT_LINE_FREQUENCY_HZ,
    DEFAULT_THEME,
    GlobalSettings,
)
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import settings_dialog_stylesheet

_T = CommandWizardText

# Internal theme name → UI label (gui_text enum member).
_THEME_LABELS: dict[str, CommandWizardText] = {
    "dark": _T.THEME_LABEL_DARK,
    "light": _T.THEME_LABEL_LIGHT,
    "france": _T.THEME_LABEL_FRANCE,
    "brasil": _T.THEME_LABEL_BRASIL,
}


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
            ascii_toggle=self._ascii.isChecked(),
            accuracy_toggle=self._accuracy.isChecked(),
            line_frequency_hz=int(
                self._line_freq.currentData() or DEFAULT_LINE_FREQUENCY_HZ
            ),
            theme=str(self._theme.currentData() or DEFAULT_THEME),
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
        root.addLayout(form)

        instr_title = QLabel("Instrument")
        instr_title.setObjectName("section")
        root.addWidget(instr_title)

        instr_form = QFormLayout()
        instr_form.setSpacing(10)
        self._line_freq = QComboBox()
        for freq in ALLOWED_LINE_FREQUENCIES:
            self._line_freq.addItem(f"{freq} Hz", freq)
        self._line_freq.setToolTip(
            "AC power-line frequency. Sets the QSCV integration-time limits."
        )
        instr_form.addRow("Line frequency", self._line_freq)
        root.addLayout(instr_form)

        appearance_title = QLabel(tr_ui(_T.SETTINGS_APPEARANCE_SECTION))
        appearance_title.setObjectName("section")
        root.addWidget(appearance_title)

        appearance_form = QFormLayout()
        appearance_form.setSpacing(10)
        self._theme = QComboBox()
        for name in ALLOWED_THEMES:
            self._theme.addItem(tr_ui(_THEME_LABELS[name]), name)
        self._theme.setToolTip(tr_ui(_T.SETTINGS_THEME_RESTART_HINT))
        appearance_form.addRow(tr_ui(_T.SETTINGS_THEME_LABEL), self._theme)
        root.addLayout(appearance_form)

        theme_hint = QLabel(tr_ui(_T.SETTINGS_THEME_RESTART_HINT))
        theme_hint.setObjectName("hint")
        theme_hint.setWordWrap(True)
        root.addWidget(theme_hint)

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
        self._btn_cancel.setAutoDefault(False)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_save = QPushButton("Save")
        self._btn_save.setObjectName("primary")
        # Save is the dialog default: pressing Enter/Return commits the edits
        # (accept) instead of firing the first-added button (Cancel → reject).
        self._btn_save.setAutoDefault(True)
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self.accept)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_save)
        root.addLayout(buttons)

    def _load(self, settings: GlobalSettings) -> None:
        self._author.setText(settings.author)
        self._organization.setText(settings.organization)
        self._ascii.setChecked(settings.ascii_toggle)
        self._accuracy.setChecked(settings.accuracy_toggle)
        idx = self._line_freq.findData(settings.line_frequency_hz)
        self._line_freq.setCurrentIndex(idx if idx >= 0 else 0)
        theme_idx = self._theme.findData(settings.theme)
        self._theme.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
