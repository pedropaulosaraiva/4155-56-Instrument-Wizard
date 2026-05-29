"""
views/connection_top_bar.py
---------------------------
Thin horizontal status bar rendered at the top of the window.
Hosts the CompactConnectorWidget (or its demo surrogate) as the
centred focal element, with branding on the left and a system-status
pill on the right.

No business logic lives here — the presenter updates the status pill
via set_system_status().
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

    def __init__(
        self,
        connector_widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._connector = connector_widget
        self._setup_ui()
        self._apply_styles()

    # ── Public API ───────────────────────────────────────────────────────────

    def set_system_status(self, ready: bool) -> None:
        if ready:
            self._lbl_status.setText("🟢  System Ready")
            self._lbl_status.setStyleSheet(top_bar_sys_status_stylesheet())
        else:
            self._lbl_status.setText("🟡  Hardware Busy")
            self._lbl_status.setStyleSheet(
                top_bar_sys_status_stylesheet()
                .replace(P.STATUS_OK, P.STATUS_WARN)
            )

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

        # Right — system status pill
        self._lbl_status = QLabel("🟢  System Ready")
        layout.addWidget(self._lbl_status)

    def _apply_styles(self) -> None:
        self.setStyleSheet(connection_top_bar_stylesheet())
        self._lbl_status.setStyleSheet(top_bar_sys_status_stylesheet())
