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


def tr_ui(text_enum: CommandWizardText) -> str:
    return QCoreApplication.translate("UIText", text_enum.value)
