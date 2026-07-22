"""
extra_widgets/import_measure_dialog.py
--------------------------------------
Modal for importing external measurement files as a new setup.

The user names the setup, chooses the CSV dialect (delimiter + quote
character), and collects one or more data files via drag-and-drop or a file
browser.  As with :class:`SetupMetadataDialog`, the owner (presenter) passes an
``on_submit`` callback: returning an error string keeps the modal open and
shows the message in red (the import validation lists every problematic file),
returning ``None`` accepts/closes the dialog.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.data_export import csv_dialect_is_valid
from wizard_4155_4156.models.data_import import (
    WHITESPACE_DELIMITER,
    CsvOptions,
)
from wizard_4155_4156.styles.icons import AppIcon24, app_icon
from wizard_4155_4156.styles.stylesheets import (
    error_bar_stylesheet,
    import_drop_zone_stylesheet,
    import_file_list_stylesheet,
    runs_menu_button_stylesheet,
    runs_secondary_button_stylesheet,
    settings_dialog_stylesheet,
)

_T = CommandWizardText

#: on_submit(name, description, file_paths, csv_options) → error string | None
SubmitCallback = Callable[[str, str, list[str], CsvOptions], Optional[str]]


def _dragged_paths(event) -> list[str]:
    """Local file paths carried by a drag/drop event (empty if none)."""
    return [
        u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()
    ]


class _FileDropZone(QFrame):
    """Dashed drop target accepting local files dragged from the OS."""

    files_dropped = Signal(list)  # list[str] of local file paths

    def __init__(self, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(72)
        self.set_active(False)
        lay = QVBoxLayout(self)
        label = QLabel(hint)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        lay.addWidget(label)

    def set_active(self, active: bool) -> None:
        """Toggle the accent (drag-hover) border."""
        self.setStyleSheet(import_drop_zone_stylesheet(active))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _dragged_paths(event):
            self.set_active(True)
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        # Explicitly re-accept every move — some platforms reset the accept
        # state between events, which silently kills the drop.
        if _dragged_paths(event):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.set_active(False)
        paths = _dragged_paths(event)
        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)


class ImportMeasureDialog(QDialog):
    """Collects a name, CSV options and data files for an import.

    Two personas share this modal:

    * **New setup** (default): ``name`` is the setup's name, required.
    * **Runs of an existing setup** (``name_for_single_file=True``): ``name``
      is the run's name and only applies — and is only required — while
      exactly one file is selected; with several files each run is named
      after its file.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        on_submit: Optional[SubmitCallback] = None,
        *,
        title: str | None = None,
        name_label: str | None = None,
        name_placeholder: str | None = None,
        suggested_name: str = "",
        hint: str | None = None,
        name_for_single_file: bool = False,
    ) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        self._paths: list[str] = []
        self._title = title or tr_ui(_T.RUNS_IMPORT_TITLE)
        self._name_label = name_label or tr_ui(_T.RUNS_IMPORT_NAME_LABEL)
        self._name_placeholder = name_placeholder or tr_ui(
            _T.RUNS_IMPORT_NAME_PLACEHOLDER
        )
        self._hint = hint or tr_ui(_T.RUNS_IMPORT_HINT)
        self._name_for_single_file = name_for_single_file
        self.setWindowTitle(self._title)
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setStyleSheet(settings_dialog_stylesheet())
        # Accept drops on the whole dialog, not just the dashed zone — the
        # zone is the visual affordance, but any spot in the modal works.
        self.setAcceptDrops(True)
        self._build_ui()
        self._name.setText(suggested_name)
        self._update_ok_enabled()
        self._apply_height()

    # ── Dialog-wide drag-and-drop ────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _dragged_paths(event):
            self._drop_zone.set_active(True)
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if _dragged_paths(event):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._drop_zone.set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._drop_zone.set_active(False)
        paths = _dragged_paths(event)
        if paths:
            event.acceptProposedAction()
            self._add_files(paths)

    # ── Public API ───────────────────────────────────────────────────────────

    def get_name(self) -> str:
        return self._name.text().strip()

    def get_description(self) -> str:
        return self._description.toPlainText().strip()

    def get_file_paths(self) -> list[str]:
        return list(self._paths)

    def get_csv_options(self) -> CsvOptions:
        return CsvOptions(
            delimiter=self._delimiter.currentData(),
            quotechar=self._quote.currentData(),
            decimal=self._decimal.currentData(),
        )

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # The form can outgrow short screens, so the body scrolls while the
        # Cancel/OK bar stays pinned; the dialog height is clamped to the
        # screen in _apply_height().  Reuses the settings-dialog scroll QSS.
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
        root.setSpacing(12)

        heading = QLabel(self._title)
        heading.setObjectName("section")
        root.addWidget(heading)

        root.addWidget(QLabel(self._name_label))
        self._name = QLineEdit()
        self._name.setPlaceholderText(self._name_placeholder)
        self._name.textChanged.connect(self._update_ok_enabled)
        self._name.textChanged.connect(self._clear_error)
        root.addWidget(self._name)

        root.addWidget(QLabel(tr_ui(_T.RUNS_IMPORT_DESC_LABEL)))
        self._description = QPlainTextEdit()
        self._description.setPlaceholderText(
            tr_ui(_T.RUNS_IMPORT_DESC_PLACEHOLDER)
        )
        self._description.setFixedHeight(70)
        root.addWidget(self._description)

        root.addLayout(self._build_format_row())
        root.addWidget(self._build_drop_zone())
        root.addLayout(self._build_browse_row())

        self._files = QListWidget()
        self._files.setStyleSheet(import_file_list_stylesheet())
        self._files.setFixedHeight(120)
        root.addWidget(self._files)

        hint = QLabel(self._hint)
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Errors can list one line per bad file.  The whole modal now scrolls
        # (see _build_ui), so the error grows to fit its content and the outer
        # scroll — and _show_error scrolls it into view — instead of being
        # clipped inside a nested fixed-height box.
        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.setStyleSheet(error_bar_stylesheet())
        self._error.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._error.setVisible(False)
        root.addWidget(self._error)
        root.addStretch(1)

        button_bar = QWidget()
        button_bar.setObjectName("settings-buttonbar")
        buttons = QHBoxLayout(button_bar)
        buttons.setContentsMargins(22, 10, 22, 16)
        buttons.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_ok = QPushButton(tr_ui(_T.RUNS_IMPORT_BTN_OK))
        self._btn_ok.setObjectName("primary")
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self._handle_submit)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_ok)
        outer.addWidget(button_bar, 0)
        self._button_bar = button_bar

    def _build_format_row(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self._format = QComboBox()
        self._format.addItem(tr_ui(_T.RUNS_IMPORT_FMT_CSV))

        self._delimiter = QComboBox()
        self._delimiter.addItem(tr_ui(_T.RUNS_IMPORT_DELIM_COMMA), ",")
        self._delimiter.addItem(tr_ui(_T.RUNS_IMPORT_DELIM_SEMI), ";")
        self._delimiter.addItem(tr_ui(_T.RUNS_IMPORT_DELIM_TAB), "\t")
        self._delimiter.addItem(
            tr_ui(_T.RUNS_IMPORT_DELIM_WS), WHITESPACE_DELIMITER
        )

        self._quote = QComboBox()
        self._quote.addItem(tr_ui(_T.RUNS_IMPORT_QUOTE_DOUBLE), '"')
        self._quote.addItem(tr_ui(_T.RUNS_IMPORT_QUOTE_SINGLE), "'")
        self._quote.addItem(tr_ui(_T.RUNS_IMPORT_QUOTE_NONE), None)

        self._decimal = QComboBox()
        self._decimal.addItem(tr_ui(_T.RUNS_IMPORT_DECIMAL_POINT), ".")
        self._decimal.addItem(tr_ui(_T.RUNS_IMPORT_DECIMAL_COMMA), ",")

        self._dialect_combos = (
            self._delimiter,
            self._decimal,
            self._quote,
        )
        self._valid_dialect = tuple(
            combo.currentIndex() for combo in self._dialect_combos
        )
        for combo in self._dialect_combos:
            combo.currentIndexChanged.connect(
                lambda _i, c=combo: self._on_dialect_changed(c)
            )

        cells = [
            (_T.RUNS_IMPORT_FORMAT_LABEL, self._format, 0, 0),
            (_T.RUNS_IMPORT_DELIM_LABEL, self._delimiter, 0, 2),
            (_T.RUNS_IMPORT_QUOTE_LABEL, self._quote, 1, 0),
            (_T.RUNS_IMPORT_DECIMAL_LABEL, self._decimal, 1, 2),
        ]
        for text, combo, r, c in cells:
            grid.addWidget(QLabel(tr_ui(text)), r, c)
            grid.addWidget(combo, r, c + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        return grid

    def _on_dialect_changed(self, combo: QComboBox) -> None:
        """Accept the new dialect or revert *combo* with an explanation.

        Same uniform rule as the Table page export options
        (``csv_dialect_is_valid``): comma may be both the delimiter and the
        decimal separator only when fields are quoted.  Quoting does not
        apply when splitting on whitespace, so the quote combo is disabled
        there.
        """
        if csv_dialect_is_valid(
            self._delimiter.currentData(),
            self._decimal.currentData(),
            self._quote.currentData(),
        ):
            self._valid_dialect = tuple(
                c.currentIndex() for c in self._dialect_combos
            )
        else:
            for c, index in zip(self._dialect_combos, self._valid_dialect):
                c.blockSignals(True)
                c.setCurrentIndex(index)
                c.blockSignals(False)
            QToolTip.showText(
                combo.mapToGlobal(QPoint(0, combo.height())),
                tr_ui(_T.CSV_DIALECT_CONFLICT),
                combo,
            )
        self._quote.setEnabled(
            self._delimiter.currentData() != WHITESPACE_DELIMITER
        )

    def _build_drop_zone(self) -> QWidget:
        self._drop_zone = _FileDropZone(tr_ui(_T.RUNS_IMPORT_DROP_HINT))
        self._drop_zone.files_dropped.connect(self._add_files)
        return self._drop_zone

    def _build_browse_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton(tr_ui(_T.RUNS_IMPORT_BROWSE))
        btn.setIcon(app_icon(AppIcon24.FOLDER))
        btn.setIconSize(QSize(16, 16))
        btn.setStyleSheet(runs_secondary_button_stylesheet())
        btn.clicked.connect(self._on_browse)
        row.addWidget(btn)
        return row

    # ── File collection ──────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            tr_ui(_T.RUNS_IMPORT_BROWSE_TITLE),
            "",
            tr_ui(_T.RUNS_IMPORT_FILE_FILTER),
        )
        if paths:
            self._add_files(paths)

    def _add_files(self, paths: list[str]) -> None:
        for path in paths:
            if os.path.isfile(path) and path not in self._paths:
                self._paths.append(path)
        self._rebuild_file_list()
        self._clear_error()
        self._update_ok_enabled()

    def _remove_file(self, path: str) -> None:
        self._paths = [p for p in self._paths if p != path]
        self._rebuild_file_list()
        self._clear_error()
        self._update_ok_enabled()

    def _rebuild_file_list(self) -> None:
        self._files.clear()
        for path in self._paths:
            row = QWidget()
            # Named + styled-background so the QSS hover rule paints on it
            # (the item's own :hover never fires under an item widget).
            row.setObjectName("import_row")
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            lay = QHBoxLayout(row)
            lay.setContentsMargins(10, 4, 6, 4)
            lay.setSpacing(6)
            label = QLabel(os.path.basename(path))
            label.setToolTip(path)
            lay.addWidget(label, stretch=1)
            remove = QToolButton()
            remove.setIcon(app_icon(AppIcon24.X))
            remove.setIconSize(QSize(14, 14))
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.setStyleSheet(runs_menu_button_stylesheet())
            remove.clicked.connect(
                lambda _=False, p=path: self._remove_file(p)
            )
            lay.addWidget(remove)
            item = QListWidgetItem()
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            # Height from the row's own layout so the label never clips;
            # width 0 lets the list decide (avoids horizontal scrolling).
            item.setSizeHint(QSize(0, max(30, row.sizeHint().height())))
            self._files.addItem(item)
            self._files.setItemWidget(item, row)

    # ── Submit ───────────────────────────────────────────────────────────────

    def _is_submittable(self) -> bool:
        if not self._paths:
            return False
        if self._name_for_single_file:
            # The name only names a lone file's run; several files are
            # named after themselves so no name is needed.
            return len(self._paths) != 1 or bool(self.get_name())
        return bool(self.get_name())

    def _update_ok_enabled(self) -> None:
        if self._name_for_single_file:
            self._name.setEnabled(len(self._paths) <= 1)
        self._btn_ok.setEnabled(self._is_submittable())

    def _handle_submit(self) -> None:
        name = self.get_name()
        if not self._is_submittable():
            return
        self._clear_error()
        if self._on_submit is None:
            self.accept()
            return
        error = self._on_submit(
            name, self.get_description(), self.get_file_paths(),
            self.get_csv_options(),
        )
        if error:
            self._show_error(error)
            return
        self.accept()

    def _show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)
        self._apply_height()
        # Bring the (bottom-most) error into view within the scrolled body.
        self._scroll.ensureWidgetVisible(self._error)

    def _clear_error(self) -> None:
        self._error.clear()
        self._error.setVisible(False)
        self._apply_height()

    # ── Sizing ───────────────────────────────────────────────────────────────

    def _apply_height(self) -> None:
        """Size the dialog to its content, clamped to the visible screen.

        Mirrors ``SettingsDialog``: cap the height (the body scrolls past it)
        and shift the window up so the whole modal stays on-screen.
        """
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
