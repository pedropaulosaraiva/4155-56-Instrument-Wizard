"""
gpib/controller.py
------------------
Hardware abstraction layer for Agilent/Keysight 4155/4156 series analyzers.

Layer contract
--------------
- No Qt imports of any kind.
- Owns the single PyVISA ResourceManager and the instrument handle.
- Stateless between calls except for _instrument and _is_connected.
- All public methods raise ConnectionError when called without an active
  connection; callers (workers) are responsible for catching and forwarding
  the exception to their signals.

Thread safety
-------------
This class is NOT thread-safe on its own.  Thread safety is guaranteed
externally by ConnectorPresenter, which restricts the QThreadPool to a
single thread (FIFO queue), ensuring sequential, non-concurrent access to
every method of this class.
"""

from typing import Final, Optional, Sequence, cast

from pyvisa import ResourceManager, VisaIOError
from pyvisa.resources import MessageBasedResource

from wizard_4155_4156.SCPI.command_builders import CommonCommandBuilder


class GPIB41xxController:
    """
    Thin wrapper around a PyVISA MessageBasedResource.

    Exposes four I/O primitives (write, query, query_binary_values,
    identify_connections) plus connect/disconnect lifecycle management.
    All timeout values are expressed in milliseconds, matching PyVISA's
    convention.
    """

    GPIB_ADDRESS_ID: Final[str] = "GPIB"
    VALID_MODELS: Final[list[str]] = ["4155C", "4156C", "4155B", "4156B"]
    TEMPORARY_CONN_TIMEOUT_MS: Final[int] = 2_000
    CONN_TIMEOUT_MS: Final[int] = 10_000

    def __init__(self) -> None:
        # Created lazily on the first scan via initialize_visa() so a missing
        # VISA backend cannot crash application startup.
        self.rm: Optional[ResourceManager] = None
        self._instrument: Optional[MessageBasedResource] = None
        self._is_connected: bool = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_visa_ready(self) -> bool:
        """Whether the PyVISA ResourceManager has been successfully created."""
        return self.rm is not None

    # ── VISA driver lifecycle ────────────────────────────────────────────────

    def initialize_visa(self) -> None:
        """
        Create the PyVISA ResourceManager on first use.  Idempotent — a no-op
        once ready.  Raises if no VISA backend is available; the assignment
        only completes on success, so a failure leaves self.rm as None and the
        next call retries.
        """
        if self.rm is None:
            self.rm = ResourceManager()

    def _require_visa(self) -> ResourceManager:
        if self.rm is None:
            raise ConnectionError("VISA driver not initialized.")
        return self.rm

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self, resource_name: str) -> None:
        rm = self._require_visa()
        if self._is_connected:
            self.disconnect()
        self._instrument = cast(
            MessageBasedResource, rm.open_resource(resource_name)
        )
        self._instrument.read_termination = "\n"
        self._instrument.write_termination = "\n"
        self._instrument.timeout = self.CONN_TIMEOUT_MS
        self._is_connected = True

    def disconnect(self) -> None:
        if self._instrument is not None:
            try:
                self._instrument.close()
            except VisaIOError:
                pass
            finally:
                self._instrument = None
                self._is_connected = False

    # ── Bus discovery ────────────────────────────────────────────────────────

    def identify_connections(self) -> dict[str, str]:
        """
        Enumerate GPIB resources and return {resource_string: display_label}
        for instruments whose *IDN? response contains a known model number.
        Unresponsive resources are silently skipped.
        """
        rm = self._require_visa()
        found: dict[str, str] = {}
        cmd_builder = CommonCommandBuilder()
        cmd_builder.identify()
        idn_query = cmd_builder.build()

        gpib_resources = (
            r for r in rm.list_resources() if self.GPIB_ADDRESS_ID in r
        )

        for resource in gpib_resources:
            try:
                with rm.open_resource(resource) as conn:
                    temp = cast(MessageBasedResource, conn)
                    temp.timeout = self.TEMPORARY_CONN_TIMEOUT_MS
                    idn = temp.query(idn_query)

                for model in self.VALID_MODELS:
                    if model in idn.strip():
                        found[resource] = f"{model} - {resource}"
                        break
            except VisaIOError:
                continue

        return found

    # ── I/O primitives ───────────────────────────────────────────────────────

    def write(self, message: str) -> int:
        self._require_connection()
        return self._instrument.write(message)  # type: ignore[union-attr]

    def query(self, message: str) -> str:
        self._require_connection()
        return self._instrument.query(message)  # type: ignore[union-attr]

    def query_without_timeout(self, message: str) -> str:
        self._require_connection()

        original_timeout = self._instrument.timeout  # type: ignore
        try:
            self._instrument.timeout = None  # type: ignore
            return self._instrument.query(message)  # type: ignore[union-attr]
        finally:
            self._instrument.timeout = original_timeout  # type: ignore

    def query_binary_values(
        self, message: str, **kwargs
    ) -> Sequence[int | float]:
        self._require_connection()
        return self._instrument.query_binary_values(message, **kwargs)  # type: ignore[union-attr]

    def _require_connection(self) -> None:
        if self._instrument is None:
            raise ConnectionError(
                "No instrument connected. Cannot send command."
            )
