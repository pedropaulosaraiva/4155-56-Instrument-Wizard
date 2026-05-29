"""
views/demo_connector.py
-----------------------
Temporary stand-in for the real CompactConnectorWidget.

REPLACE with your actual import:
    from wizard_4155_4156.gui.compact_connector import CompactConnectorWidget

The interface this widget must expose for ConnectionTopBar and MainWindow:
    Signals:
    data_ready(dict)      — emitted when a measurement dataset arrives
    hardware_busy(bool)   — emitted to lock/unlock the UI
    Slots:
    update_connection_status(connected: bool, name: str) —
    called by connector logic
    Attribute:
    modal   — the ConnectorWizardModal instance (
        opened via show_connection_wizard)
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
    QWidget,
)

from wizard_4155_4156.styles.stylesheets import (
    compact_connector_stylesheet,
    connector_label_model_stylesheet,
    connector_label_status_connected_stylesheet,
    connector_label_status_disconnected_stylesheet,
    connector_modal_stylesheet,
    connector_progress_bar_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P


class DemoConnectorModal(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connection Wizard — GPIB Instrument")
        self.resize(520, 480)
        self.setModal(True)
        self._setup_ui()
        self.setStyleSheet(connector_modal_stylesheet())

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Equipment selection
        grp_equip = QGroupBox("Equipment Selection")
        row = QHBoxLayout()
        row.setSpacing(8)

        self.combo_equipments = QComboBox()
        self.combo_equipments.setMinimumWidth(200)
        self.combo_equipments.addItem("Scan to detect instruments...")

        self.btn_scan = QPushButton("🔍  Scan Bus")
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)

        row.addWidget(self.combo_equipments, stretch=1)
        row.addWidget(self.btn_scan)
        row.addWidget(self.btn_connect)
        row.addWidget(self.btn_disconnect)
        grp_equip.setLayout(row)
        layout.addWidget(grp_equip)

        # Status
        grp_status = QGroupBox("Operation Status")
        v_status = QVBoxLayout()
        self.lbl_status = QLabel("● Idle — Waiting for command")
        self.lbl_status.setStyleSheet(f"color: {P.TEXT_MUTED};")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        v_status.addWidget(self.lbl_status)
        v_status.addWidget(self.progress_bar)
        grp_status.setLayout(v_status)
        layout.addWidget(grp_status)

        # Log
        grp_log = QGroupBox("Communication Log")
        v_log = QVBoxLayout()
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setPlaceholderText(
            "SCPI commands and responses will appear here..."
        )
        v_log.addWidget(self.text_log)
        grp_log.setLayout(v_log)
        layout.addWidget(grp_log, stretch=1)


class DemoCompactConnectorWidget(QFrame):
    """
    Demo CompactConnectorWidget with dark-theme styling applied.

    Replace this class with your real widget and call
    ``your_widget.setStyleSheet(compact_connector_stylesheet())``
    to override the default white background.
    """

    data_ready = Signal(dict)
    hardware_busy = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(340, 60)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.modal = DemoConnectorModal(self)
        self._setup_ui()
        self._apply_styles()

    # ── Public API ───────────────────────────────────────────────────────────

    def update_connection_status(
        self, connected: bool, name: str = ""
    ) -> None:
        self.modal.btn_connect.setEnabled(not connected)
        self.modal.btn_disconnect.setEnabled(connected)
        self.modal.btn_scan.setEnabled(not connected)
        self.modal.combo_equipments.setEnabled(not connected)

        if connected:
            self._lbl_model.setText(f"📟  {name}")
            self._lbl_status.setText("● Connected")
            self._lbl_status.setStyleSheet(
                connector_label_status_connected_stylesheet()
            )
        else:
            self._lbl_model.setText("No Equipment Connected")
            self._lbl_status.setText("● Disconnected")
            self._lbl_status.setStyleSheet(
                connector_label_status_disconnected_stylesheet()
            )
            self._progress.setValue(0)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(3)

        self._lbl_model = QLabel("No Equipment Connected")
        self._lbl_model.setStyleSheet(connector_label_model_stylesheet())

        self._lbl_status = QLabel("● Disconnected")
        self._lbl_status.setStyleSheet(
            connector_label_status_disconnected_stylesheet()
        )

        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(connector_progress_bar_stylesheet())

        layout.addWidget(self._lbl_model)
        layout.addWidget(self._lbl_status)
        layout.addWidget(self._progress)

    def _apply_styles(self) -> None:
        self.setStyleSheet(compact_connector_stylesheet())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.modal.show()
            self.modal.raise_()
            self.modal.activateWindow()
