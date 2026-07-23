"""
extra_widgets/instrument_mismatch_dialog.py
-------------------------------------------
Shared confirmation shown before sending a setup to an instrument other than
the one it was created for.

Used by both execution workflows — the Runs page (saved setups) and the Quick
Apply / Quick Apply & Run actions of the config pages.  Each workflow owns its
own session-scoped "don't ask again" state; this module only renders the box
and reports what the user chose.
"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QMessageBox, QWidget

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui

_T = CommandWizardText


def confirm_instrument_mismatch(
    parent: QWidget | None,
    setup_model: str,
    connected_model: str,
) -> tuple[bool, bool]:
    """Warn that the setup targets a different instrument than connected.

    Returns ``(proceed, dont_ask_again)``; the caller owns the session-scoped
    suppression decision.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr_ui(_T.MISMATCH_TITLE))
    box.setText(
        tr_ui(_T.MISMATCH_MSG).format(
            setup_model=setup_model,
            connected_model=connected_model,
        )
    )
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    dont_ask = QCheckBox(tr_ui(_T.MISMATCH_DONT_ASK))
    box.setCheckBox(dont_ask)
    proceed = box.exec() == QMessageBox.StandardButton.Yes
    return proceed, dont_ask.isChecked()
