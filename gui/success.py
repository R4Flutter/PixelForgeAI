"""
success.py
----------
Completion summary shown after a run.

Surfaces the RunSummary (total / succeeded / failed / elapsed), lists any
files that failed, and offers "Open output folder" + "Process again". The
"open folder" action is cross-platform via a best-effort launcher.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.job import RunSummary
from components.buttons import PrimaryButton, SecondaryButton
from components.cards import SectionCard, StatCard
from components.icons import icon, pixmap


class SuccessPage(QWidget):
    """Run-complete page driven by a RunSummary."""

    process_again = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")
        self._output_folder = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 32, 40, 32)
        root.setSpacing(20)

        head = QHBoxLayout()
        head.setSpacing(16)
        badge = QLabel()
        badge.setPixmap(pixmap("success", 44, color="#22C55E", accent="#22C55E"))
        head.addWidget(badge, alignment=Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self._title = QLabel("All done!")
        self._title.setObjectName("PageTitle")
        self._title.setStyleSheet("color:#22C55E;")
        self._subtitle = QLabel("Your images are ready.")
        self._subtitle.setObjectName("PageSubtitle")
        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)
        head.addLayout(titles)
        head.addStretch(1)
        root.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self._s_total = StatCard("0", "Total images")
        self._s_ok = StatCard("0", "Succeeded")
        self._s_fail = StatCard("0", "Failed")
        self._s_time = StatCard("00:00", "Elapsed")
        for s in (self._s_total, self._s_ok, self._s_fail, self._s_time):
            stats.addWidget(s, 1)
        root.addLayout(stats)

        self._failed_card = SectionCard("Failed files")
        self._failed_list = QListWidget()
        self._failed_list.setObjectName("LogConsole")
        self._failed_list.setWordWrap(True)
        self._failed_list.setFixedHeight(140)
        self._failed_card.addWidget(self._failed_list)
        root.addWidget(self._failed_card)

        root.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._btn_open = SecondaryButton("  Open output folder")
        self._btn_open.setIcon(icon("folder_open", 18))
        self._btn_open.clicked.connect(self._open_folder)
        self._btn_again = PrimaryButton("  Process again")
        self._btn_again.setIcon(icon("refresh", 18, color="#FFFFFF"))
        self._btn_again.clicked.connect(self.process_again.emit)
        actions.addStretch(1)
        actions.addWidget(self._btn_open)
        actions.addWidget(self._btn_again)
        root.addLayout(actions)

    # ------------------------------------------------------------------ #
    def show_summary(self, summary: RunSummary, output_folder: str) -> None:
        self._output_folder = output_folder
        self._s_total.set_value(str(summary.total))
        self._s_ok.set_value(str(summary.succeeded))
        self._s_fail.set_value(str(summary.failed))
        m, s = divmod(int(summary.elapsed_seconds), 60)
        self._s_time.set_value(f"{m:02d}:{s:02d}")

        if summary.cancelled:
            self._title.setText("Run cancelled")
            self._title.setStyleSheet("color:#FBBF24;")
            self._subtitle.setText("Processing was cancelled partway through.")
        elif summary.all_succeeded:
            self._title.setText("All done!")
            self._title.setStyleSheet("color:#22C55E;")
            self._subtitle.setText("Every image processed successfully.")
        else:
            self._title.setText("Completed with errors")
            self._title.setStyleSheet("color:#F87171;")
            self._subtitle.setText("Some images could not be processed.")

        self._failed_list.clear()
        self._failed_card.setVisible(bool(summary.failed_files))
        for f in summary.failed_files:
            QListWidgetItem(f, self._failed_list)

    # ------------------------------------------------------------------ #
    def _open_folder(self) -> None:
        if not self._output_folder:
            return
        _open_path_in_file_manager(self._output_folder)


def _open_path_in_file_manager(path: str) -> None:
    """Best-effort, cross-platform "open folder" that never raises."""
    try:
        if sys.platform == "win32":
            import os
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", path])
            else:
                subprocess.Popen(["nautilus", path])
    except OSError:
        pass
