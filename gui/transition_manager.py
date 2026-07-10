from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QObject,
    QPoint,
    QRect,
)
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import QLabel, QWidget


def _reduced_motion() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in (
        "",
        "0",
        "false",
    )


class TransitionManager(QObject):
    _NAV_DURATION_MS = 260

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._current_group = None

    def set_depth_layers(self, bg: QWidget, ambient: QWidget) -> None:
        pass

    def cinematic_transition(
        self,
        outgoing: QWidget,
        incoming: QWidget,
        direction: str = "left",
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        if _reduced_motion():
            if on_finished:
                on_finished()
            return

        stack = outgoing.parent()
        if stack is None:
            if on_finished:
                on_finished()
            return

        stack_rect = stack.rect()

        screenshot = QPixmap(stack_rect.size())
        outgoing.render(screenshot, QPoint(), QRegion())

        overlay = QLabel(stack)
        overlay.setPixmap(screenshot)
        overlay.setGeometry(QRect(QPoint(0, 0), stack_rect.size()))
        overlay.show()
        overlay.raise_()

        if on_finished:
            on_finished()

        end_x = -stack_rect.width() if direction == "left" else stack_rect.width()
        slide = QPropertyAnimation(overlay, b"pos")
        slide.setDuration(self._NAV_DURATION_MS)
        slide.setStartValue(QPoint(0, 0))
        slide.setEndValue(QPoint(end_x, 0))
        slide.setEasingCurve(QEasingCurve.OutCubic)

        def _cleanup() -> None:
            overlay.deleteLater()

        slide.finished.connect(_cleanup)
        self._current_group = slide
        slide.start(QAbstractAnimation.DeleteWhenStopped)
