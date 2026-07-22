"""
extra_widgets/settings_dialog.py
--------------------------------
Modal dialog for global application settings.

Edits author / organization, instrument line frequency, and appearance, plus a
collapsed-by-default **Advanced Options** section holding two instrument-
behavior toggles (skip reset / keep auto calibration) and a destructive
"Delete All Measurement Runs…" action.  Mirrors the existing connection-wizard
modal pattern.

The dialog reads/writes the Qt-free :class:`GlobalSettings` value object; it
performs no settings persistence itself — MainWindow saves through
``GlobalSettingsManager`` on ``accept``.  The delete action is delegated to an
``on_delete_all_runs`` callback (owned by the Runs presenter); this dialog only
drives the irreversible-confirmation UX.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
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
        self,
        settings: GlobalSettings,
        parent: QWidget | None = None,
        *,
        on_delete_all_runs: Optional[Callable[[], int]] = None,
        delete_runs_enabled: bool = False,
    ) -> None:
        super().__init__(parent)
        # Callback that performs the actual run deletion (Runs presenter) and
        # returns the deleted count; None disables the action.
        self._on_delete_all_runs = on_delete_all_runs
        self._delete_runs_enabled = delete_runs_enabled
        self.setWindowTitle("Global Settings")
        self.setModal(True)
        self.setFixedWidth(460)
        self.setStyleSheet(settings_dialog_stylesheet())
        self._build_ui()
        self._load(settings)
        self._apply_height()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_settings(self) -> GlobalSettings:
        """Build a GlobalSettings from the current field values."""
        return GlobalSettings(
            author=self._author.text().strip(),
            organization=self._organization.text().strip(),
            line_frequency_hz=int(
                self._line_freq.currentData() or DEFAULT_LINE_FREQUENCY_HZ
            ),
            theme=str(self._theme.currentData() or DEFAULT_THEME),
            skip_reset=self._skip_reset.isChecked(),
            keep_auto_calibration=self._keep_auto_cal.isChecked(),
        )

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # The dialog content can outgrow short screens once "Advanced Options"
        # is expanded, so the scrolling body holds every section while the
        # Cancel/Save bar stays pinned at the bottom.  The dialog height is
        # clamped to the screen in _apply_height().
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("settings-scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        outer.addWidget(self._scroll, 1)

        self._content = QWidget()
        self._content.setObjectName("settings-content")
        self._scroll.setWidget(self._content)

        root = QVBoxLayout(self._content)
        root.setContentsMargins(22, 20, 22, 12)
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

        hint = QLabel(
            "Author and organization are stamped onto every saved setup."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._build_advanced_section(root)
        root.addStretch(1)

        button_bar = QWidget()
        button_bar.setObjectName("settings-buttonbar")
        buttons = QHBoxLayout(button_bar)
        buttons.setContentsMargins(22, 10, 22, 16)
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
        outer.addWidget(button_bar, 0)
        self._button_bar = button_bar

    def _build_advanced_section(self, root: QVBoxLayout) -> None:
        """Collapsed-by-default 'Advanced Options' group.

        A checkable QToolButton header toggles the visibility of a body widget
        (the simple ``setVisible`` collapse idiom used across the config
        pages), so advanced functionality stays hidden from typical users.
        """
        self._advanced_toggle = QToolButton()
        self._advanced_toggle.setObjectName("advanced-toggle")
        self._advanced_toggle.setText(tr_ui(_T.ADVANCED_SECTION))
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setChecked(False)  # collapsed by default
        self._advanced_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._advanced_toggle.toggled.connect(self._on_advanced_toggled)
        root.addWidget(self._advanced_toggle)

        self._advanced_body = QWidget()
        body = QVBoxLayout(self._advanced_body)
        body.setContentsMargins(6, 4, 0, 4)
        body.setSpacing(8)

        warning = QLabel(tr_ui(_T.ADVANCED_WARNING))
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        body.addWidget(warning)

        self._skip_reset = QCheckBox(tr_ui(_T.ADVANCED_SKIP_RESET_LABEL))
        body.addWidget(self._skip_reset)
        skip_hint = QLabel(tr_ui(_T.ADVANCED_SKIP_RESET_HINT))
        skip_hint.setObjectName("hint")
        skip_hint.setWordWrap(True)
        body.addWidget(skip_hint)

        self._keep_auto_cal = QCheckBox(tr_ui(_T.ADVANCED_KEEP_CAL_LABEL))
        body.addWidget(self._keep_auto_cal)
        cal_hint = QLabel(tr_ui(_T.ADVANCED_KEEP_CAL_HINT))
        cal_hint.setObjectName("hint")
        cal_hint.setWordWrap(True)
        body.addWidget(cal_hint)

        self._btn_delete_runs = QPushButton(
            tr_ui(_T.ADVANCED_DELETE_RUNS_BUTTON)
        )
        self._btn_delete_runs.setObjectName("danger")
        self._btn_delete_runs.setAutoDefault(False)
        self._btn_delete_runs.setEnabled(
            self._delete_runs_enabled and self._on_delete_all_runs is not None
        )
        if not self._btn_delete_runs.isEnabled():
            self._btn_delete_runs.setToolTip(
                tr_ui(_T.ADVANCED_DELETE_RUNS_DISABLED_TIP)
            )
        self._btn_delete_runs.clicked.connect(self._on_delete_all_runs_clicked)
        delete_row = QHBoxLayout()
        delete_row.addWidget(self._btn_delete_runs)
        delete_row.addStretch()
        body.addLayout(delete_row)

        delete_hint = QLabel(tr_ui(_T.ADVANCED_DELETE_RUNS_HINT))
        delete_hint.setObjectName("hint")
        delete_hint.setWordWrap(True)
        body.addWidget(delete_hint)

        self._advanced_body.setVisible(False)
        root.addWidget(self._advanced_body)

    def _on_advanced_toggled(self, checked: bool) -> None:
        self._advanced_toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self._advanced_body.setVisible(checked)
        # Grow/shrink to fit the newly shown/hidden content, but never past the
        # screen — the scroll body absorbs any overflow.
        self._apply_height()

    def _apply_height(self) -> None:
        """Size the dialog to its content, clamped to the visible screen.

        When expanding would push the window past the screen edge, cap the
        height (the body scrolls) and shift the window up so it stays fully
        on-screen.
        """
        # sizeHint of the scrolled content + the pinned button bar.
        wanted = (
            self._content.sizeHint().height()
            + self._button_bar.sizeHint().height()
            + 2
        )
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(self.width(), wanted)
            return

        avail = screen.availableGeometry()
        # Leave room for the window title bar / frame plus a comfortable margin
        # so the window never fills the whole screen (it scrolls past the cap).
        frame_extra = max(0, self.frameGeometry().height() - self.height())
        cap = int(avail.height() * 0.85) - frame_extra
        self.setMaximumHeight(cap)
        wanted = min(wanted, cap)
        self.resize(self.width(), wanted)

        # Keep the (now taller) window inside the screen — grow upward when the
        # bottom would spill over.  Only once shown, so we don't fight the
        # dialog's initial centering.
        if self.isVisible():
            fg = self.frameGeometry()
            new_x = min(
                max(fg.x(), avail.left()),
                max(avail.left(), avail.right() - fg.width()),
            )
            new_y = min(
                max(fg.y(), avail.top()),
                max(avail.top(), avail.bottom() - fg.height()),
            )
            if (new_x, new_y) != (fg.x(), fg.y()):
                self.move(new_x, new_y)

    def _on_delete_all_runs_clicked(self) -> None:
        if self._on_delete_all_runs is None:
            return
        token = tr_ui(_T.ADVANCED_DELETE_RUNS_TOKEN)
        text, ok = QInputDialog.getText(
            self,
            tr_ui(_T.ADVANCED_DELETE_RUNS_TITLE),
            tr_ui(_T.ADVANCED_DELETE_RUNS_PROMPT),
        )
        if not ok or text.strip() != token:
            return  # cancelled or confirmation text did not match
        deleted = self._on_delete_all_runs()
        if deleted <= 0:
            QMessageBox.information(
                self,
                tr_ui(_T.ADVANCED_DELETE_RUNS_TITLE),
                tr_ui(_T.ADVANCED_DELETE_RUNS_NONE),
            )
            return
        QMessageBox.information(
            self,
            tr_ui(_T.ADVANCED_DELETE_RUNS_TITLE),
            tr_ui(_T.ADVANCED_DELETE_RUNS_SUCCESS).format(count=deleted),
        )
        # Nothing left to delete this session.
        self._btn_delete_runs.setEnabled(False)

    def _load(self, settings: GlobalSettings) -> None:
        self._author.setText(settings.author)
        self._organization.setText(settings.organization)
        idx = self._line_freq.findData(settings.line_frequency_hz)
        self._line_freq.setCurrentIndex(idx if idx >= 0 else 0)
        theme_idx = self._theme.findData(settings.theme)
        self._theme.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
        self._skip_reset.setChecked(settings.skip_reset)
        self._keep_auto_cal.setChecked(settings.keep_auto_calibration)
