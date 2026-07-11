from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRectF, QPointF, Signal, QTimer, QEvent, Property
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap,
    QEnterEvent, QMouseEvent,
)
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy, QGraphicsOpacityEffect

from design_system.tokens.colors import Colors as C
from design_system.tokens.spacing import Spacing as S
from design_system.tokens.typography import Typography as T


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


class PreviewViewer(QWidget):
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._target_path: str = ""
        self._nav_hovered = False
        self._nav_opacity = 0.0
        self._nav_fade_anim: Optional[QPropertyAnimation] = None
        self._transitioning = False
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def set_pixmap(self, path: str, fade: bool = True) -> None:
        if not path or not os.path.isfile(path):
            return
        if fade and not _reduced() and self._pixmap is not None:
            if self._transitioning:
                return
            self._transitioning = True
            self._target_path = path
            fade_out = QPropertyAnimation(self._opacity_effect, b"opacity", self)
            fade_out.setDuration(180)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setEasingCurve(QEasingCurve.OutCubic)
            fade_out.finished.connect(self._on_fade_out_done)
            fade_out.start()
        else:
            self._do_load(path)
            self._opacity_effect.setOpacity(1.0)

    def _on_fade_out_done(self) -> None:
        self._do_load(self._target_path)
        fade_in = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade_in.setDuration(180)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InCubic)
        fade_in.finished.connect(self._on_fade_in_done)
        fade_in.start()

    def _on_fade_in_done(self) -> None:
        self._transitioning = False

    def _do_load(self, path: str) -> None:
        pm = QPixmap(path)
        if not pm.isNull():
            self._pixmap = pm
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self._target_path = ""
        self.update()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._nav_hovered = True
        self._fade_nav(0.6)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._nav_hovered = False
        self._fade_nav(0.0)
        super().leaveEvent(event)

    def _fade_nav(self, target: float) -> None:
        if self._nav_fade_anim and self._nav_fade_anim.state() == QPropertyAnimation.Running:
            self._nav_fade_anim.stop()
        self._nav_fade_anim = QPropertyAnimation(self, b"nav_opacity", self)
        self._nav_fade_anim.setDuration(250)
        self._nav_fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._nav_fade_anim.setStartValue(self._nav_opacity)
        self._nav_fade_anim.setEndValue(target)
        self._nav_fade_anim.start()

    def _get_nav_op(self) -> float:
        return self._nav_opacity

    def _set_nav_op(self, v: float) -> None:
        self._nav_opacity = v
        self.update()

    nav_opacity = Property(float, _get_nav_op, _set_nav_op)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._nav_opacity > 0.01:
            w = self.width()
            h = self.height()
            mx, my = event.position().x(), event.position().y()
            btn_r = 36
            gap = 40
            center_y = h / 2

            lx = (w - gap) / 2 - btn_r
            rx = (w + gap) / 2
            ly = center_y - btn_r / 2
            ry = center_y - btn_r / 2

            if lx <= mx <= lx + btn_r and ly <= my <= ly + btn_r:
                self.prev_requested.emit()
                return
            if rx <= mx <= rx + btn_r and ry <= my <= ry + btn_r:
                self.next_requested.emit()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        p.setBrush(QColor(C.bg_card))
        p.setPen(QPen(QColor(C.border), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 14, 14)

        if self._pixmap:
            scaled = self._pixmap.scaled(w - S.xl * 2, h - S.xl * 2,
                                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
            px = (w - scaled.width()) / 2
            py = (h - scaled.height()) / 2
            p.drawPixmap(int(px), int(py), scaled)
        else:
            f = QFont(["Inter", "Segoe UI"], 14, QFont.Medium)
            p.setFont(f)
            p.setPen(QColor(C.text_muted))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No image selected")

        if self._nav_opacity > 0.01:
            btn_r = 36
            gap = 40
            center_y = h / 2
            alpha = int(180 * self._nav_opacity)

            for direction in (-1, 1):
                bx = (w - gap) / 2 - btn_r if direction == -1 else (w + gap) / 2
                by = center_y - btn_r / 2

                c = QColor(C.bg_surface)
                c.setAlpha(alpha)
                p.setBrush(c)
                p.setPen(QPen(QColor(C.border), 1))
                p.drawRoundedRect(QRectF(bx, by, btn_r, btn_r), btn_r / 2, btn_r / 2)

                p.setPen(QColor(C.text_primary))
                f_btn = QFont(["Inter", "Segoe UI"], 16, QFont.Bold)
                p.setFont(f_btn)
                arrow = "\u25C0" if direction == -1 else "\u25B6"
                p.drawText(QRectF(bx, by, btn_r, btn_r), Qt.AlignCenter, arrow)

        p.end()
