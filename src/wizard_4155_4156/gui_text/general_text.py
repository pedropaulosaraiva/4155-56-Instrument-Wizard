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
    CHAN_BTN_GENERATE_SETUP = "Generate a New Setup Page"
    CHAN_OPT_COMMON_TO_GROUND = "Common circuit is connected to ground"
    CHAN_OPT_INTERLOCK_OPEN = "Interlock terminal is open"

    # SMU section naming — follows the selected instrument model.
    # 4155x mainframes carry Medium Power SMUs, 4156x High Resolution SMUs.
    CHAN_SMU_SECTION_MPSMU = "Medium Power Source Monitor Units  (MPSMU)"
    CHAN_SMU_SECTION_HRSMU = "High Resolution Source Monitor Units  (HRSMU)"
    CHAN_SMU_PREFIX_MPSMU = "MPSMU"
    CHAN_SMU_PREFIX_HRSMU = "HRSMU"

    # Unit-card field captions
    CHAN_FIELD_MODE = "MODE"
    CHAN_FIELD_FUNCTION = "FUNCTION"
    CHAN_FIELD_VNAME = "V-Name"
    CHAN_FIELD_INAME = "I-Name"

    # SMU output modes.  The combo item text is the friendly label below; its
    # userData stays the raw SMUMode value the presenter expects.
    CHAN_SMU_MODE_V = "Source Voltage / Measure Current (V)"
    CHAN_SMU_MODE_I = "Source Current / Measure Voltage (I)"
    CHAN_SMU_MODE_VPULSE = "Source Pulsed Voltage / Measure Current (VPULSE)"
    CHAN_SMU_MODE_IPULSE = "Source Pulsed Current / Measure Voltage (IPULSE)"
    CHAN_SMU_MODE_COMM = "Common Terminal / Measure Current (COMM)"

    # VMU modes
    CHAN_VMU_MODE_V = "Measure Voltage to Common (V)"
    CHAN_VMU_MODE_DVOLT = "Differential Voltage Between VMUs (DVOLT)"

    # Unit functions (shared by SMU and VSU cards)
    CHAN_FUNC_CONST = "Constant Output (CONST)"
    CHAN_FUNC_VAR1 = "Primary Sweep (VAR1)"
    CHAN_FUNC_VAR2 = "Subordinate Sweep (VAR2)"
    CHAN_FUNC_VARD = "Synchronous Sweep (VAR1')"

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
    TABLE_EMPTY = "No measurement data yet. Run a measurement to populate."
    TABLE_SETUP_LABEL = "Setup:"
    TABLE_EXEC_LABEL = "Run:"
    TABLE_FORMAT_LABEL = "Format:"
    TABLE_BTN_DOWNLOAD = "Export run"  # download icon supplied by the view
    TABLE_BTN_COPY = "Copy"  # copy icon supplied by the view
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
    # Export options row (CSV/XLSX only).
    TABLE_DELIM_LABEL = "Delimiter:"
    TABLE_DECIMAL_LABEL = "Decimal:"
    TABLE_QUOTE_LABEL = "Quote:"
    TABLE_DELIM_COMMA = "Comma (,)"
    TABLE_DELIM_SEMICOLON = "Semicolon (;)"
    TABLE_DELIM_TAB = "Tab"
    TABLE_DELIM_SPACE = "Space"
    TABLE_DEC_DOT = "Dot (.)"
    TABLE_DEC_COMMA = "Comma (,)"
    TABLE_QUOTE_DOUBLE = 'Double quote (")'
    TABLE_QUOTE_SINGLE = "Single quote (')"
    TABLE_QUOTE_NONE = "None"
    TABLE_DATETIME_CHECK = (
        "Include measurement date and time in the exported filename"
    )
    TABLE_BTN_SAVE_ALL = (
        "Export all runs (.zip)"  # save icon supplied by the view
    )
    TABLE_SAVE_ALL_TITLE = "Export all runs (.zip)"
    TABLE_SAVE_ALL_FILTER = "ZIP archive (*.zip)"
    TABLE_SAVED_ALL = "Saved {count} runs to {path}"
    # Shared with the import dialog (uniform CSV dialect rule).
    CSV_DIALECT_CONFLICT = (
        "Comma can be both the delimiter and the decimal separator only "
        "when a quote character is used."
    )

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
    # Import Measure (external data files → setup + runs)
    RUNS_BTN_IMPORT = "Import Measure"
    RUNS_IMPORT_TITLE = "Import measure"
    RUNS_IMPORT_NAME_LABEL = "Name"
    RUNS_IMPORT_NAME_PLACEHOLDER = "Unique setup name for the imported data"
    RUNS_IMPORT_DESC_LABEL = "Description (optional)"
    RUNS_IMPORT_DESC_PLACEHOLDER = (
        "Where this data comes from, instrument, conditions…"
    )
    RUNS_IMPORT_FORMAT_LABEL = "File format"
    RUNS_IMPORT_FMT_CSV = "CSV"
    RUNS_IMPORT_DELIM_LABEL = "Delimiter"
    RUNS_IMPORT_DELIM_COMMA = "Comma (,)"
    RUNS_IMPORT_DELIM_SEMI = "Semicolon (;)"
    RUNS_IMPORT_DELIM_TAB = "Tab"
    RUNS_IMPORT_DELIM_WS = "Whitespace (spaces/tabs)"
    RUNS_IMPORT_DECIMAL_LABEL = "Decimal separator"
    RUNS_IMPORT_DECIMAL_POINT = "Point (.)"
    RUNS_IMPORT_DECIMAL_COMMA = "Comma (,)"
    RUNS_IMPORT_QUOTE_LABEL = "Quote character"
    RUNS_IMPORT_QUOTE_DOUBLE = 'Double quote (")'
    RUNS_IMPORT_QUOTE_SINGLE = "Single quote (')"
    RUNS_IMPORT_QUOTE_NONE = "None"
    RUNS_IMPORT_DROP_HINT = "Drag & drop data files here"
    RUNS_IMPORT_BROWSE = "Browse…"
    RUNS_IMPORT_BROWSE_TITLE = "Select data files"
    RUNS_IMPORT_FILE_FILTER = "CSV files (*.csv);;All files (*)"
    RUNS_IMPORT_HINT = (
        "Each run will be named after its file. All files must contain "
        "the same variables (columns)."
    )
    RUNS_IMPORT_BTN_OK = "Import"
    RUNS_IMPORT_ERR_HEADER = (
        "Some files could not be imported — nothing was saved:"
    )
    RUNS_IMPORT_ERR_STANDARD_VARS = "Standard variables: {vars}"
    RUNS_IMPORT_ERR_NO_STANDARD = "Standard variables: none (no valid file)"
    RUNS_IMPORT_NO_COPY = (
        "Imported setups have no instrument configuration."
    )
    # Import Execution (external data files → runs of an existing setup)
    RUNS_BTN_IMPORT_EXEC = "Import Execution"
    RUNS_IMPORT_EXEC_TITLE = 'Import runs into "{setup}"'
    RUNS_IMPORT_EXEC_NAME_LABEL = "Run name (applies to a single file)"
    RUNS_IMPORT_EXEC_NAME_PLACEHOLDER = "Name for the imported run"
    RUNS_IMPORT_EXEC_HINT = (
        "Files must contain exactly the setup's variables: {vars}. "
        "When multiple files are selected, each run is named after its "
        "file."
    )
    RUNS_IMPORT_EXEC_NO_VARS = (
        "This setup defines no display variables — imported files cannot "
        "be validated against it."
    )

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
    GRAPH_CHK_GRID = "Grid"
    GRAPH_LBL_MIN = "Min:"
    GRAPH_LBL_MAX = "Max:"
    GRAPH_LBL_MULTIPLIER = "Multiplier:"
    GRAPH_NO_EXECUTIONS = "No executions in this project yet."
    GRAPH_INCOMPATIBLE_TOOLTIP = (
        "Its variables ({exec_vars}) differ from the ones already "
        "plotted ({plot_vars}), so it cannot share this plot."
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
    # Font sizes section (values in points)
    GRAPH_SEC_FONTS = "Font sizes"
    GRAPH_LBL_FONT_TITLE = "Title:"
    GRAPH_LBL_FONT_X = "X label:"
    GRAPH_LBL_FONT_Y = "Y label:"
    GRAPH_LBL_FONT_TICKS = "Tick labels:"
    GRAPH_LBL_FONT_LEGEND = "Legend:"
    GRAPH_LBL_LINE = "Line:"
    GRAPH_LBL_MARKER = "Marker:"
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
    GRAPH_TT_TRACE_WIDTH = "Line width (px)"
    GRAPH_TT_MARKER_SIZE = "Marker size (px)"
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
    GRAPH_LBL_EXPORT_BG = "Background:"
    GRAPH_EXPORT_BG_THEME = "Theme"
    GRAPH_EXPORT_BG_WHITE = "White"
    GRAPH_EXPORT_BG_BLACK = "Black"
    GRAPH_EXPORT_BG_TRANSPARENT = "Transparent"
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

    # ── Advanced options (Preferences dialog) ────────────────────────────────
    ADVANCED_SECTION = "Advanced Options"
    ADVANCED_WARNING = (
        "For advanced users only — these options change the application's "
        "default behavior."
    )
    ADVANCED_SKIP_RESET_LABEL = "Skip instrument reset before each setup/run"
    ADVANCED_SKIP_RESET_HINT = (
        "When enabled, the application does not send the instrument reset "
        "command at the start of a setup or run. This lets you manually "
        "configure the instrument beforehand — for example performing a Zero "
        "Offset Cancel, an operation not yet supported by the application — "
        "and preserve those settings when the setup or run begins."
    )
    ADVANCED_KEEP_CAL_LABEL = "Keep automatic calibration enabled"
    ADVANCED_KEEP_CAL_HINT = (
        "When enabled, the application does not disable the instrument's "
        "automatic calibration (performed roughly every 30 minutes). Remember "
        "to disconnect the DUT after each measurement so the instrument can "
        "run its calibration cycle when required. Note: an instrument reset "
        "does not erase calibration data — it only restores the default "
        "operating configuration — so this option simply keeps auto "
        "calibration on."
    )
    ADVANCED_DELETE_RUNS_BUTTON = "Delete All Measurement Runs…"
    ADVANCED_DELETE_RUNS_HINT = (
        "Deletes every recorded measurement run. Measurement setups and graph "
        "scenes are left untouched."
    )
    ADVANCED_DELETE_RUNS_DISABLED_TIP = (
        "Open a project first to delete its measurement runs."
    )
    ADVANCED_DELETE_RUNS_TITLE = "Delete all measurement runs"
    ADVANCED_DELETE_RUNS_TOKEN = "DELETE ALL"
    ADVANCED_DELETE_RUNS_PROMPT = (
        "This permanently deletes EVERY recorded measurement run in the open "
        "project. Measurement setups and graph scenes are preserved, but the "
        "deleted runs cannot be recovered.\n\n"
        "If you want to keep this project's measurements, make a copy of the "
        "project file before continuing.\n\n"
        "To confirm, type DELETE ALL below:"
    )
    ADVANCED_DELETE_RUNS_SUCCESS = (
        "Deleted {count} measurement run(s). Setups and graph scenes were "
        "preserved."
    )
    ADVANCED_DELETE_RUNS_NONE = "There are no measurement runs to delete."


def tr_ui(text_enum: CommandWizardText) -> str:
    return QCoreApplication.translate("UIText", text_enum.value)
