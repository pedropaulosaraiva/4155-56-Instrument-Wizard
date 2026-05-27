from PySide6.QtCore import Qt, QThreadPool, Signal, Slot
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

from wizard_4155_4156.gpib.controller import GPIB41xxController
from wizard_4155_4156.gpib.workers import (
    ConnectTask,
    DataFetchTask,
    DisconnectTask,
    MeasurementRunTask,
    ScanTask,
    SetupTask,
)
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.gui_text.log_messages import LogMsg
from wizard_4155_4156.SCPI.base_director import CommandPair

AnyWorkerTask = (
    ScanTask | ConnectTask | DisconnectTask | SetupTask |
    MeasurementRunTask | DataFetchTask
)


class ConnectorWizardModal(QDialog):
    """
    Modal dialog providing a detailed interface for scanning the GPIB bus,
    selecting an instrument, and monitoring low-level connection logs.
    """
    def __init__(self, parent: "CompactConnectorWidget"):
        super().__init__(parent)
        self.setWindowTitle(tr_ui(CommandWizardText.WIZARD_TITLE))
        self.resize(500, 450)
        self.setModal(True)
        self.parent_widget = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        group_equip = QGroupBox(tr_ui(CommandWizardText.GROUP_EQUIP))
        h_equip = QHBoxLayout()
        self.combo_equipments = QComboBox()
        self.btn_scan = QPushButton(tr_ui(CommandWizardText.BTN_SCAN))
        self.btn_connect = QPushButton(tr_ui(CommandWizardText.BTN_CONNECT))
        self.btn_disconnect = QPushButton(
            tr_ui(CommandWizardText.BTN_DISCONNECT)
        )
        self.btn_disconnect.setEnabled(False)

        h_equip.addWidget(self.combo_equipments)
        h_equip.addWidget(self.btn_scan)
        h_equip.addWidget(self.btn_connect)
        h_equip.addWidget(self.btn_disconnect)
        group_equip.setLayout(h_equip)
        layout.addWidget(group_equip)

        group_status = QGroupBox(tr_ui(CommandWizardText.GROUP_STATUS))
        v_status = QVBoxLayout()
        self.lbl_status = QLabel(tr_ui(CommandWizardText.IDLE))
        self.progress_bar = QProgressBar()
        v_status.addWidget(self.lbl_status)
        v_status.addWidget(self.progress_bar)
        group_status.setLayout(v_status)
        layout.addWidget(group_status)

        group_log = QGroupBox(tr_ui(CommandWizardText.GROUP_LOG))
        v_log = QVBoxLayout()
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4;"
            "font-family: monospace;"
        )
        v_log.addWidget(self.text_log)
        group_log.setLayout(v_log)
        layout.addWidget(group_log)

        # Delegate hardware actions to the parent widget to maintain a single
        # point of entry
        self.btn_scan.clicked.connect(self.parent_widget.scan_bus)
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_disconnect.clicked.connect(self.parent_widget.disconnect_bus)

    def update_scan_results(self, results: dict):
        self.combo_equipments.clear()
        for address, instrument_name in results.items():
            # Store the raw GPIB address as hidden 'userData'
            # while displaying the readable instrument name
            self.combo_equipments.addItem(instrument_name, address)

    def on_connect_clicked(self):
        # Retrieve both the hidden address and
        # the visible text to initiate the connection
        address = self.combo_equipments.currentData()
        name = self.combo_equipments.currentText()

        if address:
            self.parent_widget.connect_to_instrument(address, name)

    def update_connection_status(self, connected: bool):
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        self.btn_scan.setEnabled(not connected)
        self.combo_equipments.setEnabled(not connected)

    def append_log(self, msg: str):
        self.text_log.append(msg)

    def update_progress(self, current: int, total: int, status: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_status.setText(status)


class CompactConnectorWidget(QFrame):
    """
    A compact UI element that displays current hardware status and acts as the
    central dispatcher for all hardware interactions. It manages a
    single-threaded FIFO queue to ensure thread-safe GPIB communication
    without freezing the main application GUI.
    """

    # Emitted when a fetch task completes, providing the parsed data dictionary
    data_ready = Signal(dict)

    # Emitted to lock/unlock the main application UI during hardware operations
    # preventing users from spamming the command queue and overloading the bus.
    hardware_busy = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            CompactConnectorWidget {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
            }
            CompactConnectorWidget:hover {
                background-color: #eef2f5;
            }
        """)
        self.setFixedSize(300, 70)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # * SINGLE INSTANCE of the controller shared across
        # * all background workers
        self.controller = GPIB41xxController()

        # ! CRITICAL: Thread pool is restricted to exactly 1 thread.
        # ! This creates a strict FIFO (First-In, First-Out) queue, ensuring no
        # ! concurrent I/O operations crash the PyVISA resource or the hardware
        # ! buffer.
        self.gpib_pool = QThreadPool()
        self.gpib_pool.setMaxThreadCount(1)

        self.modal = ConnectorWizardModal(self)
        self.setup_ui()
        self.scan_bus()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(2)

        self.lbl_model = QLabel(tr_ui(CommandWizardText.NO_EQUIP_CONNECTED))
        self.lbl_model.setStyleSheet("font-weight: bold; color: #333;")

        self.lbl_status = QLabel(tr_ui(CommandWizardText.STATUS_DISCONNECTED))
        self.lbl_status.setStyleSheet("font-size: 10px; color: #666;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)

        layout.addWidget(self.lbl_model)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.progress_bar)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.modal.show()
            self.modal.raise_()

    def _wire_signals(self, task: AnyWorkerTask) -> AnyWorkerTask:
        """
        Helper to universally map background task signals back to the main
        thread UI slots.
        """
        task.signals.log_msg.connect(self.modal.append_log)
        task.signals.progress_update.connect(self.on_progress_update)
        task.signals.worker_error.connect(self.on_worker_error)
        return task

    def scan_bus(self):
        task = self._wire_signals(ScanTask(self.controller))
        task.signals.scan_results.connect(self.on_scan_results)
        self.gpib_pool.start(task)

    def connect_to_instrument(self, address: str, name: str):
        task = self._wire_signals(ConnectTask(self.controller, address, name))
        task.signals.connection_status.connect(self.on_connection_status)
        self.gpib_pool.start(task)

    def disconnect_bus(self):
        """
        Enqueue the disconnect operation rather than executing it immediately
        on the GUI thread. This prevents fatal race conditions if a measurement
        is currently running in the background.
        """
        task = self._wire_signals(DisconnectTask(self.controller))
        task.signals.connection_status.connect(self.on_connection_status)
        self.gpib_pool.start(task)

    def trigger_setup_only(self, setup_cmds: list[CommandPair]):
        """
        Queues only the instrument configuration phase.
        """
        self.hardware_busy.emit(True)

        setup_task = self._wire_signals(SetupTask(self.controller, setup_cmds))
        setup_task.signals.finished_setup.connect(self.on_setup_finished)

        self.gpib_pool.start(setup_task)

    def trigger_run_only(
        self, run_cmds: list[CommandPair], fetch_cmds: list[CommandPair]):
        """
        Queues measurement execution and subsequent data extraction.
        """
        self.hardware_busy.emit(True)

        run_task = self._wire_signals(
            MeasurementRunTask(self.controller, run_cmds)
        )
        fetch_task = self._wire_signals(
            DataFetchTask(self.controller, fetch_cmds)
        )

        fetch_task.signals.data_fetched.connect(self.on_data_fetched)

        self.gpib_pool.start(run_task)
        self.gpib_pool.start(fetch_task)

    def trigger_full_sequence(
        self,
        setup_cmds: list[CommandPair],
        run_cmds: list[CommandPair],
        fetch_cmds: list[CommandPair]
    ):
        """
        Queues a complete cycle:
        configuration, execution, and data extraction.
        """
        self.hardware_busy.emit(True)

        setup_task = self._wire_signals(
            SetupTask(self.controller, setup_cmds)
        )
        run_task = self._wire_signals(
            MeasurementRunTask(self.controller, run_cmds)
        )
        fetch_task = self._wire_signals(
            DataFetchTask(self.controller, fetch_cmds)
        )

        fetch_task.signals.data_fetched.connect(self.on_data_fetched)

        # Tasks are queued sequentially. The single-thread pool ensures they
        # execute in exact order (Setup -> Run -> Fetch).
        self.gpib_pool.start(setup_task)
        self.gpib_pool.start(run_task)
        self.gpib_pool.start(fetch_task)

    @Slot()
    def on_setup_finished(self):
        self.hardware_busy.emit(False)
        self.lbl_status.setText(tr_ui(CommandWizardText.STATUS_IDLE))
        self.progress_bar.setValue(0)
        self.modal.progress_bar.setValue(0)

    @Slot(dict)
    def on_data_fetched(self, data: dict):
        self.hardware_busy.emit(False)
        self.data_ready.emit(data)

    @Slot(dict)
    def on_scan_results(self, results: dict):
        self.modal.update_scan_results(results)
        if not results:
            self.lbl_model.setText(tr_ui(CommandWizardText.SCAN_NO_FOUND))

    @Slot(bool, str)
    def on_connection_status(self, connected: bool, instrument_name: str):
        self.modal.update_connection_status(connected)

        if connected:
            self.lbl_model.setText(tr_ui(CommandWizardText.CONNECTED_MODEL).format(model=instrument_name))
            self.lbl_status.setText(tr_ui(CommandWizardText.STATUS_IDLE))
        else:
            self.lbl_model.setText(tr_ui(CommandWizardText.DISCONNECTED_LBL))
            self.lbl_status.setText(tr_ui(CommandWizardText.STATUS_OFFLINE))

            self.progress_bar.setValue(0)
            self.modal.progress_bar.setValue(0)

    @Slot(int, int, str)
    def on_progress_update(self, current: int, total: int, status: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_status.setText(tr_ui(CommandWizardText.STATUS_PREFIX).format(status=status))
        self.modal.update_progress(current, total, status)

    @Slot(str)
    def on_worker_error(self, err_msg: str):
        # ! CRITICAL: If a task fails (e.g., Setup fails), we must clear the
        # ! pool. Otherwise, the queue will blindly execute the next cascaded
        # ! task (e.g., Run) ! on an improperly configured instrument, leading
        # ! to unknown hardware states.
        self.gpib_pool.clear()

        self.hardware_busy.emit(False)
        self.lbl_status.setText(tr_ui(CommandWizardText.HARDWARE_ERROR_ALERT))
        self.modal.append_log(LogMsg.WORKER_ERROR.format(error=err_msg))

    def closeEvent(self, event):
        """
        Ensure background threads are cleanly terminated when the widget is
        destroyed.
        """
        self.gpib_pool.clear()
        super().closeEvent(event)
