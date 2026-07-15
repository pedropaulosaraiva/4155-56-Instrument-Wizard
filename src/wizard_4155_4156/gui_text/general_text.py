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

    # ── Measurement setup (shared: config factory + Runs page) ───────────────
    MEAS_NO_CONFIG = (
        "No measurement configuration generated. "
        "Use 'Configure Measure' on the Channels page."
    )
    MEAS_BTN_APPLY_SETUP = "Apply Setup"

    # ── Channels page ────────────────────────────────────────────────────────
    # Validation icons (check / alert-triangle) are supplied by the view.
    CHAN_VALIDATION_VALID = "{message}"
    CHAN_VALIDATION_INVALID = "{message}"
    CHAN_BTN_GENERATE_SETUP = "Generate Setup Page"
    CHAN_OPT_COMMON_TO_GROUND = "Common circuit is connected to ground"
    CHAN_OPT_INTERLOCK_OPEN = "Interlock terminal is open"

    # ── Measurement-config top bar & status widget ───────────────────────────
    CFG_MODE_SWEEP = "Sweep"
    CFG_MODE_SAMPLING = "Sampling"
    CFG_MODE_QSCV = "QSCV"
    CFG_BTN_SAVE_SETUP = "Save Setup"
    CFG_MENU_SAVE_JSON = "Save JSON…"
    CFG_MENU_GENERATE_JSON = "Generate JSON"
    CFG_MENU_QUICK_APPLY_SETUP = "Quick Apply Setup"
    CFG_MENU_QUICK_APPLY_RUN = "Quick Apply Setup & Run"
    CFG_QUICK_NEED_CONNECTION = "Connect an instrument first."
    CFG_QUICK_BUSY = "Instrument is busy."
    CFG_STATUS_READY = "Ready to Save"
    CFG_STATUS_READY_AND_RUN = "Ready to Save and Run"
    CFG_STATUS_NOT_READY = "Not Ready"
    CFG_INFO_INDEXES = "Total measurement indexes"
    CFG_INFO_POINTS = "Total measurement points"
    CFG_INFO_EXEC_TIME = "Minimum runtime"
    CFG_INFO_STATUS = "Current setup status"
    CFG_MODAL_TITLE = "Measurement status"
    CFG_COL_CRITICAL = "Critical"
    CFG_COL_WARNINGS = "Warnings"
    CFG_COL_INFO = "Information"
    CFG_NO_CRITICAL = "No blocking errors."
    CFG_NO_WARNINGS = "No warnings."
    CFG_SAVED_TOAST = "Saved to {name}"  # save icon supplied by the view

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

    # ── Graphs page ──────────────────────────────────────────────────────────
    GRAPH_SCENE_DEFAULT = "Scene {n}"
    GRAPH_TT_ADD_SCENE = "Add scene"
    GRAPH_TT_TOGGLE_SIDEBAR = "Show/hide the configuration sidebar"
    GRAPH_CLOSE_SCENE_TITLE = "Close scene"
    GRAPH_CLOSE_SCENE_MSG = "Close this scene and discard its configuration?"
    GRAPH_RENAME_TITLE = "Rename scene"
    GRAPH_RENAME_LABEL = "Scene name:"
    GRAPH_TT_RENAME_HINT = "Double-click to rename this scene"
    # Sidebar tabs
    GRAPH_TAB_DATA = "Data"
    GRAPH_TAB_PLOT = "Plot"
    GRAPH_TAB_TOOLS = "Tools"
    GRAPH_TAB_ANALYSIS = "Analysis"
    # Data tab
    GRAPH_SEC_DATASETS = "Datasets"
    GRAPH_SEC_LAYOUT = "Grid layout"
    GRAPH_SEC_AXIS_X = "X axis"
    GRAPH_SEC_AXIS_Y = "Y axis"
    GRAPH_LBL_GRID = "Grid:"
    GRAPH_TT_GRID_ROWS = "Grid rows"
    GRAPH_TT_GRID_COLS = "Grid columns"
    GRAPH_CHK_MAXIMIZE = "Maximize active plot"
    GRAPH_LBL_VARIABLE = "Variable:"
    GRAPH_CHK_AUTOSCALE = "Auto scale"
    GRAPH_CHK_LOG = "Logarithmic"
    GRAPH_LBL_MIN = "Min:"
    GRAPH_LBL_MAX = "Max:"
    GRAPH_LBL_MULTIPLIER = "Multiplier:"
    GRAPH_NO_EXECUTIONS = "No executions in this project yet."
    GRAPH_INCOMPATIBLE_TOOLTIP = (
        "This execution's variables differ from the ones already "
        "plotted, so it cannot share this plot."
    )
    # Plot / Tools tabs
    GRAPH_SEC_VIEW = "View"
    GRAPH_SEC_CURSORS = "Cursors"
    GRAPH_SEC_ROI = "Region of interest"
    GRAPH_SEC_EXPORT = "Export"
    GRAPH_SEC_LABELS = "Labels"
    GRAPH_SEC_TRACES = "Traces"
    GRAPH_BTN_RESET_VIEW = "Reset view"
    GRAPH_LBL_MOUSE = "Mouse mode:"
    GRAPH_MOUSE_PAN = "Pan"
    GRAPH_MOUSE_ZOOM = "Zoom box"
    GRAPH_LBL_CURSORS = "Cursors:"
    GRAPH_CURSOR_OFF = "Off"
    GRAPH_CURSOR_SINGLE = "Single"
    GRAPH_CURSOR_DUAL = "Dual"
    GRAPH_LBL_CURSOR_SOURCE = "Cursor trace:"
    GRAPH_CHK_ROI = "ROI (fit / extraction window)"
    GRAPH_BTN_EXPORT_PNG = "Export PNG (active plot)…"
    GRAPH_BTN_EXPORT_PNG_SCENE = "Export PNG (entire scene)…"
    GRAPH_BTN_EXPORT_CSV = "Export CSV…"
    GRAPH_BTN_EXPORT_XLSX = "Export XLSX…"
    GRAPH_LBL_PLOT_TITLE = "Plot title:"
    GRAPH_LBL_X_LABEL = "X label:"
    GRAPH_LBL_Y_LABEL = "Y label:"
    GRAPH_PH_TITLE = "Optional — no title when empty"
    GRAPH_PH_AXIS_LABEL = "Auto — uses the variable name"
    GRAPH_NO_TRACES = "No traces in the active plot."
    GRAPH_CURSOR_READOUT = "x = {x}    y = {y}"
    GRAPH_CURSOR_DELTA = "Δx = {dx}    Δy = {dy}    Δy/Δx = {slope}"
    # Trace line styles / markers (order mirrors trace.LINE_STYLES/MARKERS)
    GRAPH_LINE_SOLID = "Solid"
    GRAPH_LINE_DASH = "Dash"
    GRAPH_LINE_DOT = "Dot"
    GRAPH_LINE_NONE = "None"
    GRAPH_MARKER_NONE = "None"
    GRAPH_MARKER_CIRCLE = "Circle"
    GRAPH_MARKER_SQUARE = "Square"
    GRAPH_MARKER_TRIANGLE = "Triangle"
    GRAPH_MARKER_CROSS = "Cross"
    # Analysis tab
    GRAPH_SEC_CURVE_FIT = "Curve fit"
    GRAPH_SEC_TRACE_MATH = "Trace math"
    GRAPH_LBL_FIT_TRACE = "Trace:"
    GRAPH_LBL_FIT_MODEL = "Model:"
    GRAPH_LBL_FIT_DEGREE = "Degree:"
    GRAPH_BTN_FIT_ROI = "Fit over ROI"
    GRAPH_BTN_FIT_FULL = "Fit full range"
    GRAPH_LBL_CATEGORY = "Category:"
    GRAPH_CAT_DERIVATIVE = "Derivative"
    GRAPH_CAT_UNARY = "Unary"
    GRAPH_CAT_BINARY = "Binary"
    GRAPH_LBL_OPERATION = "Operation:"
    GRAPH_LBL_SOURCE_A = "Source A:"
    GRAPH_LBL_SOURCE_B = "Source B:"
    GRAPH_BTN_ADD_COMPUTED = "Add computed trace"
    GRAPH_FITS_TITLE = "Fits"
    GRAPH_COMPUTED_TITLE = "Computed traces"
    GRAPH_TT_REMOVE_SELECTED = "Remove the selected entry"
    GRAPH_BTN_COPY_FIT = "Copy"
    GRAPH_TT_COPY_SELECTED = "Copy selected text"
    GRAPH_ANALYSIS_EMPTY = (
        "Select executions on the Data tab to enable analysis."
    )
    GRAPH_FIT_NEED_ROI = "Enable and position the ROI first."
    GRAPH_NON_FUNCTIONAL_MSG = (
        "This trace has multiple Y values for the same X that do not "
        "come from repeated acquisitions, so it is not a function of X "
        "and cannot be used for trace math or curve fitting."
    )
    # Export
    GRAPH_EXPORT_PNG_TITLE = "Export plot image"
    GRAPH_EXPORT_SCENE_TITLE = "Export scene image"
    GRAPH_EXPORT_CSV_TITLE = "Export plot data"
    GRAPH_EXPORT_DONE = "Saved {path}"
    GRAPH_EXPORT_ERROR = "Could not save file:\n{error}"
    GRAPH_EXPORT_NO_PLOT = "The active plot has nothing to export."

    # ── Global settings (Preferences dialog) ─────────────────────────────────
    SETTINGS_APPEARANCE_SECTION = "Appearance"
    SETTINGS_THEME_LABEL = "Theme"
    SETTINGS_THEME_RESTART_HINT = (
        "Theme changes take effect after the application is restarted."
    )
    SETTINGS_THEME_RESTART_TITLE = "Restart required"
    SETTINGS_THEME_RESTART_BODY = (
        "The new theme will be applied the next time you start "
        "Wizard 4155/4156."
    )
    THEME_LABEL_DARK = "Black"
    THEME_LABEL_LIGHT = "Light"
    THEME_LABEL_FRANCE = "France (light blue)"
    THEME_LABEL_BRASIL = "Brasil (dark green)"


def tr_ui(text_enum: CommandWizardText) -> str:
    return QCoreApplication.translate("UIText", text_enum.value)
