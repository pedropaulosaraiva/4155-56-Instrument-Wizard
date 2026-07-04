"""
views/connector_widget.py
--------------------------
View layer for GPIB connection management.

Contains
--------
ConnectorWizardModal   — QDialog displaying bus scan results, status log,
                         and connection controls.
CompactConnectorWidget — QFrame thumbnail shown in ConnectionTopBar.
                         Acts as the single visible entry-point for the
                         GPIB connection workflow.

MVP boundary rules enforced here
---------------------------------
- No GPIB41xxController instantiation.
- No QThreadPool ownership.
- No @Slot business-logic handlers.
- Hardware state changes are communicated IN via display_* methods.
- User intents are communicated OUT via Signal declarations.

The three forwarding methods (scan_bus, connect_to_instrument,
disconnect_bus) exist solely to maintain a stable call interface for
ConnectorWizardModal buttons, which are authored in terms of their
parent widget.  Each method emits the corresponding Signal — the
Presenter subscribes to those signals and performs the actual I/O.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import (
    compact_connector_stylesheet,
    connector_label_model_stylesheet,
    #   connector_label_status_connected_stylesheet,
    connector_label_status_disconnected_stylesheet,
    connector_label_status_idle_stylesheet,
    connector_modal_stylesheet,
    connector_progress_bar_stylesheet,
)

# =============================================================================
# CONNECTOR WIZARD MODAL  (View — QDialog)
# =============================================================================


class ConnectorWizardModal(QDialog):
    """
    Detailed modal for bus scanning, instrument selection, and log monitoring.

    Buttons delegate directly to CompactConnectorWidget's forwarding methods,
    which emit signals consumed by ConnectorPresenter.  The modal never
    communicates with the presenter or the controller directly.
    """

    def __init__(self, parent: "CompactConnectorWidget") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr_ui(CommandWizardText.WIZARD_TITLE))
        self.resize(520, 480)
        self.setModal(True)
        self.parent_widget = parent
        self._setup_ui()
        self.setStyleSheet(connector_modal_stylesheet())

    # ── Display API (called by CompactConnectorWidget display_* methods) ─────

    def update_scan_results(self, results: dict) -> None:
        """Populate the instrument combo with {address: label} pairs."""
        self.combo_equipments.clear()
        for address, label in results.items():
            # address stored as userData; label shown to the user
            self.combo_equipments.addItem(label, address)

    def update_connection_status(self, connected: bool) -> None:
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        self.btn_scan.setEnabled(not connected)
        self.combo_equipments.setEnabled(not connected)

    def append_log(self, msg: str) -> None:
        self.text_log.append(msg)

    def update_progress(self, current: int, total: int, status: str) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_status.setText(status)

    def reset_progress(self) -> None:
        self.progress_bar.setValue(0)
        self.lbl_status.setText(tr_ui(CommandWizardText.IDLE))

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Equipment selection group
        grp_equip = QGroupBox(tr_ui(CommandWizardText.GROUP_EQUIP))
        row = QHBoxLayout()
        row.setSpacing(8)

        self.combo_equipments = QComboBox()
        self.combo_equipments.setMinimumWidth(200)
        self.btn_scan = QPushButton(tr_ui(CommandWizardText.BTN_SCAN))
        self.btn_connect = QPushButton(tr_ui(CommandWizardText.BTN_CONNECT))
        self.btn_disconnect = QPushButton(
            tr_ui(CommandWizardText.BTN_DISCONNECT)
        )
        self.btn_disconnect.setEnabled(False)

        row.addWidget(self.combo_equipments)
        row.addWidget(self.btn_scan)
        row.addWidget(self.btn_connect)
        row.addWidget(self.btn_disconnect)
        grp_equip.setLayout(row)
        layout.addWidget(grp_equip)

        # Operation status group
        grp_status = QGroupBox(tr_ui(CommandWizardText.GROUP_STATUS))
        v_status = QVBoxLayout()
        self.lbl_status = QLabel(tr_ui(CommandWizardText.IDLE))
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        v_status.addWidget(self.lbl_status)
        v_status.addWidget(self.progress_bar)
        grp_status.setLayout(v_status)
        layout.addWidget(grp_status)

        # Communication log group
        grp_log = QGroupBox(tr_ui(CommandWizardText.GROUP_LOG))
        v_log = QVBoxLayout()
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        v_log.addWidget(self.text_log)
        grp_log.setLayout(v_log)
        layout.addWidget(grp_log)

        # Button → parent forwarding method connections.
        # scan_bus / connect_to_instrument / disconnect_bus on the parent
        # widget simply emit the corresponding Signal consumed by the Presenter
        self.btn_scan.clicked.connect(self.parent_widget.scan_bus)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_disconnect.clicked.connect(self.parent_widget.disconnect_bus)

    def _on_connect_clicked(self) -> None:
        # Retrieve both the hidden address and
        # the visible text to initiate the connection
        address: str = self.combo_equipments.currentData()
        name: str = self.combo_equipments.currentText()
        if address:
            self.parent_widget.connect_to_instrument(address, name)


# =============================================================================
# COMPACT CONNECTOR WIDGET  (View — QFrame)
# =============================================================================


class CompactConnectorWidget(QFrame):
    """
    Thumbnail widget shown in ConnectionTopBar.

    Signals (user intents — consumed by ConnectorPresenter)
    -------------------------------------------------------
    scan_requested          — user clicked "Scan Bus"
    connect_requested(str, str) — user clicked "Connect"; (address, name)
    disconnect_requested    — user clicked "Disconnect"

    Display methods (called by ConnectorPresenter)
    ----------------------------------------------
    display_connected(name)     — instrument connected successfully
    display_disconnected()      — instrument disconnected or connection failed
    display_scan_no_found()     — bus scan returned empty results
    display_progress(c, t, s)   — update both local and modal progress bars
    display_status(text)        — overwrite status label; reset progress
    display_error(text)         — show error text in status label
    """

    scan_requested = Signal()
    connect_requested = Signal(str, str)  # (address, name)
    disconnect_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(340, 60)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.modal = ConnectorWizardModal(self)
        self._setup_ui()
        self._apply_styles()

    # ── User-intent forwarding methods ───────────────────────────────────────
    # These are the stable call interface for ConnectorWizardModal buttons.
    # Each method emits the corresponding signal for ConnectorPresenter.

    def scan_bus(self) -> None:
        self.scan_requested.emit()

    def connect_to_instrument(self, address: str, name: str) -> None:
        self.connect_requested.emit(address, name)

    def disconnect_bus(self) -> None:
        self.disconnect_requested.emit()

    # ── Display API (called by ConnectorPresenter) ───────────────────────────

    def display_connected(self, name: str) -> None:
        self._lbl_model.setText(
            tr_ui(CommandWizardText.CONNECTED_MODEL).format(model=name)
        )
        self._lbl_status.setText(tr_ui(CommandWizardText.STATUS_IDLE))
        self._lbl_status.setStyleSheet(
            connector_label_status_idle_stylesheet()
        )

    def display_disconnected(self) -> None:
        self._lbl_model.setText(tr_ui(CommandWizardText.DISCONNECTED_LBL))
        self._lbl_status.setText(tr_ui(CommandWizardText.STATUS_OFFLINE))
        self._lbl_status.setStyleSheet(
            connector_label_status_disconnected_stylesheet()
        )
        self._progress.setValue(0)
        self.modal.reset_progress()

    def display_scan_no_found(self) -> None:
        self._lbl_model.setText(tr_ui(CommandWizardText.SCAN_NO_FOUND))

    def display_progress(self, current: int, total: int, status: str) -> None:
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        if status:
            self._lbl_status.setText(
                tr_ui(CommandWizardText.STATUS_PREFIX).format(status=status)
            )

    def display_status(self, text: str) -> None:
        """Called after setup finishes or any state reset."""
        self._lbl_status.setText(text)
        self._lbl_status.setStyleSheet(
            connector_label_status_idle_stylesheet()
        )
        self._progress.setValue(0)
        self.modal.reset_progress()

    def display_error(self, text: str) -> None:
        self._lbl_status.setText(text)
        self._lbl_status.setStyleSheet(
            connector_label_status_disconnected_stylesheet()
        )

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(3)

        self._lbl_model = QLabel(tr_ui(CommandWizardText.NO_EQUIP_CONNECTED))
        self._lbl_status = QLabel(tr_ui(CommandWizardText.STATUS_DISCONNECTED))

        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)

        layout.addWidget(self._lbl_model)
        layout.addWidget(self._lbl_status)
        layout.addWidget(self._progress)

    def _apply_styles(self) -> None:
        # Frame background — overrides the widget's original white stylesheet
        self.setStyleSheet(compact_connector_stylesheet())
        self._lbl_model.setStyleSheet(connector_label_model_stylesheet())
        self._lbl_status.setStyleSheet(
            connector_label_status_disconnected_stylesheet()
        )
        self._progress.setStyleSheet(connector_progress_bar_stylesheet())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.modal.show()
            self.modal.raise_()
