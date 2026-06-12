from enum import StrEnum

from PySide6.QtCore import QCoreApplication


class CommandWizardText(StrEnum):
    # Titles & Groups
    WIZARD_TITLE = "Connector Wizard - Settings"
    GROUP_EQUIP = "Select Equipment"
    GROUP_STATUS = "Status"
    GROUP_LOG = "Communication Log"

    # Buttons
    BTN_SCAN = "Scan Bus"
    BTN_CONNECT = "Connect"
    BTN_DISCONNECT = "Disconnect"

    # Labels & Statuses
    IDLE = "Idle"
    STATUS_DISCONNECTED = "Status: Disconnected"
    STATUS_IDLE = "Status: Idle"
    STATUS_OFFLINE = "Status: Offline"
    STATUS_PREFIX = "Status: {status}"

    # Component States
    NO_EQUIP_CONNECTED = "No Equipment Connected"
    SCAN_NO_FOUND = "Bus Scan: No 415xy Found"
    DISCONNECTED_LBL = "Disconnected"
    UNKNOWN_MODEL = "Unknown Model"
    CONNECTED_MODEL = "Connected: {model}"
    EQUIP_ITEM = "{idn} ({address})"
    HARDWARE_ERROR_ALERT = "Hardware Error! Check Log."

    # ── Measurements & Run page ──────────────────────────────────────────────
    MEAS_PAGE_TITLE = "Measurements & Run"
    MEAS_CONFIG_SOURCE = "Configuration Source"
    MEAS_RUN_CONTROLS = "Run Controls"
    MEAS_SOURCE_LIVE = "Source: Live Measure Config"
    MEAS_SOURCE_FILE = "Source: {name}"
    MEAS_NO_CONFIG = (
        "No measurement configuration generated. "
        "Use 'Configure Measure' on the Channels page."
    )
    MEAS_BTN_LOAD_FILE = "Load setup file…"
    MEAS_BTN_USE_LIVE = "Use live config"
    MEAS_BTN_APPLY_SETUP = "Apply Setup"
    MEAS_BTN_RUN_FETCH = "Run && Fetch"
    MEAS_BTN_FULL_SEQUENCE = "Apply Setup, Run && Fetch"
    MEAS_FILE_DIALOG_TITLE = "Load Measurement Setup"
    MEAS_FILE_DIALOG_FILTER = "Setup files (*.json);;All files (*)"
    MEAS_SUMMARY_EMPTY = "No configuration available."
    MEAS_SUMMARY_TEMPLATE = (
        "Mode: {mode}\nActive channels: {channels}\nDisplay variables: {vars}"
    )
    MEAS_PREVIEW_TITLE = "Active Configuration"
    MEAS_PREVIEW_EMPTY = "No configuration to preview."
    MEAS_PREVIEW_COL_FIELD = "Field"
    MEAS_PREVIEW_COL_VALUE = "Value"
    MEAS_STATUS_READY = "Status: Ready"
    MEAS_STATUS_DISCONNECTED = "Status: Connect an instrument to run."
    MEAS_STATUS_RUNNING = "Status: Running…"
    MEAS_CONFIG_ERROR = "Configuration error:\n{error}"
    MEAS_FILE_ERROR = "Could not load setup file:\n{error}"

    # ── Channels page ────────────────────────────────────────────────────────
    CHAN_VALIDATION_VALID = "✅ {message}"
    CHAN_VALIDATION_INVALID = "⚠️ {message}"
    CHAN_OPT_COMMON_TO_GROUND = "Common circuit is connected to ground"
    CHAN_OPT_INTERLOCK_OPEN = "Interlock terminal is open"

    # ── Table View page ──────────────────────────────────────────────────────
    TABLE_PAGE_TITLE = "Table View"
    TABLE_EMPTY = "No measurement data yet. Run a measurement to populate."


def tr_ui(text_enum: CommandWizardText) -> str:
    return QCoreApplication.translate("UIText", text_enum.value)
