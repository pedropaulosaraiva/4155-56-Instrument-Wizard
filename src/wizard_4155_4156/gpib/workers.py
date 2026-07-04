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

from typing import Any, Callable, Final

from numpy import array as np_array
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QRunnable, Signal

from wizard_4155_4156.gpib.controller import GPIB41xxController
from wizard_4155_4156.gui_text.log_messages import ErrorMsg, LogMsg, StatusMsg
from wizard_4155_4156.SCPI.base_director import CommandPair

# --- Constants ---
SCPI_ERROR_QUERY: Final[str] = "SYST:ERR?"
SCPI_NO_ERROR_PREFIXES: Final[tuple[str, ...]] = ("0,", "+0,")
DEFAULT_MAX_RETRIES: Final[int] = 3
MAX_SCPI_ERRORS: Final[int] = 30
BINARY_DATATYPE: Final[str] = "d"
BINARY_HEADER_FMT: Final[str] = "ieee"
OPC_QUERY: Final[str] = "*OPC?"


class WorkerSignals(QObject):
    log_msg = Signal(str)
    progress_update = Signal(int, int, str)
    connection_status = Signal(bool, str)
    scan_results = Signal(dict)
    worker_error = Signal(str)

    finished_setup = Signal()
    finished_measurement = Signal()
    data_fetched = Signal(dict)


class BaseWorkerTask(QRunnable):
    """
    Base worker class providing generic try/except boilerplate and
    signal initialization.
    """

    def __init__(self, controller: GPIB41xxController):
        super().__init__()
        self.controller = controller
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            self._execute()
        except Exception as e:
            self._handle_error(e)

    def _execute(self) -> None:
        """Override this method in subclasses to implement specific logic."""
        raise NotImplementedError

    def _handle_error(self, e: Exception) -> None:
        """
        Default error handling. Subclasses can override for custom emission.
        """
        self.signals.worker_error.emit(str(e))


class ScanTask(BaseWorkerTask):
    def _execute(self) -> None:
        # Lazily bring up the VISA driver on the first scan only.
        if not self.controller.is_visa_ready:
            self.signals.log_msg.emit(LogMsg.VISA_INIT_START)
            try:
                self.controller.initialize_visa()
            except Exception as e:
                self.signals.log_msg.emit(
                    LogMsg.VISA_INIT_FAILED.format(error=str(e))
                )
                raise
            self.signals.log_msg.emit(LogMsg.VISA_INIT_OK)

        self.signals.log_msg.emit(LogMsg.SCAN_START)
        self.signals.progress_update.emit(0, 1, StatusMsg.SCAN_BUS)

        found_instruments = self.controller.identify_connections()

        self.signals.scan_results.emit(found_instruments)
        self.signals.progress_update.emit(1, 1, StatusMsg.SCAN_COMPLETE)
        self.signals.log_msg.emit(
            LogMsg.SCAN_FOUND.format(count=len(found_instruments))
        )

    def _handle_error(self, e: Exception) -> None:
        self.signals.worker_error.emit(
            ErrorMsg.SCAN_FAILED.format(error=str(e))
        )


class ConnectTask(BaseWorkerTask):
    def __init__(
        self, controller: GPIB41xxController, address: str, name: str
    ):
        super().__init__(controller)
        self.address = address
        self.name = name

    def _execute(self) -> None:
        self.signals.log_msg.emit(
            LogMsg.CONNECTING.format(address=self.address)
        )
        self.controller.connect(self.address)
        self.signals.connection_status.emit(True, self.name)
        self.signals.log_msg.emit(LogMsg.CONNECTED.format(idn=self.name))

    def _handle_error(self, e: Exception) -> None:
        self.signals.connection_status.emit(False, "")
        self.signals.worker_error.emit(
            ErrorMsg.CONNECT_FAILED.format(error=str(e))
        )


class DisconnectTask(BaseWorkerTask):
    def _execute(self) -> None:
        self.controller.disconnect()
        self.signals.connection_status.emit(False, "")
        self.signals.log_msg.emit(LogMsg.DISCONNECTED)


