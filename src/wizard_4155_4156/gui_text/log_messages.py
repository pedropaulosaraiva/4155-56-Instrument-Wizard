from enum import StrEnum


class LogMsg(StrEnum):
    # Scan + Connect
    SCAN_START = "<span style='color:blue;'>Scanning GPIB bus...</span>"
    SCAN_FOUND = (
        "<span style='color:green;'>Found {count} instrument(s).</span>"
    )
    CONNECTING = "<span style='color:blue;'>Connecting to {address}...</span>"
    CONNECTED = "<span style='color:blue;'>Connected: {idn}</span>"
    DISCONNECTED = "<span style='color:red;'>Disconnected.</span>"

    # Setup + Measure
    SETUP_RST = "<span style='color:green;'>SEND: *RST ; :CAL:AUTO OFF</span>"
    SETUP_SEND = "<span style='color:green;'>SEND: {command}</span>"
    SETUP_VERIFY = "<span style='color:blue;'>VERIFY: {cmd} -> {resp}</span>"
    SETUP_ABORTED = "<span style='color:red;'>Setup Aborted: {error}</span>"
    MEASURE_SEND = "<span style='color:green;'>SEND: :PAGE:SCON:SING</span>"

    # Fetch + Errors
    FETCH_START = "<span style='color:blue;'>Fetching Binary Data...</span>"
    FETCH_QUERY = "<span style='color:green;'>QUERY: :DATA? '{var}'</span>"
    FETCH_RECEIVED = (
        "<span style='color:blue;'>RECEIVED: {var} ({points} points)</span>"
    )
    FETCH_ERROR = "<span style='color:red;'>Fetch Error: {error}</span>"
    WORKER_ERROR = (
        "<span style='color:red; font-weight:bold;'>ERROR: {error}</span>"
    )


class StatusMsg(StrEnum):
    # Scan
    SCAN_BUS = "Scanning Bus..."
    SCAN_COMPLETE = "Scan Complete"

    # Setup
    SETUP_RESET = "Resetting Instrument (*RST)"
    SETUP_SENDING = "Sending: {command}"
    SETUP_COMPLETE = "Setup Complete"

    # Measure
    MEASURE_RUNNING = "Running Measurement..."
    MEASURE_COMPLETE = "Measurement Complete"

    # Fetch
    FETCHING_VAR = "Fetching {command}..."
    FETCH_SUCCESS = "Data Fetched Successfully"


class ErrorMsg(StrEnum):
    SCAN_FAILED = "Scan failed: {error}"
    CONNECT_FAILED = "Connection error: {error}"
    SETUP_NOT_CONNECTED = "Cannot setup: Not connected."
    SETUP_SCPI = "SCPI Error: {error}"
    MEASURE_NOT_CONNECTED = "Cannot run: Not connected."
    MEASURE_FAILED = "Measurement Failed: {error}"
    FETCH_FAILED = "Data Fetch Failed: {error}"
