"""
gpib/__init__.py
----------------
Public surface of the GPIB hardware sub-package.

Layer contract
--------------
Everything in this package is framework-agnostic at the controller level
(controller.py) and restricted to Qt threading primitives at the worker
level (workers.py).  No Qt widget or UI import is permitted anywhere in
this package — that boundary is enforced by code review.

Import path for consumers:

    from wizard_4155_4156.gpib import GPIB41xxController
    from wizard_4155_4156.gpib import (
        ScanTask, ConnectTask, DisconnectTask,
        SetupTask, MeasurementRunTask, DataFetchTask,
        WorkerSignals, is_scpi_error_response,
    )
"""
from wizard_4155_4156.gpib.controller import GPIB41xxController
from wizard_4155_4156.gpib.workers import (
    ConnectTask,
    DataFetchTask,
    DisconnectTask,
    MeasurementRunTask,
    ScanTask,
    SetupTask,
    WorkerSignals,
    is_scpi_error_response,
)

__all__ = [
    # Hardware abstraction
    "GPIB41xxController",
    # Worker tasks
    "ScanTask",
    "ConnectTask",
    "DisconnectTask",
    "SetupTask",
    "MeasurementRunTask",
    "DataFetchTask",
    # Shared primitives
    "WorkerSignals",
    "is_scpi_error_response",
]
