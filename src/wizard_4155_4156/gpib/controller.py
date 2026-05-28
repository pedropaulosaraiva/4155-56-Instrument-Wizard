from typing import Final, Optional, Sequence, cast

from pyvisa import ResourceManager, VisaIOError
from pyvisa.resources import MessageBasedResource

from wizard_4155_4156.SCPI.command_builders import CommonCommandBuilder


class GPIB41xxController:
    GPIB_ADRESS_ID: Final[str] = "GPIB"
    VALID_MODELS: Final[list[str]] = ["4155C", "4156C", "4155B", "4156B"]
    QUERY_COMMAND_ID: Final[str] = "?"
    TEMPORARY_CONN_TIMEOUT_MS: Final[int] = 2000
    CONN_TIMEOUT_MS: Final[int] = 10000

    def __init__(self):
        self.rm = ResourceManager()
        self._instrument: Optional[MessageBasedResource] = None
        self._is_connected: bool = False

    @property
    def is_connected(self):
        return self._is_connected

    def connect(self, resource_name: str) -> None:
        if self._is_connected:
            self.disconnect()

        self._instrument = cast(
            MessageBasedResource, self.rm.open_resource(resource_name)
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

    def identify_connections(self) -> dict | dict[str, str]:
        found_instruments = {}
        identificator: str = ""
        cmd_builder = CommonCommandBuilder()
        cmd_builder.identify()
        identification_query = cmd_builder.build()

        resources = self.rm.list_resources()
        gpib_resources = (
            ressource
            for ressource in resources
            if self.GPIB_ADRESS_ID in ressource
        )

        for ressource in gpib_resources:
            try:
                with self.rm.open_resource(ressource) as conn:
                    temp_conn = cast(MessageBasedResource, conn)
                    temp_conn.timeout = self.TEMPORARY_CONN_TIMEOUT_MS

                    identificator = temp_conn.query(identification_query)

                for model in self.VALID_MODELS:
                    if model in identificator.strip(" \t\n\r"):
                        found_instruments[ressource] = f"{model} - {ressource}"
                        break
            except VisaIOError:
                continue

        return found_instruments

    def write(self, message: str) -> int:
        if self._instrument is None:
            raise ConnectionError(
                "No instrument connected. Impossible to send command."
            )
        return self._instrument.write(message)

    def query(self, message: str) -> str:
        if self._instrument is None:
            raise ConnectionError(
                "No instrument connected. Impossible to send command."
            )
        return self._instrument.query(message)

    def query_binary_values(
        self, message: str, **kwargs
    ) -> Sequence[int | float]:
        if self._instrument is None:
            raise ConnectionError(
                "No instrument connected. Impossible to send command."
            )

        return self._instrument.query_binary_values(message, **kwargs)
