from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from backend.entitlement import EntitlementManager, EntitlementState
from backend.job import JobRequest, RunSummary, Settings
from backend.state import load_settings, save_settings
from backend.updater import APP_NAME, APP_VERSION
from backend.worker import ProcessingWorker
from commands.base import CommandDispatcher
from events.base import EventBus
from events.pipeline_events import (
    PipelineCompletedEvent,
    PipelineStartedEvent,
)
from dependency import Dependency
from gui.about import AboutPage
from gui.home import HomePage
from gui.processing import ProcessingPage
from gui.results import ResultsPage
from gui.settings_page import SettingsPage
from gui.sidebar import Sidebar
from gui.trial_expired import TrialExpiredDialog
from gui.transition_manager import TransitionManager
from plogging.logger import get_logger

log = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, di: Dependency) -> None:
        super().__init__()
        self.setObjectName("AppRoot")
        self.setWindowTitle(f"{APP_NAME} â€” {APP_VERSION}")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self._di = di
        self._event_bus: EventBus = di.event_bus
        self._dispatcher: CommandDispatcher = di.dispatcher

        self._settings: Settings = load_settings()
        self._worker: Optional[ProcessingWorker] = None
        self._entitlement = EntitlementManager()
        self._pending_paths: list = []
        self._last_output: str = ""
        self._transition = TransitionManager(self)
        self._last_nav_idx = 0

        central = QWidget()
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.on_navigate(self._navigate)
        lay.addWidget(self._sidebar)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._stack = QStackedWidget()
        self._home = HomePage()
        self._processing = ProcessingPage()
        self._results = ResultsPage(self._event_bus)
        self._settings_page = SettingsPage(self._entitlement)
        self._about = AboutPage()

        self._transition.set_depth_layers(self._home._bg, self._home._glow)

        for w in (self._home, self._processing, self._results,
                  self._settings_page, self._about):
            self._stack.addWidget(w)
        body.addWidget(self._stack, 1)

        foot = QFrame()
        foot.setObjectName("Sidebar")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(20, 8, 20, 8)
        self._foot_left = QLabel(f"v{APP_VERSION}")
        self._foot_left.setObjectName("FooterCopy")
        self._foot_right = QLabel("Free tier")
        self._foot_right.setObjectName("FooterCopy")
        fl.addWidget(self._foot_left)
        fl.addStretch(1)
        fl.addWidget(self._foot_right)
        body.addWidget(foot)

        lay.addLayout(body, 1)

        self._wire_pages()
        self._wire_event_bus()
        self._settings_page.set_settings(self._settings)
        self._navigate(0)
        self._refresh_footer()
        if self._entitlement.evaluate().state is EntitlementState.LOCKED:
            QTimer.singleShot(0, self._show_trial_expired)

    def _wire_event_bus(self) -> None:
        self._event_bus.on(PipelineCompletedEvent, self._on_pipeline_completed)
        self._event_bus.on(PipelineStartedEvent, self._on_pipeline_started)

    def _on_pipeline_completed(self, event: PipelineCompletedEvent) -> None:
        from models.pipeline_result import PipelineResult
        result = PipelineResult(
            total=event.statistics.total_images,
            succeeded=event.statistics.succeeded,
            failed=event.statistics.failed,
            elapsed_seconds=event.statistics.elapsed_seconds,
            output_folder=event.output_folder,
        )
        self._results.show_result(result, event.output_folder)
        self._navigate(2)
        self._refresh_footer()

    def _on_pipeline_started(self, event: PipelineStartedEvent) -> None:
        self._processing.begin(event.total_images)
        self._navigate(1)

    def _wire_pages(self) -> None:
        self._home.start_requested.connect(self._start_job)
        self._processing.pause_requested.connect(self._pause)
        self._processing.resume_requested.connect(self._resume)
        self._processing.cancel_requested.connect(self._cancel)
        self._results.process_again.connect(self._process_again)
        self._settings_page.settings_changed.connect(self._on_settings_changed)

    def _navigate(self, idx: int) -> None:
        if self._is_running() and idx != 1:
            return
        outgoing = self._stack.currentWidget()
        incoming = self._stack.widget(idx)
        if outgoing is incoming:
            self._sidebar.set_active(idx)
            return

        if outgoing is None:
            self._stack.setCurrentIndex(idx)
            self._sidebar.set_active(idx)
            self._last_nav_idx = idx
            return

        direction = "left" if idx > self._last_nav_idx else "right"

        def _set_index() -> None:
            self._stack.setCurrentIndex(idx)
            self._sidebar.set_active(idx)

        self._transition.cinematic_transition(
            outgoing, incoming, direction=direction, on_finished=_set_index
        )
        self._last_nav_idx = idx

    def _on_settings_changed(self) -> None:
        self._settings = self._settings_page.get_settings()
        save_settings(self._settings)
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        e = self._entitlement.evaluate()
        if e.state is EntitlementState.LICENSED:
            self._foot_right.setText("Pro")
        elif e.state is EntitlementState.TRIAL:
            self._foot_right.setText(f"Trial Â· {e.trial_days_remaining}d left")
        else:
            self._foot_right.setText("Trial expired")
        self._foot_left.setText(f"v{APP_VERSION}")

    def _start_job(self, paths: list) -> None:
        try:
            if self._is_running() or not paths:
                return
            if not self._entitlement.is_unlocked:
                self._pending_paths = list(paths)
                self._show_trial_expired()
                return
            self._on_settings_changed()

            job = JobRequest.from_images(paths, self._settings)
            total = len(job.resolve_image_paths())
            if total == 0:
                self._processing.on_failed("No valid images were selected.")
                self._navigate(1)
                return

            self._worker = ProcessingWorker(job)
            w = self._worker
            w.stage.connect(self._processing.on_stage)
            w.status.connect(self._processing.on_status)
            w.progress.connect(self._processing.on_progress)
            w.log_line.connect(self._processing.on_log)
            w.image_failed.connect(self._processing.on_image_failed)
            w.failed_job.connect(self._on_failed_job)
            w.finished_job.connect(self._on_finished_job)
            w.finished.connect(w.deleteLater)

            self._last_output = self._resolved_output(self._settings)
            self._processing.begin(total, paths=list(job.sources))
            self._navigate(1)
            self._set_running(True)
            w.start()
        except Exception as exc:
            log.error("_start_job failed: %s", exc)

    def _pause(self) -> None:
        if self._worker is not None:
            self._worker.pause()

    def _resume(self) -> None:
        if self._worker is not None:
            self._worker.resume()

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    def _show_trial_expired(self) -> None:
        dlg = TrialExpiredDialog(self._entitlement, self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_footer()
            paths = self._pending_paths
            self._pending_paths = []
            if paths:
                self._processing.reset()
                self._start_job(paths)
        else:
            self._refresh_footer()
            self._pending_paths = []

    def _on_failed_job(self, message: str) -> None:
        self._processing.on_failed(message)
        self._set_running(False)
        self._worker = None

    def _on_finished_job(self, summary: RunSummary) -> None:
        self._processing.on_summary(summary)
        self._set_running(False)
        self._worker = None
        from models.pipeline_result import PipelineResult
        result = PipelineResult(
            total=summary.total,
            succeeded=summary.succeeded,
            failed=summary.failed,
            elapsed_seconds=summary.elapsed_seconds,
            failed_files=list(summary.failed_files),
            cancelled=summary.cancelled,
            output_folder=self._last_output,
        )
        self._results.show_result(result, self._last_output)
        self._navigate(2)
        self._refresh_footer()

    def _process_again(self) -> None:
        self._processing.reset()
        self._navigate(0)

    def _is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _set_running(self, running: bool) -> None:
        btn = self._home._process
        if running:
            btn.setEnabled(False)
        else:
            btn.setEnabled(btn._count > 0)
        btn.update()

    @staticmethod
    def _resolved_output(settings: Settings) -> str:
        folder = (settings.output_folder or "").strip()
        if not folder or folder == ".":
            from backend.state import paths
            return str((paths().root / "output" / "final").resolve())
        return folder

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(4000)
        super().closeEvent(event)
