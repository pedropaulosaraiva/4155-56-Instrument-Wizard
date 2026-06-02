"""
gpib/workers.py
---------------
Background QRunnable tasks for GPIB communication.

Layer contract
--------------
- May import QObject / QRunnable / Signal (Qt threading primitives only).
- Must NOT import any QWidget subclass or application-level UI module.
- All results and errors are surfaced exclusively via WorkerSignals.

FIFO guarantee
--------------
Thread safety is enforced at the scheduling level by ConnectorPresenter,
which runs tasks on a QThreadPool restricted to exactly one thread.
Tasks execute in submission order with no overlap — no locking needed here.
"""
from re import match as re_match
from typing import Any, Final, List

from numpy import array as np_array
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QRunnable, Signal

from wizard_4155_4156.gpib.controller import GPIB41xxController
from wizard_4155_4156.gui_text.log_messages import ErrorMsg, LogMsg, StatusMsg
from wizard_4155_4156.SCPI.base_director import CommandPair

# ── Helpers ──────────────────────────────────────────────────────────────────


def is_scpi_error_response(response: str) -> bool:
    """
    Evaluate a standard SCPI error-queue response.
    Returns True when the instrument-reported code is non-zero (error).
    """
    _NO_ERROR_CODE: Final[int] = 0
    match = re_match(r'^([-+]?\d+),\s*".*"', response)
    if match:
        return int(match.group(1)) != _NO_ERROR_CODE
    return False


# ── Shared signal bus ────────────────────────────────────────────────────────

class WorkerSignals(QObject):
    """
    Signal container shared across all task types.
    ConnectorPresenter connects only the subset relevant to each task.
    """
    log_msg = Signal(str)
    progress_update = Signal(int, int, str)   # current, total, status_text
    connection_status = Signal(bool, str)        # connected, instrument_name
    scan_results = Signal(dict)
    worker_error = Signal(str)
    finished_setup = Signal()
    finished_measurement = Signal()
    data_fetched = Signal(dict)


# ── Connection tasks ─────────────────────────────────────────────────────────

class ScanTask(QRunnable):
    def __init__(self, controller: GPIB41xxController) -> None:
        super().__init__()
        self.controller = controller
        self.signals = WorkerSignals()

    def run(self) -> None:
        self.signals.log_msg.emit(LogMsg.SCAN_START)
        self.signals.progress_update.emit(0, 1, StatusMsg.SCAN_BUS)
        try:
            found = self.controller.identify_connections()
            self.signals.scan_results.emit(found)
            self.signals.progress_update.emit(1, 1, StatusMsg.SCAN_COMPLETE)
            self.signals.log_msg.emit(LogMsg.SCAN_FOUND.format(count=len(found)))
        except Exception as e:
            self.signals.worker_error.emit(ErrorMsg.SCAN_FAILED.format(error=str(e)))


class ConnectTask(QRunnable):
    def __init__(
        self, controller: GPIB41xxController, address: str, name: str
    ) -> None:
        super().__init__()
        self.controller = controller
        self.address = address
        self.name = name
        self.signals = WorkerSignals()

    def run(self) -> None:
        self.signals.log_msg.emit(LogMsg.CONNECTING.format(address=self.address))
        try:
            self.controller.connect(self.address)
            self.signals.connection_status.emit(True, self.name)
            self.signals.log_msg.emit(LogMsg.CONNECTED.format(idn=self.name))
        except Exception as e:
            self.signals.connection_status.emit(False, "")
            self.signals.worker_error.emit(ErrorMsg.CONNECT_FAILED.format(error=str(e)))


class DisconnectTask(QRunnable):
    """
    Enqueued — not executed immediately — to prevent race conditions when
    a measurement task is still pending in the pool.
    """
    def __init__(self, controller: GPIB41xxController) -> None:
        super().__init__()
        self.controller = controller
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self.controller.disconnect()
            self.signals.connection_status.emit(False, "")
            self.signals.log_msg.emit(LogMsg.DISCONNECTED)
        except Exception as e:
            self.signals.worker_error.emit(str(e))


