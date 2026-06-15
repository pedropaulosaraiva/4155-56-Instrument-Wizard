"""
views/main_window.py
--------------------
Root QMainWindow.

Layout
------
┌──────────────────────────────────────────────────┐
│               ConnectionTopBar                   │  fixed height
├──────┬───────────────────────────────────────────┤
│      │                                           │
│ Nav  │          QStackedWidget                   │  expands
│ Bar  │          (one BasePage per index)         │
│      │                                           │
└──────┴───────────────────────────────────────────┘
│               QStatusBar                         │  fixed height

Responsibilities
----------------
- Instantiate all pages and register them in QStackedWidget.
- Own the NavigationBar and connect page_changed → stack navigation.
- Own HomePresenter and wire its output signals.
- Own the menu bar with Recent Projects submenu.
- Delegate all styling to stylesheets.py.
- Expose on_data_ready / on_hardware_busy for connector widget signals.
"""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.db.engine import PROJECT_EXTENSION, ProjectManager
from wizard_4155_4156.db.global_settings import GlobalSettingsManager
from wizard_4155_4156.extra_widgets.settings_dialog import SettingsDialog
from wizard_4155_4156.extra_widgets.setup_metadata_dialog import (
    SetupMetadataDialog,
)
from wizard_4155_4156.models.project import RecentProjectsManager
from wizard_4155_4156.presenters.channels_presenter import ChannelsPresenter
from wizard_4155_4156.presenters.connector_presenter import ConnectorPresenter
from wizard_4155_4156.presenters.home_presenter import HomePresenter
from wizard_4155_4156.presenters.measure_config_factory import (
    MeasureConfigFactory,
)
from wizard_4155_4156.presenters.measurements_presenter import (
    MeasurementsPresenter,
)
from wizard_4155_4156.presenters.runs_presenter import RunsPresenter
from wizard_4155_4156.styles.stylesheets import (
    application_stylesheet,
    status_bar_stylesheet,
    status_indicator_busy_stylesheet,
    status_indicator_ready_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.connection_top_bar import ConnectionTopBar
from wizard_4155_4156.views.connector_widget import CompactConnectorWidget
from wizard_4155_4156.views.navigation_bar import NavigationBar
from wizard_4155_4156.views.pages import (
    BasePage,
    ChannelsPageView,
    GraphPage,
    HomePageView,
    MeasurementsPageView,
    Page,
    RunsPageView,
    TablePageView,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Wizard 4155/4156 — Semiconductor Analyzer")
        self.setMinimumSize(1300, 760)

        # ── Core models ──────────────────────────────────────────────────────
        self._recent_manager = RecentProjectsManager()
        # Per-project SQLite database (one open project at a time) and global
        # JSON settings.  Mirror RecentProjectsManager's ownership pattern.
        self._project_manager = ProjectManager()
        self._global_settings = GlobalSettingsManager()

        # ── Build UI ─────────────────────────────────────────────────────────
        self._build_menu()
        self._build_central_widget()
        self._build_status_bar()

        # ── Presenters ───────────────────────────────────────────────────────
        self._home_presenter = HomePresenter(
            view=self._home_page,
            model=self._recent_manager,
            parent=self,
        )
        self._home_presenter.project_file_opened.connect(
            self._on_project_file_opened
        )
        self._home_presenter.new_project_triggered.connect(
            self._on_new_project
        )
        self._home_presenter.settings_requested.connect(
            self._show_settings_dialog
        )

        # ── ChannelsPresenter ────────────────────────────────────────────────
        # Call self._channels_presenter.get_config() from SweepConfigPresenter
        # MeasurementsPresenter to read active channel layout and variable
        # names.
        self._channels_presenter = ChannelsPresenter(
            view=self._channels_page, parent=self
        )
        self._channels_presenter.measure_configured.connect(
            self._on_measure_configured
        )

        # ── MeasureConfigFactory ─────────────────────────────────────────────
        # Lazily generates the measurement-config page (sweep or sampling)
        # from a static channels snapshot each time "Configure Measure" is
        # clicked.  No page exists until then — the nav button stays
        # disabled.
        self._measure_factory = MeasureConfigFactory(
            channels_presenter=self._channels_presenter,
            parent=self,
        )
        self._nav_bar.set_page_enabled(Page.MEASURE_CONFIG, False)
        # Everything except Home is locked until a project is opened/created.
        self._set_project_pages_enabled(False)

        # ── ConnectorPresenter ───────────────────────────────────────────────
        # Owns GPIB41xxController + single-thread QThreadPool.
        # _connector (CompactConnectorWidget) is the View;
        # this is its Presenter.
        self._connector_presenter = ConnectorPresenter(
            view=self._connector, parent=self
        )
        self._connector_presenter.data_ready.connect(self.on_data_ready)
        self._connector_presenter.hardware_busy.connect(self.on_hardware_busy)

        # ── MeasurementsPresenter ────────────────────────────────────────────
        # Orchestrates Setup/Run/Fetch by reading config from the generated
        # measure-config page (or a loaded file) and delegating hardware
        # I/O to the connector.
        self._measurements_presenter = MeasurementsPresenter(
            view=self._measurements_page,
            config_provider=self._measure_factory,
            connector_presenter=self._connector_presenter,
            parent=self,
        )

        # ── RunsPresenter ────────────────────────────────────────────────────
        # CRUD browser over the open project database.  Reads the live config
        # through the same factory and stamps author/org from global settings.
        self._runs_presenter = RunsPresenter(
            view=self._runs_page,
            project_manager=self._project_manager,
            config_provider=self._measure_factory,
            settings_manager=self._global_settings,
            connector_presenter=self._connector_presenter,
            parent=self,
        )
        self._runs_presenter.execution_data_ready.connect(self.on_data_ready)
        self._runs_presenter.copy_to_config_requested.connect(
            self._on_copy_to_config
        )

        # Trigger initial bus scan AFTER signal wiring so scan_results
        # reaches the modal's combo box via the connected Slot.
        self._connector_presenter.start()

        # ── Global stylesheet ────────────────────────────────────────────────
        self.setStyleSheet(application_stylesheet())

    # =========================================================================
    # Build helpers
    # =========================================================================

    def _build_central_widget(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Top bar ─────────────────────────────────────────────────────────────
        self._connector = CompactConnectorWidget()
        self._top_bar = ConnectionTopBar(self._connector)
        root_layout.addWidget(self._top_bar)

        # Horizontal content area: NavBar | PageStack ─────────────────────────
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._nav_bar = NavigationBar()
        self._nav_bar.page_changed.connect(self._navigate_to)
        content_layout.addWidget(self._nav_bar)

        # Thin separator between nav and stack
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(
            f"color: {P.BORDER}; max-width: 1px; background: {P.BORDER};"
        )
        content_layout.addWidget(sep)

        self._stack = self._build_page_stack()
        content_layout.addWidget(self._stack, stretch=1)

        root_layout.addWidget(content, stretch=1)
        self.setCentralWidget(root)

    def _build_page_stack(self) -> QStackedWidget:
        """
        Pages are resolved through self._page_widgets (Page → widget),
        NOT through stack indices.  Page.MEASURE_CONFIG starts empty —
        its widget is generated lazily by MeasureConfigFactory when
        "Configure Measure" is clicked on the Channels page.
        """
        stack = QStackedWidget()

        self._home_page = HomePageView()
        stack.addWidget(self._home_page)

        self._channels_page = ChannelsPageView()
        stack.addWidget(self._channels_page)
        self._measurements_page = MeasurementsPageView()
        stack.addWidget(self._measurements_page)
        self._runs_page = RunsPageView()
        stack.addWidget(self._runs_page)
        self._graph_page = GraphPage()
        stack.addWidget(self._graph_page)
        self._table_page = TablePageView()
        stack.addWidget(self._table_page)

        self._page_widgets: dict[Page, QWidget | None] = {
            Page.HOME: self._home_page,
            Page.CHANNELS: self._channels_page,
            Page.MEASURE_CONFIG: None,  # generated lazily
            Page.MEASUREMENTS: self._measurements_page,
            Page.RUNS: self._runs_page,
            Page.GRAPH: self._graph_page,
            Page.TABLE: self._table_page,
        }

        return stack

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.setStyleSheet(status_bar_stylesheet())
        self.setStatusBar(bar)

        self._status_indicator = QLabel(" ● Ready ")
        self._status_indicator.setStyleSheet(
            status_indicator_ready_stylesheet()
        )
        bar.addWidget(self._status_indicator)

        bar.showMessage(
            "Semiconductor Parameter Analyzer — GPIB Controller Ready"
        )
        self._status_bar = bar

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File ────────────────────────────────────────────────────────────────
        file_menu = mb.addMenu("File")

        new_act = QAction("New Project", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self._on_new_project)
        file_menu.addAction(new_act)

        open_act = QAction("Open Project…", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._on_open_project_menu)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        self._recent_menu = QMenu("Recent Projects", self)
        file_menu.addMenu(self._recent_menu)
        self._update_recent_menu()

        file_menu.addSeparator()

        save_act = QAction("Save", self)
        save_act.setShortcut("Ctrl+S")
        file_menu.addAction(save_act)

        save_as_act = QAction("Save As…", self)
        save_as_act.setShortcut("Ctrl+Shift+S")
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        exit_act = QAction("Exit", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Options ─────────────────────────────────────────────────────────────
        opt_menu = mb.addMenu("Options")

        conn_act = QAction("Connection Wizard…", self)
        conn_act.setShortcut("Ctrl+Shift+C")
        conn_act.triggered.connect(self._show_connection_wizard)
        opt_menu.addAction(conn_act)

        pref_act = QAction("Preferences…", self)
        pref_act.setShortcut("Ctrl+,")
        pref_act.triggered.connect(self._show_settings_dialog)
        opt_menu.addAction(pref_act)

    # =========================================================================
    # Navigation
    # =========================================================================

    def _navigate_to(self, page: Page) -> None:
        widget = self._page_widgets.get(page)
        if widget is None:
            # Dynamic slot not generated yet (Measure Config).
            self._status_bar.showMessage(
                "Configure a measurement from the Channels page first.", 3000
            )
            return
        self._stack.setCurrentWidget(widget)
        # Let the page react to becoming visible
        if isinstance(widget, BasePage):
            widget.on_activate()
        # Keep nav bar in sync when navigation is triggered programmatically
        self._nav_bar.set_active_page(page)
        self._status_bar.showMessage(
            f"Navigated to: {page.name.replace('_', ' ').title()}", 2000
        )

    # =========================================================================
    # Presenter output handlers
    # =========================================================================

    def _on_project_file_opened(self, path: str) -> None:
        """Open an existing .wiz4155 project database."""
        try:
            self._project_manager.open(path)
        except FileNotFoundError:
            self._status_bar.showMessage(f"Project not found: {path}", 6000)
            # Drop the stale entry from recents and refresh the home view.
            self._home_presenter._on_remove_project(path)  # noqa: SLF001
            self._update_recent_menu()
            return
        except Exception as exc:  # noqa: BLE001
            self._status_bar.showMessage(
                f"Could not open project: {exc}", 6000
            )
            return
        self._update_recent_menu()
        self._activate_project(path)

    def _on_new_project(self) -> None:
        """Create a new standalone .wiz4155 project database."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "New Project",
            "",
            f"Project Database (*{PROJECT_EXTENSION})",
        )
        if not path:
            return
        if not path.endswith(PROJECT_EXTENSION):
            path += PROJECT_EXTENSION
        try:
            self._project_manager.create(path)
        except Exception as exc:  # noqa: BLE001
            self._status_bar.showMessage(
                f"Could not create project: {exc}", 6000
            )
            return
        # Record it in recents (also refreshes the home view) and open it.
        self._home_presenter.register_opened_file(path)
        self._update_recent_menu()
        self._activate_project(path)

    def _activate_project(self, path: str) -> None:
        """Common post-open/create steps: title, unlock pages, runs page."""
        name = self._project_manager.current_name
        self.setWindowTitle(
            f"Wizard 4155/4156 — Semiconductor Analyzer  ·  {name}"
        )
        self._set_project_pages_enabled(True)
        self._runs_presenter.set_database(self._project_manager.current_db)
        self._navigate_to(Page.RUNS)
        self._status_bar.showMessage(f"Project ready: {path}", 5000)

    def _set_project_pages_enabled(self, enabled: bool) -> None:
        """Lock/unlock every page except Home (and the lazy Measure Config)."""
        for page in (
            Page.CHANNELS,
            Page.MEASUREMENTS,
            Page.RUNS,
            Page.GRAPH,
            Page.TABLE,
        ):
            self._nav_bar.set_page_enabled(page, enabled)

    def _on_save_setup_to_db(self) -> None:
        """Persist the live measurement config as a setup and jump to Runs."""
        if not self._project_manager.is_open:
            self._status_bar.showMessage(
                "Open or create a project before saving a setup.", 5000
            )
            return
        # Validate the live config up front so we never prompt on an invalid one.
        try:
            self._measure_factory.get_json()
        except ValueError as exc:
            self._status_bar.showMessage(f"Cannot save setup: {exc}", 6000)
            return
        dlg = SetupMetadataDialog(title="Save setup", parent=self)
        if not dlg.exec():
            return
        error = self._runs_presenter.create_setup_from_current(
            dlg.get_name(), dlg.get_description()
        )
        if error:
            self._status_bar.showMessage(error, 6000)
            return
        self._navigate_to(Page.RUNS)
        self._status_bar.showMessage("Setup saved to project.", 4000)

    def _show_settings_dialog(self) -> None:
        dlg = SettingsDialog(self._global_settings.get(), self)
        if dlg.exec():
            self._global_settings.save(dlg.get_settings())
            self._status_bar.showMessage("Settings saved.", 3000)

    def _on_measure_configured(self, _config_dict: dict) -> None:
        """
        "Configure Measure" clicked on the Channels page: discard any
        previously generated measure-config page and build a fresh one
        from the current channels snapshot, then navigate to it.
        """
        self._install_measure_config(
            self._measure_factory.generate,
            "Measurement configuration page generated.",
        )

    def _on_copy_to_config(self, channels_config, config_dict: dict) -> None:
        """Open a fresh config page preloaded from a saved setup (copy)."""
        self._install_measure_config(
            lambda: self._measure_factory.generate_from_setup(
                channels_config, config_dict
            ),
            "Setup copied to a new measurement configuration.",
        )

    def _install_measure_config(self, generate_fn, success_msg: str) -> None:
        """Swap in a freshly generated measure-config page and navigate to it.

        Shared by "Configure Measure" (from channels) and "Copy to measurement
        configuration" (from a saved setup).
        """
        old_page = self._measure_factory.current_page()
        if old_page is not None:
            # Remove from the stack BEFORE deleting so Qt never paints
            # a dying widget.
            self._stack.removeWidget(old_page)
            old_page.deleteLater()
        self._page_widgets[Page.MEASURE_CONFIG] = None

        new_page = generate_fn()
        if new_page is None:
            # Unsupported mode (QSCV) — keep the slot empty.
            self._nav_bar.set_page_enabled(Page.MEASURE_CONFIG, False)
            self._status_bar.showMessage(
                "QSCV configuration is not yet supported.", 5000
            )
            return

        self._stack.addWidget(new_page)
        self._page_widgets[Page.MEASURE_CONFIG] = new_page
        # "Save Setup" on the config page persists to the DB + jumps to Runs.
        new_page.save_to_db_requested.connect(self._on_save_setup_to_db)
        self._nav_bar.set_page_enabled(Page.MEASURE_CONFIG, True)
        self._navigate_to(Page.MEASURE_CONFIG)
        self._status_bar.showMessage(success_msg, 5000)

    # =========================================================================
    # Menu handlers (delegate to presenter where possible)
    # =========================================================================

    def _on_open_project_menu(self) -> None:
        """Delegate file dialog to HomePresenter."""
        self._home_presenter._on_open_project()  # noqa: SLF001

    def _show_connection_wizard(self) -> None:
        self._connector.modal.show()
        self._connector.modal.raise_()
        self._connector.modal.activateWindow()
        self._status_bar.showMessage("Connection wizard opened.", 3000)

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        projects = self._recent_manager.get_projects()[:8]
        if not projects:
            placeholder = QAction("No recent projects", self)
            placeholder.setEnabled(False)
            self._recent_menu.addAction(placeholder)
            return
        for proj in projects:
            act = QAction(proj.name, self)
            act.setData(proj.path)
            act.triggered.connect(
                lambda _checked, p=proj.path: (
                    self._home_presenter._on_project_opened(p)  # noqa: SLF001
                )
            )
            self._recent_menu.addAction(act)

    # =========================================================================
    # Hardware signal handlers  (connected to connector widget)
    # =========================================================================

    def on_data_ready(self, data: dict) -> None:
        self._status_bar.showMessage(
            f"Data received — {len(data)} record(s).", 5000
        )
        # Surface fetched data first as a table, then switch to that page.
        self._table_page.display_data(data)
        self._navigate_to(Page.TABLE)

    def on_hardware_busy(self, busy: bool) -> None:
        self._status_indicator.setText(" ● Busy " if busy else " ● Ready ")
        self._status_indicator.setStyleSheet(
            status_indicator_busy_stylesheet()
            if busy
            else status_indicator_ready_stylesheet()
        )
        self._top_bar.set_system_status(not busy)

    def closeEvent(self, event) -> None:  # noqa: N802
        """
        Drain the GPIB thread pool before the window is destroyed.
        Without this, background tasks may attempt to access Qt objects
        that are already being torn down, causing a segfault.
        """
        self._connector_presenter.cleanup()
        self._project_manager.close()
        super().closeEvent(event)
