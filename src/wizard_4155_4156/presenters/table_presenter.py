"""
presenters/table_presenter.py
-----------------------------
Presenter for the Table View page.

Mediates ``TablePageView`` between two transparent data sources:

* **Project** — saved setups and their completed executions, read from the open
  project database (via ``ProjectManager``).
* **Live data** — the last in-memory acquired dataset (a static snapshot from
  ``ConnectorPresenter.data_ready``), surfaced as a synthetic "Live Data" setup
  with a single "Live" execution.  This covers data produced by the legacy
  Measurements page or by a setup that no longer exists.

It also drives export: the action button copies the generated code to the
clipboard (code formats) or saves the data to a file (table formats).  All DB
access happens on the GUI thread here — no ``Session`` ever reaches a worker.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from wizard_4155_4156.db.assembler import execution_to_data_dict
from wizard_4155_4156.db.repository import (
    ExecRow,
    ExecutionRepository,
    SetupRepository,
)
from wizard_4155_4156.extra_widgets.file_dialogs import (
    DialogPurpose,
    get_save_path,
)
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.data_export import (
    FORMATS,
    SPECS,
    CsvOptions,
    DataFormat,
    FormatKind,
    build_zip,
    csv_dialect_is_valid,
    export_filename,
    generate_bytes,
    generate_text,
    is_code,
    ordered_dataset,
    sanitize_filename,
)
from wizard_4155_4156.views.pages.table_page import TablePageView

#: Sentinel ids for the synthetic "Live Data" setup / "Live" execution.
LIVE_SETUP_ID = -1
LIVE_EXEC_ID = -1

_FORMAT_LABELS: dict[DataFormat, CommandWizardText] = {
    DataFormat.CSV: CommandWizardText.TABLE_FMT_CSV,
    DataFormat.XLSX: CommandWizardText.TABLE_FMT_XLSX,
    DataFormat.PY_PURE: CommandWizardText.TABLE_FMT_PY_PURE,
    DataFormat.PY_NUMPY: CommandWizardText.TABLE_FMT_PY_NUMPY,
    DataFormat.C_ARRAY: CommandWizardText.TABLE_FMT_C_ARRAY,
    DataFormat.MATLAB: CommandWizardText.TABLE_FMT_MATLAB,
}

#: CSV dialect option values; indices mirror the view's combo order
#: (same positional pattern as ``FORMATS``).
_CSV_DELIMITERS: list[str] = [",", ";", "\t", " "]
_CSV_DECIMALS: list[str] = [".", ","]
_CSV_QUOTES: list[str | None] = ['"', "'", None]

_DELIM_LABELS = [
    CommandWizardText.TABLE_DELIM_COMMA,
    CommandWizardText.TABLE_DELIM_SEMICOLON,
    CommandWizardText.TABLE_DELIM_TAB,
    CommandWizardText.TABLE_DELIM_SPACE,
]
_DECIMAL_LABELS = [
    CommandWizardText.TABLE_DEC_DOT,
    CommandWizardText.TABLE_DEC_COMMA,
]
_QUOTE_LABELS = [
    CommandWizardText.TABLE_QUOTE_DOUBLE,
    CommandWizardText.TABLE_QUOTE_SINGLE,
    CommandWizardText.TABLE_QUOTE_NONE,
]


class TablePresenter(QObject):
    """Mediates TablePageView ↔ project database + the live-data cache."""

    #: Ask MainWindow to bring the Table page into view.
    navigation_requested = Signal()
    #: Transient status text for MainWindow's status bar.
    status_message = Signal(str)

    def __init__(
        self,
        view: TablePageView,
        project_manager,
        connector_presenter,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._projects = project_manager
        self._connector = connector_presenter

        self._live_data: Optional[dict[str, list[float]]] = None
        self._current_setup_id: Optional[int] = None
        self._current_exec_id: Optional[int] = None

        # Snapshots of the last displayed combo items + render state, used to
        # skip re-rendering (and thus preserve scroll/column state) when the
        # page is re-activated with unchanged data.
        self._last_setups: list[tuple[int, str]] = []
        self._last_execs: list[tuple[int, str, bool]] = []
        self._exec_dates: dict[int, datetime] = {}
        self._live_generation = 0
        self._rendered_key: Optional[tuple] = None

        self._init_formats()
        self._connect()

    # ── Public API (called by MainWindow / other presenters) ─────────────────

    def set_database(self, _db=None) -> None:
        """Refresh the setup list when a project is created/opened/closed."""
        self._last_setups = []
        self._last_execs = []
        self._exec_dates = {}
        self._rendered_key = None
        self._refresh(keep_selection=False)

    def show_live_data(self, data: Mapping[str, Sequence[float]]) -> None:
        """Cache a freshly acquired dataset and show it as 'Live'."""
        self._live_generation += 1
        self._live_data = {
            name: [float(v) for v in values] for name, values in data.items()
        }
        self._view.display_setups(self._setup_items())
        self._select_setup(LIVE_SETUP_ID)
        self._load_executions(LIVE_SETUP_ID)
        self.navigation_requested.emit()

    def show_execution(self, setup_id: int, execution_id: int) -> None:
        """Select a specific project setup + execution and show it."""
        self._view.display_setups(self._setup_items())
        self._select_setup(setup_id)
        self._load_executions(setup_id, prefer=execution_id)
        self.navigation_requested.emit()

    # ── Wiring ───────────────────────────────────────────────────────────────

    def _init_formats(self) -> None:
        self._view.set_formats([tr_ui(_FORMAT_LABELS[fmt]) for fmt in FORMATS])
        self._view.select_format(0)
        self._view.set_csv_option_items(
            [tr_ui(t) for t in _DELIM_LABELS],
            [tr_ui(t) for t in _DECIMAL_LABELS],
            [tr_ui(t) for t in _QUOTE_LABELS],
        )
        #: Last accepted (delimiter, decimal, quote) combo indices — the
        #: fallback when the user picks a conflicting dialect combination.
        self._valid_csv_indices = (0, 0, 0)

    def _connect(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)
        v.setup_changed.connect(self._on_setup_changed)
        v.execution_changed.connect(self._on_execution_changed)
        v.format_changed.connect(self._on_format_changed)
        v.action_requested.connect(self._on_action)
        v.save_all_requested.connect(self._on_save_all)
        v.csv_option_changed.connect(self._on_csv_option_changed)
        self._connector.data_ready.connect(self.show_live_data)

    # ── View-signal handlers ─────────────────────────────────────────────────

    def _on_page_activated(self) -> None:
        if self._activation_unchanged():
            self._sync_chrome()
            return
        self._refresh(keep_selection=True)

    def _on_setup_changed(self, setup_id: int) -> None:
        self._current_setup_id = setup_id
        self._load_executions(setup_id)

    def _on_execution_changed(self, execution_id: int) -> None:
        self._current_exec_id = execution_id
        self._refresh_content()

    def _on_format_changed(self, _index: int) -> None:
        self._refresh_content()

    def _on_csv_option_changed(self, which: str) -> None:
        """Accept the new dialect, or revert it and explain why."""
        opts = self._current_csv_options()
        if csv_dialect_is_valid(
            opts.delimiter, opts.decimal_separator, opts.quotechar
        ):
            self._valid_csv_indices = (
                self._view.current_delimiter_index(),
                self._view.current_decimal_index(),
                self._view.current_quote_index(),
            )
            return
        self._view.select_csv_options(*self._valid_csv_indices)
        self._view.show_csv_option_tooltip(
            which, tr_ui(CommandWizardText.CSV_DIALECT_CONFLICT)
        )

    def _on_action(self) -> None:
        data = self._resolve_dataset()
        if not data:
            return
        fmt = self._current_format()
        if is_code(fmt):
            self._copy_code(data, fmt)
        else:
            self._download_table(data, fmt)

    # ── Refresh ──────────────────────────────────────────────────────────────

    def _refresh(self, *, keep_selection: bool) -> None:
        prev_setup = self._current_setup_id if keep_selection else None
        prev_exec = self._current_exec_id if keep_selection else None

        setups = self._setup_items()
        self._last_setups = setups
        self._view.display_setups(setups)
        if not setups:
            self._current_setup_id = None
            self._current_exec_id = None
            self._last_execs = []
            self._view.display_executions([])
            self._show_empty()
            return

        setup_id = prev_setup if _has(setups, prev_setup) else setups[0][0]
        self._select_setup(setup_id)
        self._load_executions(setup_id, prefer=prev_exec)

    def _load_executions(
        self, setup_id: int, prefer: Optional[int] = None
    ) -> None:
        execs = self._exec_items(setup_id)
        self._last_execs = execs
        self._view.display_executions(execs)
        if not execs:
            self._current_exec_id = None
            self._show_empty(tr_ui(CommandWizardText.TABLE_NO_EXEC))
            return
        exec_id = prefer if _has(execs, prefer) else execs[0][0]
        self._view.select_execution(exec_id)
        self._current_exec_id = exec_id
        self._refresh_content()

    def _refresh_content(self) -> None:
        data = self._resolve_dataset()
        if not data:
            self._show_empty()
            return
        self._view.set_action_enabled(True)
        self._view.display_error("")
        fmt = self._current_format()
        key = self._render_key()
        if key != self._rendered_key:
            if is_code(fmt):
                self._view.display_code(
                    generate_text(data, fmt), SPECS[fmt].language
                )
            else:
                self._view.display_table(dict(data))
            self._rendered_key = key
        self._view.set_action_mode("copy" if is_code(fmt) else "download")
        self._sync_chrome()

    def _show_empty(self, message: Optional[str] = None) -> None:
        self._view.set_action_enabled(False)
        self._view.set_export_options_mode("hidden")
        self._view.set_save_all_visible(False)
        self._rendered_key = None
        if message is None:
            message = (
                tr_ui(CommandWizardText.TABLE_NO_SETUP)
                if self._projects.current_db is not None
                else tr_ui(CommandWizardText.TABLE_EMPTY)
            )
        self._view.display_empty(message)

    def _render_key(self) -> tuple:
        """Identity of what the central area shows.  Both table formats share
        one key (the rendered table is identical), so CSV↔XLSX toggles keep
        scroll/column state; each code format renders distinct text."""
        fmt = self._current_format()
        kind_part = fmt if is_code(fmt) else FormatKind.TABLE
        return (
            self._current_setup_id,
            self._current_exec_id,
            kind_part,
            self._live_generation,
        )

    def _activation_unchanged(self) -> bool:
        """True when re-activating the page would re-render identical content
        — executions are immutable, so unchanged combo item lists imply
        unchanged datasets (live data is guarded by ``_live_generation``)."""
        if self._current_exec_id is None or self._rendered_key is None:
            return False
        if self._rendered_key != self._render_key():
            return False
        if self._setup_items() != self._last_setups:
            return False
        return self._exec_items(self._current_setup_id) == self._last_execs

    def _sync_chrome(self) -> None:
        """Options-row mode + Save All state for the current selection."""
        fmt = self._current_format()
        if self._current_exec_id is None or is_code(fmt):
            self._view.set_export_options_mode("hidden")
            self._view.set_save_all_visible(False)
            return
        self._view.set_export_options_mode(
            "csv" if fmt is DataFormat.CSV else "xlsx"
        )
        self._view.set_save_all_visible(True)
        self._view.set_save_all_enabled(
            self._current_setup_id not in (None, LIVE_SETUP_ID)
        )

    # ── Item builders ────────────────────────────────────────────────────────

    def _setup_items(self) -> list[tuple[int, str]]:
        items: list[tuple[int, str]] = []
        if self._live_data:
            items.append(
                (LIVE_SETUP_ID, tr_ui(CommandWizardText.TABLE_LIVE_DATA))
            )
        db = self._projects.current_db
        if db is not None:
            with db.session() as s:
                rows = SetupRepository.list_rows(s)
            items.extend((row.id, row.name) for row in rows)
        return items

    def _exec_items(self, setup_id: int) -> list[tuple[int, str, bool]]:
        """Combo entries ``(id, label, synthetic)`` — the flag lets the
        view tag sample runs with the bookmark icon."""
        if setup_id == LIVE_SETUP_ID:
            return [
                (
                    LIVE_EXEC_ID,
                    tr_ui(CommandWizardText.TABLE_LIVE_EXEC),
                    False,
                )
            ]
        db = self._projects.current_db
        if db is None:
            return []
        with db.session() as s:
            rows = ExecutionRepository.list_rows(s, setup_id)
        self._exec_dates.update(
            (row.id, row.execution_date) for row in rows
        )
        return [
            (row.id, _exec_label(row), row.is_synthetic) for row in rows
        ]

    # ── Dataset resolution ───────────────────────────────────────────────────

    def _resolve_dataset(self) -> Optional[dict[str, list[float]]]:
        exec_id = self._current_exec_id
        if exec_id is None:
            return None
        if exec_id == LIVE_EXEC_ID:
            return self._live_data
        db = self._projects.current_db
        if db is None:
            return None
        with db.session() as s:
            execution = ExecutionRepository.get(s, exec_id)
            if execution is None:
                return None
            return execution_to_data_dict(execution)

    def _current_format(self) -> DataFormat:
        idx = self._view.current_format_index()
        if 0 <= idx < len(FORMATS):
            return FORMATS[idx]
        return FORMATS[0]

    def _current_csv_options(self) -> CsvOptions:
        return CsvOptions(
            delimiter=_pick(
                _CSV_DELIMITERS, self._view.current_delimiter_index()
            ),
            decimal_separator=_pick(
                _CSV_DECIMALS, self._view.current_decimal_index()
            ),
            quotechar=_pick(_CSV_QUOTES, self._view.current_quote_index()),
        )

    def _select_setup(self, setup_id: int) -> None:
        self._current_setup_id = setup_id
        self._view.select_setup(setup_id)

    # ── Export actions ───────────────────────────────────────────────────────

    def _copy_code(
        self, data: Mapping[str, Sequence[float]], fmt: DataFormat
    ) -> None:
        QApplication.clipboard().setText(generate_text(data, fmt))
        self.status_message.emit(tr_ui(CommandWizardText.TABLE_COPIED))

    def _download_table(
        self, data: Mapping[str, Sequence[float]], fmt: DataFormat
    ) -> None:
        data = ordered_dataset(data, self._view.current_column_order())
        ext = SPECS[fmt].extension
        label = tr_ui(_FORMAT_LABELS[fmt])
        # The checkbox only shapes the *suggested* filename; live data has no
        # stored acquisition date, so its timestamp is silently omitted.
        timestamp = (
            self._exec_dates.get(self._current_exec_id)
            if self._view.datetime_in_filename()
            else None
        )
        path = get_save_path(
            self._view,
            DialogPurpose.TABLE_EXPORT,
            tr_ui(CommandWizardText.TABLE_SAVE_TITLE),
            f"{label} (*.{ext})",
            suggested_name=export_filename("data", fmt, timestamp),
        )
        if not path:
            return
        try:
            with open(path, "wb") as fh:
                fh.write(
                    generate_bytes(data, fmt, self._current_csv_options())
                )
        except OSError as exc:
            self._view.display_error(
                tr_ui(CommandWizardText.TABLE_SAVE_ERROR).format(error=exc)
            )
            return
        self._view.display_error("")
        self.status_message.emit(
            tr_ui(CommandWizardText.TABLE_DOWNLOADED).format(path=path)
        )

    def _on_save_all(self) -> None:
        setup_id = self._current_setup_id
        fmt = self._current_format()
        db = self._projects.current_db
        if setup_id in (None, LIVE_SETUP_ID) or is_code(fmt) or db is None:
            return
        order = self._view.current_column_order()
        entries: list[tuple[str, Optional[datetime], dict]] = []
        with db.session() as s:
            for row in ExecutionRepository.list_rows(s, setup_id):
                execution = ExecutionRepository.get(s, row.id)
                if execution is None:
                    continue
                entries.append(
                    (
                        row.name,
                        row.execution_date,
                        ordered_dataset(
                            execution_to_data_dict(execution), order
                        ),
                    )
                )
        if not entries:
            return
        setup_name = next(
            (name for sid, name in self._last_setups if sid == setup_id),
            "data",
        )
        path = get_save_path(
            self._view,
            DialogPurpose.TABLE_EXPORT,
            tr_ui(CommandWizardText.TABLE_SAVE_ALL_TITLE),
            tr_ui(CommandWizardText.TABLE_SAVE_ALL_FILTER),
            suggested_name=f"{sanitize_filename(setup_name)}.zip",
        )
        if not path:
            return
        try:
            payload = build_zip(
                entries,
                fmt,
                csv_options=self._current_csv_options(),
                include_timestamp=self._view.datetime_in_filename(),
            )
            with open(path, "wb") as fh:
                fh.write(payload)
        except OSError as exc:
            self._view.display_error(
                tr_ui(CommandWizardText.TABLE_SAVE_ERROR).format(error=exc)
            )
            return
        self._view.display_error("")
        self.status_message.emit(
            tr_ui(CommandWizardText.TABLE_SAVED_ALL).format(
                count=len(entries), path=path
            )
        )


def _has(items: Sequence[tuple], value: Optional[int]) -> bool:
    return value is not None and any(item[0] == value for item in items)


def _pick(values: Sequence, index: int):
    """Positional combo-index lookup with the same 0-fallback as formats."""
    return values[index] if 0 <= index < len(values) else values[0]


def _exec_label(row: ExecRow) -> str:
    return f"{row.name} · {row.execution_date:%d/%m/%Y %H:%M}"
