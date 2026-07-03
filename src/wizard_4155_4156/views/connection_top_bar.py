"""
views/connection_top_bar.py
---------------------------
Thin horizontal status bar rendered at the top of the window.
Hosts the CompactConnectorWidget (or its demo surrogate) as the
centred focal element, with branding on the left and a project-status
pill on the right.

No business logic lives here — the owner updates the pill via
set_project_status() to reflect whether a project is open.  (Live
hardware busy/ready is surfaced by the bottom QStatusBar instead.)
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from wizard_4155_4156.styles.stylesheets import (
    connection_top_bar_stylesheet,
    top_bar_app_name_stylesheet,
    top_bar_label_stylesheet,
    top_bar_sys_status_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P


class ConnectionTopBar(QFrame):
    """
    Full-width bar pinned above the NavigationBar + page-stack area.

    Parameters
    ----------
    connector_widget:
        An instance of CompactConnectorWidget (or DemoCompactConnectorWidget).
        The bar centres it horizontally regardless of its fixed size.
    """

    #: Longest project name shown in the pill before it is elided.
    MAX_PROJECT_NAME_CHARS = 15

    def __init__(
        self,
        connector_widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._connector = connector_widget
        self._setup_ui()
        self._apply_styles()
        # Start with no project open.
        self.set_project_status(None)

    # ── Public API ───────────────────────────────────────────────────────────

    def set_project_status(self, project_name: str | None) -> None:
        """Reflect the open-project state in the top-bar pill.

        Pass the project name when one is open, or ``None`` when no project
        is loaded (application start / project closed).  Long names are
        elided to ``MAX_PROJECT_NAME_CHARS``; the full name is kept as the
        tooltip.
        """
        if not project_name:
            self._lbl_status.setText("📁  No Project Open")
            self._lbl_status.setToolTip("")
            self._lbl_status.setStyleSheet(
                top_bar_sys_status_stylesheet()
                .replace(P.STATUS_OK, P.STATUS_WARN)
            )
            return

        name = self._elide(project_name, self.MAX_PROJECT_NAME_CHARS)
        self._lbl_status.setText(f"📂  {name}")
        self._lbl_status.setToolTip(project_name)
        self._lbl_status.setStyleSheet(top_bar_sys_status_stylesheet())

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _elide(text: str, max_chars: int) -> str:
        text = text.strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "…"

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setFixedHeight(P.TOP_BAR_HEIGHT)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(20)

        # Left — branding
        brand = QWidget()
        brand_row = QHBoxLayout(brand)
        brand_row.setSpacing(10)
        brand_row.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("⚡")
        icon.setStyleSheet("font-size: 24px; background: transparent;")
        brand_row.addWidget(icon)

        name = QLabel("Wizard 4155/4156")
        name.setStyleSheet(top_bar_app_name_stylesheet())
        brand_row.addWidget(name)

        layout.addWidget(brand)

        # Centre — connector widget
        layout.addStretch()

        centre = QWidget()
        centre_row = QHBoxLayout(centre)
        centre_row.setSpacing(16)
        centre_row.setContentsMargins(0, 0, 0, 0)
        centre_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        conn_label = QLabel("GPIB CONNECTION")
        conn_label.setStyleSheet(top_bar_label_stylesheet())
        centre_row.addWidget(conn_label)
        centre_row.addWidget(self._connector)

        layout.addWidget(centre, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

        # Right — project status pill (text set by set_project_status())
        self._lbl_status = QLabel()
        layout.addWidget(self._lbl_status)

    def _apply_styles(self) -> None:
        self.setStyleSheet(connection_top_bar_stylesheet())
        self._lbl_status.setStyleSheet(top_bar_sys_status_stylesheet())