# ── SCPI execution engine ────────────────────────────────────────────────────

class SCPIExecutionTask(QRunnable):
    """
    Iterates a CommandPair list and dispatches write / ASCII-query /
    binary-query to the controller.  Subclasses specialise run() only.
    """

    def __init__(
        self,
        controller: GPIB41xxController,
        commands: List[CommandPair],
    ) -> None:
        super().__init__()
        self.controller = controller
        self.commands = commands
        self.signals = WorkerSignals()
        self.results: dict[str, Any] = {}

    def _execute_sequence(
        self, status_msg_write: str, status_msg_complete: str
    ) -> None:
        if not self.controller.is_connected:
            raise ConnectionError("Instrument not connected.")

        total = len(self.commands)

        for idx, pair in enumerate(self.commands, start=1):
            cmd_name = pair.set_command or pair.get_command
            self.signals.progress_update.emit(
                idx, total, status_msg_write.format(command=cmd_name)
            )

            if pair.set_command:
                self.signals.log_msg.emit(
                    LogMsg.SETUP_SEND.format(command=pair.set_command)
                )
                self.controller.write(pair.set_command)

            if pair.get_command:
                if getattr(pair, "is_binary_query", False):
                    # IEEE 488.2 binary block — high-throughput path
                    data_array = self.controller.query_binary_values(
                        pair.get_command,
                        datatype="d",
                        is_big_endian=True,
                        header_fmt="ieee",
                    )
                    if getattr(pair, "result_key", None):
                        self.results[pair.result_key] = np_array(data_array)  # type: ignore[assignment]
                    self.signals.log_msg.emit(
                        LogMsg.FETCH_RECEIVED.format(
                            var=pair.result_key, points=len(data_array)
                        )
                    )
                else:
                    # ASCII query with runtime SCPI error validation
                    resp = self.controller.query(pair.get_command).strip()
                    self.signals.log_msg.emit(
                        LogMsg.SETUP_VERIFY.format(
                            cmd=pair.get_command,
                            resp=resp
                        )
                    )
                    if is_scpi_error_response(resp):
                        raise RuntimeError(f"Hardware error response: {resp}")

        self.signals.progress_update.emit(total, total, status_msg_complete)


class SetupTask(SCPIExecutionTask):
    def run(self) -> None:
        try:
            self.signals.log_msg.emit(LogMsg.SETUP_RST)
            self._execute_sequence(
                StatusMsg.SETUP_SENDING,
                StatusMsg.SETUP_COMPLETE
            )
            self.signals.finished_setup.emit()
        except Exception as e:
            self.signals.worker_error.emit(ErrorMsg.SETUP_SCPI.format(error=str(e)))
            self.signals.log_msg.emit(LogMsg.SETUP_ABORTED.format(error=str(e)))


class MeasurementRunTask(SCPIExecutionTask):
    def run(self) -> None:
        try:
            self.signals.progress_update.emit(0, 0, StatusMsg.MEASURE_RUNNING)
            self._execute_sequence(
                StatusMsg.SETUP_SENDING,
                StatusMsg.MEASURE_COMPLETE
            )
            self.signals.finished_measurement.emit()
        except Exception as e:
            self.signals.worker_error.emit(ErrorMsg.MEASURE_FAILED.format(error=str(e)))


class DataFetchTask(SCPIExecutionTask):
    def run(self) -> None:
        try:
            self.signals.log_msg.emit(LogMsg.FETCH_START)
            self._execute_sequence(
                StatusMsg.FETCHING_VAR,
                StatusMsg.FETCH_SUCCESS
            )
            results: dict[str, NDArray] = self.results  # type: ignore[assignment]
            self.signals.data_fetched.emit(results)
        except Exception as e:
            self.signals.worker_error.emit(ErrorMsg.FETCH_FAILED.format(error=str(e)))
            self.signals.log_msg.emit(LogMsg.FETCH_ERROR.format(error=str(e)))
