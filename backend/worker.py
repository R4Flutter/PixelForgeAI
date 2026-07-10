"""
worker.py
---------
ProcessingWorker - a QThread that runs PipelineConnector off the UI thread and
emits progress/status/log updates as Qt signals bound to UI slots.

This is the ONLY PySide6-aware piece of the backend. The connector itself stays
Qt-agnostic, so pause/cancel/resume are simple threading.Event toggles owned by
this worker.
"""

from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QThread, Signal

from backend.connector import Callbacks, ConnectorError, PipelineConnector
from backend.entitlement import EntitlementManager
from backend.job import JobRequest, RunSummary


class ProcessingWorker(QThread):
    # Emitted from the worker thread; consumed on the UI thread via queued
    # connections (default for cross-thread signal/slot).
    stage = Signal(str)
    status = Signal(str)
    progress = Signal(int, int, str)        # done, total, current_file
    log_line = Signal(str, str, str)        # level, logger, message
    image_failed = Signal(str, str)        # file_name, error_message
    failed_job = Signal(str)               # catastrophic connector error
    finished_job = Signal(object)          # RunSummary

    def __init__(self, job: JobRequest, parent=None) -> None:
        super().__init__(parent)
        self._job = job
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        self._connector = PipelineConnector(self._build_callbacks())

    # ------------------------------------------------------------------ #
    # Control surface (called from the UI thread)
    # ------------------------------------------------------------------ #
    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    # ------------------------------------------------------------------ #
    # QThread entry point
    # ------------------------------------------------------------------ #
    def run(self) -> None:  # noqa: D401
        # Defense in depth: the UI already gates on entitlement, but a worker
        # must not start a job if the installation is not entitled - even if the
        # UI were bypassed. Constructing the manager reads the small sealed
        # files, so this is cheap.
        if not EntitlementManager().is_unlocked:
            self.failed_job.emit(
                "Trial expired or not licensed. Activate a licence key to continue."
            )
            return

        try:
            self._connector.validate_backend()
        except ConnectorError as exc:
            self.failed_job.emit(str(exc))
            return

        try:
            summary: RunSummary = self._connector.run(
                self._job, self._pause_event, self._cancel_event
            )
            self.finished_job.emit(summary)
        except ConnectorError as exc:
            self.failed_job.emit(str(exc))
        except Exception as exc:  # defensive: never let the thread die silently
            self.failed_job.emit(f"Unexpected error: {exc}")

    # ------------------------------------------------------------------ #
    # Callbacks -> Qt signals
    # ------------------------------------------------------------------ #
    def _build_callbacks(self) -> Callbacks:
        return Callbacks(
            on_stage=self.stage.emit,
            on_status=self.status.emit,
            on_progress=self.progress.emit,
            on_log=self.log_line.emit,
            on_image_failed=self.image_failed.emit,
        )
