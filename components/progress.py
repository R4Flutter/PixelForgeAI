"""
progress.py
-----------
Progress widgets synced to themes/dark.qss.

  ProgressBar      - determinate QProgressBar ("Progress Page").
  StepIndicator    - horizontal dots that light up as each pipeline stage
                     fires, driven by the friendly stage labels the worker
                     emits (the same strings ``backend.log_bridge.StageMapper``
                     produces).
  LogConsole       - read-only colorized log window ("Logs Window").
  Throbber         - indeterminate busy indicator.

No backend imports; the stage strings are passed in by the window.
"""
from __future__ import annotations

import html
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QTextEdit,
)

# Stage order shown by the StepIndicator. These friendly labels match the ones
# StageMapper (backend.log_bridge) emits and the worker forwards.
STAGE_LOAD = "Loading AI model…"
STAGE_REMOVE = "Removing Background…"
STAGE_UPSCALE = "Upscaling…"
STAGE_OPTIMIZE = "Optimizing Design…"
STAGE_RESIZE = "Resizing…"
STAGE_SAVE = "Saving…"
STAGE_DONE = "Completed"

_STEPS: tuple[str, ...] = ("Load", "Remove BG", "Upscale", "Resize", "Save")

# Map a friendly stage label -> active step index (0-based across _STEPS).
_STAGE_INDEX: Dict[str, int] = {
    STAGE_LOAD: 0,
    STAGE_REMOVE: 1,
    STAGE_UPSCALE: 2,
    STAGE_OPTIMIZE: 2,
    STAGE_RESIZE: 3,
    STAGE_SAVE: 4,
}


class ProgressBar(QProgressBar):
    """Determinate progress bar with percentage text."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressBar")
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(True)
        self.setFormat("%p%")

    def set_value(self, done: int, total: int) -> None:
        if total <= 0:
            self.setValue(0)
            return
        self.setRange(0, total)
        self.setValue(done)

    def reset(self) -> None:
        self.setRange(0, 100)
        self.setValue(0)


class Throbber(QProgressBar):
    """Indeterminate busy indicator (Qt animates min==max==0)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressBar")
        self.setRange(0, 0)
        self.setTextVisible(False)
        self.setFixedHeight(8)
        self.setVisible(False)

    def start(self) -> None:
        self.setRange(0, 0)
        self.setVisible(True)

    def stop(self) -> None:
        self.setRange(0, 100)
        self.setVisible(False)


class StepIndicator(QFrame):
    """Row of step dots + labels that light up as the pipeline advances."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dots: List[QFrame] = []
        self._labels: List[QLabel] = []
        self._completed = False

        for i, name in enumerate(_STEPS):
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(8)
            column.setAlignment(Qt.AlignCenter)

            dot = QFrame()
            dot.setFixedSize(18, 18)
            dot.setObjectName("StepDot")
            self._dots.append(dot)

            label = QLabel(name)
            label.setObjectName("StatusLabel")
            self._labels.append(label)

            column.addWidget(dot, alignment=Qt.AlignCenter)
            column.addWidget(label, alignment=Qt.AlignCenter)
            layout.addLayout(column)
            if i < len(_STEPS) - 1:
                spacer = QFrame()
                spacer.setFixedHeight(2)
                spacer.setMinimumWidth(40)
                layout.addWidget(spacer, 1)

        self.reset()

    def reset(self) -> None:
        self._completed = False
        for dot, label in zip(self._dots, self._labels):
            dot.setObjectName("StepDot")
            label.setStyleSheet("color: #6B7186;")
            self._polish(dot)

    def set_stage(self, stage: str) -> None:
        """Advance the dots to ``stage`` (a friendly label from StageMapper)."""
        if stage == STAGE_DONE:
            self._mark_completed()
            return
        active = _STAGE_INDEX.get(stage)
        if active is None:
            return
        self._completed = False
        for i, (dot, label) in enumerate(zip(self._dots, self._labels)):
            if i < active:
                object_name, color = "StepDotDone", "#6B7186"
            elif i == active:
                object_name, color = "StepDotActive", "#E6E8F0"
            else:
                object_name, color = "StepDot", "#6B7186"
            dot.setObjectName(object_name)
            label.setStyleSheet(f"color: {color};")
            self._polish(dot)

    def _mark_completed(self) -> None:
        self._completed = True
        for dot, label in zip(self._dots, self._labels):
            dot.setObjectName("StepDotDone")
            label.setStyleSheet("color: #22C55E;")
            self._polish(dot)

    @property
    def completed(self) -> bool:
        return self._completed

    @staticmethod
    def _polish(widget: QFrame) -> None:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)


class LogConsole(QTextEdit):
    """Read-only, colorized, auto-scrolling log viewer."""

    _LEVEL_COLORS: Dict[str, str] = {
        "DEBUG": "#6B7186",
        "INFO": "#B4BBDA",
        "WARNING": "#FBBF24",
        "ERROR": "#F87171",
        "CRITICAL": "#F87171",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LogConsole")
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self._max_blocks = 4000

    def append_line(self, level: str, logger: str, message: str) -> None:
        color = self._LEVEL_COLORS.get(level.upper(), "#B4BBDA")
        safe_msg = html.escape(str(message))
        safe_logger = html.escape(str(logger))
        line = (
            f'<span style="color:#6B7186;">[{logger}]</span> '
            f'<span style="color:{color};">{safe_msg}</span>'
        )
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.document().isEmpty():
            cursor.insertText("\n", QTextCharFormat())
        cursor.insertHtml(line)
        self.setTextCursor(cursor)
        self._trim()
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _trim(self) -> None:
        doc = self.document()
        block_count = doc.blockCount()
        if block_count <= self._max_blocks:
            return
        cursor = QTextCursor(doc.firstBlock())
        for _ in range(block_count - self._max_blocks):
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            if not cursor.movePosition(QTextCursor.NextBlock,
                                      QTextCursor.KeepAnchor):
                break
        cursor.removeSelectedText()

    def clear_log(self) -> None:
        self.clear()
