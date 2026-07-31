"""
extra_widgets/queue_panel_dialog.py
-----------------------------------
The measurement-queue panel.

Deliberately **non-modal**, and a **top-level window in its own right**: the
queue is managed while the user keeps working on the Runs page (selecting
another setup and adding it to the batch), so a modal dialog would defeat the
purpose.  Like ``DocumentationWindow``, it is created with **no parent** — a
top-level widget that still has a parent is a *secondary* window, which the
window manager keeps above its owner, gives no taskbar entry of its own, and
usually cannot be minimised independently.  Parentless, it gets the standard
frame (minimise / maximise / close) and its own taskbar button.

The presenter owns the single instance and brings it forward with
:meth:`present`, which also restores it when the user has minimised it.

Pure view: user actions leave as ``*_requested`` signals carrying the row's
``uid``; state arrives through ``display_*``.  It imports the Qt-free
``QueueRow``/``QueueItemStatus`` DTOs only — never the presenter, never the
ORM — the same way the Runs page imports ``SetupRow``.

Rows are widget-based (position, status, labels, reorder + remove buttons),
following the ``setItemWidget`` pattern already used by the file list in
``ImportMeasureDialog``, and are selectable like the Runs-page lists — the
selection is view-local (nothing in the queue depends on it) and is restored by
uid after each rebuild.  The running row is visually distinct: accent fill,
bold title, and no editing controls — a measurement in flight cannot be
reordered or cancelled (the pool thread is parked inside a blocking ``*OPC?``
read for its whole duration).
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.measurement_queue import (
    QueueItemStatus,
    QueueRow,
)
from wizard_4155_4156.styles.icons import (
    AppIcon24,
    app_icon,
    hover_tinted_icon,
    tinted_pixmap,
)
from wizard_4155_4156.styles.stylesheets import (
    queue_list_stylesheet,
    queue_notice_stylesheet,
    queue_row_position_stylesheet,
    queue_row_runtime_stylesheet,
    queue_row_status_stylesheet,
    queue_row_title_stylesheet,
    queue_state_chip_stylesheet,
    row_remove_button_stylesheet,
    runs_empty_label_stylesheet,
    runs_menu_button_stylesheet,
    runs_secondary_button_stylesheet,
    settings_dialog_stylesheet,
    status_color,
)
from wizard_4155_4156.styles.theme import PALETTE as P

_T = CommandWizardText

#: Per-status row appearance: (chip/text kind, leading icon or "").
_STATUS_LOOK: dict[QueueItemStatus, tuple[str, str]] = {
    QueueItemStatus.WAITING: ("muted", ""),
    QueueItemStatus.RUNNING: ("info", AppIcon24.PLAY),
    QueueItemStatus.DONE: ("ok", AppIcon24.CHECK),
    QueueItemStatus.FAILED: ("critical", AppIcon24.ALERT_TRIANGLE),
}

#: Queue state (``QueueState`` value) → header chip color kind.
_STATE_KIND = {
    "RUNNING": "info",
    "PENDING": "muted",
    "PAUSED": "warning",
    "IDLE": "muted",
}

_ICON_PX = 14
_ROW_MIN_HEIGHT = 56
_TOOL_PX = 14
_REMOVE_PX = 12
_REMOVE_BOX = 20
#: State-chip inner margins. The vertical one is load-bearing: it holds the
#: chip above 2 × RADIUS_PILL so its rounded corners actually render.
_CHIP_PAD_X = 12
_CHIP_PAD_Y = 9

#: Item data role carrying a row's queue uid (mirrors ``_ID_ROLE`` on the
#: Runs page), so a selection survives the list being rebuilt.
_UID_ROLE = Qt.ItemDataRole.UserRole


class _QueueRowWidget(QWidget):
    """A queue row that reports clicks so the list can select it.

    The row widget covers its list item, so the click never reaches the
    viewport on its own and ``QListWidget`` would never move the selection.
    Forwarding it explicitly is more predictable than relying on Qt's
    ignored-event propagation through the label/layout children.

    The event is **accepted**, not passed up: letting it also reach the
    viewport would have the list re-resolve the row from the mapped cursor
    position, so two mechanisms would race to set the same selection.
    """

    clicked = Signal(str)  # uid

    def __init__(self, uid: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._uid = uid

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.clicked.emit(self._uid)
        event.accept()


class QueuePanelDialog(QWidget):
    """Independent, non-modal window listing the scheduled measurements.

    A plain top-level ``QWidget`` rather than a ``QDialog``: it never returns a
    result and must not participate in the modal stack, so the dialog machinery
    would only add an accidental ``exec``/``accept`` surface.  It still wears
    the shared dialog stylesheet so it reads as part of the application.

    **Construct it without a parent** — that is what makes it a real window
    (own taskbar entry, own minimise button) instead of a secondary window
    pinned above the main one.
    """

    remove_requested = Signal(str)  # uid
    move_requested = Signal(str, int)  # uid, delta (-1 up / +1 down)
    clear_requested = Signal()
    clear_finished_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Explicit for clarity: parentless this is redundant, but it keeps the
        # widget a window even if someone later passes a parent.
        self.setWindowFlag(Qt.WindowType.Window, True)
        # The window title doubles as the taskbar label, so it names the app
        # too — same convention as DocumentationWindow.
        self.setWindowTitle(tr_ui(_T.QUEUE_WINDOW_TITLE))
        # Never let this window alone keep the application alive: closing the
        # main window must end the session even if the queue is still open.
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setMinimumWidth(820)
        self.resize(940, 500)
        self.setStyleSheet(settings_dialog_stylesheet())
        self._paused = False
        self._waiting = 0
        # Which row the user picked. Selection is view-local — nothing in the
        # queue depends on it — but it must survive the frequent rebuilds.
        self._selected_uid = ""
        self._setup_ui()

    # ── Window handling ──────────────────────────────────────────────────────

    def present(self) -> None:
        """Bring the window forward, restoring it if it was minimised.

        ``show()`` alone does not un-minimise an already-visible window, so
        clicking Queue while the window sits in the taskbar would appear to do
        nothing.  ``showNormal`` restores it without clobbering a maximised
        state the user chose.
        """
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    # ── Display API (called by QueuePresenter) ───────────────────────────────

    def display_items(self, rows: List[QueueRow]) -> None:
        # The presenter rebuilds on every pump and status tick, so the picked
        # row is remembered by uid and re-applied afterwards; an entry that has
        # since left the queue simply drops out of the selection.
        wanted = self._selected_uid
        self._list.clear()
        self._waiting = sum(
            1 for r in rows if r.status is QueueItemStatus.WAITING
        )
        if not rows:
            self._add_placeholder(tr_ui(_T.QUEUE_EMPTY))
        for row in rows:
            self._add_row(row)
        self._select_uid(wanted)
        self._btn_clear.setEnabled(self._waiting > 0)
        self._btn_clear_done.setEnabled(
            any(
                r.status in (QueueItemStatus.DONE, QueueItemStatus.FAILED)
                for r in rows
            )
        )

    def display_state(self, state: str, text: str, paused: bool) -> None:
        self._paused = paused
        self._state_label.setText(text)
        self._state_chip.setStyleSheet(
            queue_state_chip_stylesheet(_STATE_KIND.get(state, "muted"))
        )
        self._btn_pause.setText(
            tr_ui(_T.QUEUE_BTN_RESUME if paused else _T.QUEUE_BTN_PAUSE)
        )

    def display_notice(self, text: str) -> None:
        self._notice.setText(text)
        self._notice.setVisible(bool(text))

    # ── Build ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        root.addLayout(self._build_header())

        self._notice = QLabel("")
        self._notice.setStyleSheet(queue_notice_stylesheet())
        self._notice.setWordWrap(True)
        self._notice.setVisible(False)
        root.addWidget(self._notice)

        self._list = QListWidget()
        self._list.setStyleSheet(queue_list_stylesheet())
        self._list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        root.addWidget(self._list, stretch=1)

        root.addLayout(self._build_buttons())

    def _build_header(self) -> QHBoxLayout:
        head = QHBoxLayout()
        head.setSpacing(10)
        title = QLabel(tr_ui(_T.QUEUE_TITLE))
        title.setObjectName("section")
        head.addWidget(title)
        head.addStretch()

        self._state_chip = QFrame()
        self._state_chip.setObjectName("queue_state_chip")
        # Object name + styled background is the pill idiom used by
        # sys_status_pill; the rule keys off the name.
        self._state_chip.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )
        chip_row = QHBoxLayout(self._state_chip)
        # The vertical margins keep the chip at least twice RADIUS_PILL tall,
        # which is what lets the rounded corners render at all — see
        # queue_state_chip_stylesheet.
        chip_row.setContentsMargins(_CHIP_PAD_X, _CHIP_PAD_Y, _CHIP_PAD_X,
                                    _CHIP_PAD_Y)
        chip_row.setSpacing(0)
        self._state_label = QLabel(tr_ui(_T.QUEUE_STATE_IDLE))
        chip_row.addWidget(self._state_label)
        self._state_chip.setStyleSheet(queue_state_chip_stylesheet("muted"))
        head.addWidget(self._state_chip)
        return head

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._btn_pause = QPushButton(tr_ui(_T.QUEUE_BTN_PAUSE))
        self._btn_pause.setStyleSheet(runs_secondary_button_stylesheet())
        self._btn_pause.clicked.connect(self._on_pause_clicked)
        row.addWidget(self._btn_pause)

        self._btn_clear_done = QPushButton(tr_ui(_T.QUEUE_BTN_CLEAR_FINISHED))
        self._btn_clear_done.setStyleSheet(runs_secondary_button_stylesheet())
        self._btn_clear_done.clicked.connect(self.clear_finished_requested)
        row.addWidget(self._btn_clear_done)

        self._btn_clear = QPushButton(tr_ui(_T.QUEUE_BTN_CLEAR))
        self._btn_clear.setObjectName("danger")
        self._btn_clear.clicked.connect(self._on_clear_clicked)
        row.addWidget(self._btn_clear)

        row.addStretch()

        close = QPushButton(tr_ui(_T.QUEUE_BTN_CLOSE))
        close.setObjectName("primary")
        close.clicked.connect(self.close)
        row.addWidget(close)
        return row

    # ── Rows ─────────────────────────────────────────────────────────────────

    def _add_row(self, row: QueueRow) -> None:
        running = row.status is QueueItemStatus.RUNNING
        kind, icon_path = _STATUS_LOOK.get(row.status, ("muted", ""))

        widget = _QueueRowWidget(row.uid)
        widget.clicked.connect(self._select_uid)
        # Named + styled-background so the QSS hover/running rule paints on it
        # (the item's own :hover never fires under an item widget).
        widget.setObjectName("queue_row_running" if running else "queue_row")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(widget)
        lay.setContentsMargins(10, 6, 6, 6)
        lay.setSpacing(8)

        position = QLabel(str(row.position) if row.position else "")
        position.setStyleSheet(queue_row_position_stylesheet(running))
        position.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(position)

        if icon_path:
            glyph = QLabel()
            glyph.setPixmap(
                tinted_pixmap(icon_path, status_color(kind), _ICON_PX)
            )
            glyph.setStyleSheet("background: transparent;")
            lay.addWidget(glyph)

        lay.addLayout(self._build_row_text(row, running, kind), stretch=1)

        runtime = QLabel(row.runtime_label)
        runtime.setStyleSheet(queue_row_runtime_stylesheet())
        lay.addWidget(runtime)

        lay.addWidget(
            self._row_tool(
                widget, app_icon(AppIcon24.ARROW_UP), tr_ui(_T.QUEUE_TT_UP),
                row.can_move_up,
                lambda: self.move_requested.emit(row.uid, -1),
            )
        )
        lay.addWidget(
            self._row_tool(
                widget, app_icon(AppIcon24.ARROW_DOWN),
                tr_ui(_T.QUEUE_TT_DOWN), row.can_move_down,
                lambda: self.move_requested.emit(row.uid, 1),
            )
        )
        lay.addWidget(
            self._row_remove(
                widget, row.can_edit,
                lambda: self.remove_requested.emit(row.uid),
            )
        )

        item = QListWidgetItem()
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        )
        item.setData(_UID_ROLE, row.uid)
        # Height from the row's own layout so nothing clips; width 0 lets the
        # list decide (avoids a horizontal scrollbar).
        item.setSizeHint(
            QSize(0, max(_ROW_MIN_HEIGHT, widget.sizeHint().height()))
        )
        self._list.addItem(item)
        self._list.setItemWidget(item, widget)

    @staticmethod
    def _build_row_text(
        row: QueueRow, running: bool, kind: str
    ) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        title = QLabel(
            tr_ui(_T.QUEUE_ROW_ARROW).format(
                setup=row.setup_label, run=row.run_name
            )
            if row.run_name
            else row.setup_label
        )
        title.setStyleSheet(queue_row_title_stylesheet(running))
        col.addWidget(title)
        status = QLabel(row.status_text)
        status.setWordWrap(True)
        status.setStyleSheet(queue_row_status_stylesheet(kind))
        col.addWidget(status)
        return col

    @staticmethod
    def _row_tool(
        parent: QWidget, icon: QIcon, tooltip: str, enabled: bool, slot
    ) -> QToolButton:
        """Small inline row action; hidden (not greyed) when unavailable.

        A disabled control on a running row invites clicking something that can
        never work — a measurement in flight cannot be reordered or cancelled.
        The slot still *reserves* its space while hidden (the fixed-holder
        idiom ``ProjectRow`` uses for its hover-revealed ✕), so every row keeps
        the same column geometry and nothing shifts as statuses change.

        ``parent`` is required, not optional: ``setVisible(True)`` on a
        parentless widget makes it a real top-level window, so building rows
        would flash a stray window per button before the layout reparented it.
        """
        btn = QToolButton(parent)
        btn.setIcon(icon)
        btn.setIconSize(QSize(_TOOL_PX, _TOOL_PX))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setStyleSheet(runs_menu_button_stylesheet())
        btn.clicked.connect(lambda _checked=False: slot())
        policy = btn.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        btn.setSizePolicy(policy)
        btn.setVisible(enabled)
        return btn

    @staticmethod
    def _row_remove(parent: QWidget, enabled: bool, slot) -> QToolButton:
        """The trash button — red circle on hover, like the ProjectRow ✕.

        Uses ``hover_tinted_icon`` so the glyph flips to the on-accent color as
        the destructive red fill appears; a fixed tint would disappear into it.
        """
        btn = QToolButton(parent)
        btn.setIcon(
            hover_tinted_icon(
                AppIcon24.TRASH, P.TEXT_SECONDARY, P.TEXT_ON_ACCENT,
                _REMOVE_PX,
            )
        )
        btn.setIconSize(QSize(_REMOVE_PX, _REMOVE_PX))
        btn.setFixedSize(_REMOVE_BOX, _REMOVE_BOX)
        btn.setToolTip(tr_ui(_T.QUEUE_TT_REMOVE))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setStyleSheet(row_remove_button_stylesheet())
        btn.clicked.connect(lambda _checked=False: slot())
        policy = btn.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        btn.setSizePolicy(policy)
        btn.setVisible(enabled)
        return btn

    # ── Selection ────────────────────────────────────────────────────────────

    def _select_uid(self, uid: str) -> None:
        """Select the row carrying ``uid``; a no-op when it is not listed."""
        if not uid:
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(_UID_ROLE) == uid:
                self._list.setCurrentItem(item)
                return

    def _on_current_item_changed(self) -> None:
        item = self._list.currentItem()
        uid = item.data(_UID_ROLE) if item is not None else None
        self._selected_uid = uid or ""

    def _add_placeholder(self, text: str) -> None:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(runs_empty_label_stylesheet())
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(0, max(80, label.sizeHint().height() + 24)))
        self._list.addItem(item)
        self._list.setItemWidget(item, label)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_pause_clicked(self) -> None:
        if self._paused:
            self.resume_requested.emit()
        else:
            self.pause_requested.emit()

    def _on_clear_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            tr_ui(_T.QUEUE_CLEAR_TITLE),
            tr_ui(_T.QUEUE_CLEAR_MSG).format(count=self._waiting),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_requested.emit()