class SCPIExecutionTask(BaseWorkerTask):
    """
    Base task for executing a sequence of SCPI commands (Setup, Run, Fetch).
    Handles retry logic, error checking, and progress updating.
    """

    def __init__(
        self,
        controller: GPIB41xxController,
        commands: list[CommandPair],
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        super().__init__(controller)
        self.commands = commands
        self.max_retries = max_retries
        self.results: dict[str, Any] = {}

    def _check_instrument_errors(self) -> None:
        """
        Queries the instrument's error queue until empty and logs any errors.
        """
        errors_found: list[str] = []
        while True:
            if len(errors_found) >= MAX_SCPI_ERRORS:
                raise RuntimeError(
                    "SCPI error queue exceeded maximum limit of "
                    f"{MAX_SCPI_ERRORS} errors."
                )

            response = self.controller.query(SCPI_ERROR_QUERY).strip()
            if response.startswith(SCPI_NO_ERROR_PREFIXES):
                break

            self.signals.log_msg.emit(
                LogMsg.WORKER_ERROR.format(error=f"SCPI Error: {response}")
            )
            errors_found.append(response)

        if errors_found:
            raise RuntimeError(
                f"Hardware reported errors: {'; '.join(errors_found)}"
            )

    def _execute_with_retry(
        self, action: Callable[[], None], command_str: str
    ) -> None:
        """
        Executes a generic action with retries on RuntimeError (SCPI Errors).
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                action()
                self._check_instrument_errors()
                return
            except RuntimeError:
                if attempt < self.max_retries:
                    self.signals.log_msg.emit(
                        "<span style='color:orange;'>SCPI error. Retrying "
                        f"command ({attempt}/{self.max_retries}): "
                        f"{command_str}</span>"
                    )
                else:
                    raise

    def _execute_set_command(self, pair: CommandPair) -> None:
        if not pair.set_command:
            return

        self.signals.log_msg.emit(
            LogMsg.SETUP_SEND.format(command=pair.set_command)
        )

        def action() -> None:
            self.controller.write(pair.set_command)  # type: ignore

        self._execute_with_retry(action, pair.set_command)

    def _handle_binary_query(self, pair: CommandPair) -> None:
        if not pair.get_command:
            return

        data_array = self.controller.query_binary_values(
            pair.get_command,
            datatype=BINARY_DATATYPE,
            is_big_endian=True,
            header_fmt=BINARY_HEADER_FMT,
        )
        if getattr(pair, "result_key", None):
            self.results[pair.result_key] = np_array(data_array)  # type: ignore

        self.signals.log_msg.emit(
            LogMsg.FETCH_RECEIVED.format(
                var=pair.result_key, points=len(data_array)
            )
        )

    def _handle_ascii_query(self, pair: CommandPair) -> None:
        if not pair.get_command:
            return

        command = pair.get_command.strip().upper()
        if command == OPC_QUERY:
            response = self.controller.query_without_timeout(
                pair.get_command
            ).strip()
        else:
            response = self.controller.query(pair.get_command).strip()

        self.signals.log_msg.emit(
            LogMsg.SETUP_VERIFY.format(cmd=pair.get_command, resp=response)
        )

    def _execute_get_command(self, pair: CommandPair) -> None:
        if not pair.get_command:
            return

        def action() -> None:
            if getattr(pair, "is_binary_query", False):
                self._handle_binary_query(pair)
            else:
                self._handle_ascii_query(pair)

        self._execute_with_retry(action, pair.get_command)

    def _execute_sequence(
        self, status_msg_write: str, status_msg_complete: str
    ) -> None:
        if not self.controller.is_connected:
            raise ConnectionError()

        total_steps = len(self.commands)

        for step_index, pair in enumerate(self.commands, start=1):
            cmd_name = pair.set_command or pair.get_command
            self.signals.progress_update.emit(
                step_index,
                total_steps,
                status_msg_write.format(command=cmd_name),
            )

            self._execute_set_command(pair)
            self._execute_get_command(pair)

        self.signals.progress_update.emit(
            total_steps, total_steps, status_msg_complete
        )


class SetupTask(SCPIExecutionTask):
    def _execute(self) -> None:
        self.signals.log_msg.emit(LogMsg.SETUP_RST)
        self._execute_sequence(
            StatusMsg.SETUP_SENDING, StatusMsg.SETUP_COMPLETE
        )
        self.signals.finished_setup.emit()

    def _handle_error(self, e: Exception) -> None:
        self.signals.worker_error.emit(
            ErrorMsg.SETUP_SCPI.format(error=str(e))
        )
        self.signals.log_msg.emit(LogMsg.SETUP_ABORTED.format(error=str(e)))


class MeasurementRunTask(SCPIExecutionTask):
    def _execute(self) -> None:
        self.signals.progress_update.emit(0, 0, StatusMsg.MEASURE_RUNNING)
        self._execute_sequence(
            StatusMsg.SETUP_SENDING, StatusMsg.MEASURE_COMPLETE
        )
        self.signals.finished_measurement.emit()

    def _handle_error(self, e: Exception) -> None:
        self.signals.worker_error.emit(
            ErrorMsg.MEASURE_FAILED.format(error=str(e))
        )


class DataFetchTask(SCPIExecutionTask):
    def _execute(self) -> None:
        self.signals.log_msg.emit(LogMsg.FETCH_START)
        self._execute_sequence(StatusMsg.FETCHING_VAR, StatusMsg.FETCH_SUCCESS)

        self.results: dict[str, NDArray] = self.results  # type: ignore[assignment]
        self.signals.data_fetched.emit(self.results)

    def _handle_error(self, e: Exception) -> None:
        self.signals.worker_error.emit(
            ErrorMsg.FETCH_FAILED.format(error=str(e))
        )
        self.signals.log_msg.emit(LogMsg.FETCH_ERROR.format(error=str(e)))
