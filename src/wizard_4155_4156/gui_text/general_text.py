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
    TABLE_SETUP_LABEL = "Setup:"
    TABLE_EXEC_LABEL = "Execution:"
    TABLE_FORMAT_LABEL = "Format:"
    TABLE_BTN_DOWNLOAD = "⬇  Download"
    TABLE_BTN_COPY = "⧉  Copy"
    TABLE_NO_SETUP = "No setups in this project yet."
    TABLE_NO_EXEC = "No executions for this setup yet."
    TABLE_LIVE_DATA = "Live Data"
    TABLE_LIVE_EXEC = "Live"
    TABLE_COPIED = "Code copied to clipboard."
    TABLE_DOWNLOADED = "Saved {path}"
    TABLE_SAVE_TITLE = "Download data"
    TABLE_SAVE_ERROR = "Could not save file:\n{error}"
    # Format display names (order mirrors data_export.FORMATS).
    TABLE_FMT_CSV = "CSV"
    TABLE_FMT_XLSX = "XLSX"
    TABLE_FMT_PY_PURE = "Pure Python"
    TABLE_FMT_PY_NUMPY = "Python (NumPy + Matplotlib)"
    TABLE_FMT_C_ARRAY = "C/C++ array"
    TABLE_FMT_MATLAB = "MATLAB vectors"

    # ── Measurement Runs (CRUD) page ─────────────────────────────────────────
    RUNS_BTN_CREATE = "Save current config as setup"
    RUNS_BTN_APPLY_RUN = "Apply Setup and Run"
    RUNS_SETUPS_TITLE = "Setups ({count})"
    RUNS_RUNS_TITLE = "Runs ({count})"
    RUNS_DETAIL_TITLE = "Setup detail"
    # Setup-detail panel: Summary / Raw toggle + curated section titles.
    RUNS_DETAIL_SUMMARY = "Summary"
    RUNS_DETAIL_RAW = "Raw"
    RUNS_DETAIL_EMPTY = "Select a setup to see its details."
    RUNS_SUM_TIMING = "Integration & Timing"
    RUNS_SUM_SAMPLING = "Sampling"
    RUNS_SUM_MEASUREMENT = "Measurement"
    RUNS_SUM_DISPLAY_VARS = "Display variables"
    RUNS_SUM_UNITS = "Active units"
    RUNS_SETUPS_EMPTY = (
        "No setups yet.\nSave the current configuration to create one."
    )
    RUNS_RUNS_EMPTY = "No runs yet.\nUse “Insert mock data” to add one."
    # Setups ⋮ menu
    RUNS_MENU_EDIT_META = "Edit name/description"
    RUNS_MENU_EDIT_AS_NEW = "Edit as new setup"
    RUNS_MENU_SEE_DESC = "See description"
    RUNS_MENU_DELETE_SETUP = "Delete setup"
    # Runs ⋮ menu
    RUNS_MENU_VIEW_TABLE = "View as table"
    RUNS_MENU_VIEW_GRAPH = "View as graph"
    RUNS_MENU_INSERT_MOCK = "Insert mock data"
    RUNS_MENU_DELETE_RUN = "Delete run"
    # Reasons shown when a ⋮ menu entry is unavailable.
    RUNS_NEED_SETUP = "Select a setup first."
    RUNS_NEED_RUN = "Select a run first."
    RUNS_GRAPH_SOON_TOOLTIP = "Graph view is coming soon."
    RUNS_DESC_TITLE = "Description"
    RUNS_NO_DESC = "No description provided."
    RUNS_DELETE_SETUP_TITLE = "Delete setup"
    RUNS_DELETE_SETUP_MSG = (
        "Delete this setup and all its runs? This cannot be undone."
    )
    RUNS_DELETE_RUN_TITLE = "Delete run"
    RUNS_DELETE_RUN_MSG = "Delete this run and its data?"


def tr_ui(text_enum: CommandWizardText) -> str:
    return QCoreApplication.translate("UIText", text_enum.value)
