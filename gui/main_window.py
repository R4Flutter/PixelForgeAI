
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.entitlement import EntitlementManager, EntitlementState
from backend.job import JobRequest, RunSummary, Settings
from backend.state import load_settings, save_settings
from backend.updater import APP_NAME, APP_VERSION
from backend.worker import ProcessingWorker
from components.buttons import NavButton
from components.icons import icon, pixmap
from gui.about import AboutPage
from gui.home import HomePage
from gui.processing import ProcessingPage
from gui.settings_page import SettingsPage
from gui.success import SuccessPage
from gui.trial_expired import TrialExpiredDialog
from gui.transition_manager import TransitionManager


_NAV = (
    ("Home", "home", 0),
    ("Processing", "image", 1),
    ("Results", "success", 2),
    ("Settings", "settings", 3),
    ("About", "info", 4),
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AppRoot")
        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

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

        lay.addWidget(self._build_sidebar())

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._stack = QStackedWidget()
        self._home = HomePage()
        self._processing = ProcessingPage()
        self._success = SuccessPage()
        self._settings_page = SettingsPage(self._entitlement)
        self._about = AboutPage()

        self._transition.set_depth_layers(self._home._bg, self._home._glow)

        for w in (self._home, self._processing, self._success,
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
        self._settings_page.set_settings(self._settings)
        self._navigate(0)
        self._refresh_footer()
        if self._entitlement.evaluate().state is EntitlementState.LOCKED:
            QTimer.singleShot(0, self._show_trial_expired)

    def _build_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(232)
        v = QVBoxLayout(bar)
        v.setContentsMargins(18, 24, 18, 18)
        v.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(pixmap("logo", 34, color="#6366F1", accent="#A5B4FC"))
        brand.addWidget(logo, alignment=Qt.AlignTop)
        bt = QVBoxLayout()
        bt.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("BrandName")
        tag = QLabel("AI IMAGE PIPELINE")
        tag.setObjectName("BrandTag")
        bt.addWidget(name)
        bt.addWidget(tag)
        brand.addLayout(bt)
        brand.addStretch(1)
        v.addLayout(brand)

        v.addSpacing(20)

        self._nav_buttons: List[NavButton] = []
        for label, icon_name, idx in _NAV:
            btn = NavButton(icon(icon_name, 18, color="#8A90A6",
                                 accent="#6366F1"), label)
            btn.clicked.connect(lambda _checked=False, i=idx: self._navigate(i))
            v.addWidget(btn)
            self._nav_buttons.append(btn)

        v.addStretch(1)
        return bar

    def _wire_pages(self) -> None:
        self._home.start_requested.connect(self._start_job)
        self._processing.pause_requested.connect(self._pause)
        self._processing.resume_requested.connect(self._resume)
        self._processing.cancel_requested.connect(self._cancel)
        self._success.process_again.connect(self._process_again)
        self._settings_page.settings_changed.connect(self._on_settings_changed)

    def _navigate(self, idx: int) -> None:
        if self._is_running() and idx != 1:
            return
        outgoing = self._stack.currentWidget()
        incoming = self._stack.widget(idx)
        if outgoing is incoming:
            return

        if outgoing is None:
            self._stack.setCurrentIndex(idx)
            for i, btn in enumerate(self._nav_buttons):
                btn.setChecked(i == idx)
            self._last_nav_idx = idx
            return

        direction = "left" if idx > self._last_nav_idx else "right"

        def _set_index() -> None:
            self._stack.setCurrentIndex(idx)
            for i, btn in enumerate(self._nav_buttons):
                btn.setChecked(i == idx)

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
            self._foot_right.setText(f"Trial · {e.trial_days_remaining}d left")
        else:
            self._foot_right.setText("Trial expired")
        self._foot_left.setText(f"v{APP_VERSION}")

    def _start_job(self, paths: list) -> None:
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
        self._processing.begin(total)
        self._navigate(1)
        self._set_running(True)
        w.start()

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

    def _on_finished_job(self, summary: RunSummary) -> None:
        self._processing.on_summary(summary)
        self._set_running(False)
        self._success.show_summary(summary, self._last_output)
        self._navigate(2)
        self._refresh_footer()
        if self._worker is not None:
            self._worker = None

    def _process_again(self) -> None:
        self._processing.reset()
        self._navigate(0)

    def _is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _set_running(self, running: bool) -> None:
        self._home._process.setEnabled(not running)
        for i, btn in enumerate(self._nav_buttons):
            if i == 1:
                continue
            btn.setEnabled(not running)

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
