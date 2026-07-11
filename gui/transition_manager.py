from __future__ import annotations

import math
import os
from typing import Callable, List, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QPauseAnimation,
    QTimer,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Property,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPixmap,
    Qt,
)
from PySide6.QtWidgets import QLabel, QWidget


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


class _TransitionOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._darkness = 0.0
        self._fly_progress = 0.0
        self._fly_pm: Optional[QPixmap] = None
        self._src_rect = QRectF()
        self._dst_rect = QRectF()
        self._zoom = 1.0
        self._wipe_progress = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_source_rect(self, r: QRectF) -> None:
        self._src_rect = r

    def set_dest_rect(self, r: QRectF) -> None:
        self._dst_rect = r

    def set_fly_pixmap(self, pm: QPixmap) -> None:
        self._fly_pm = pm

    def _get_darkness(self) -> float:
        return self._darkness

    def _set_darkness(self, v: float) -> None:
        self._darkness = v
        self.update()

    def _get_fly(self) -> float:
        return self._fly_progress

    def _set_fly(self, v: float) -> None:
        self._fly_progress = v
        self.update()

    def _get_zoom(self) -> float:
        return self._zoom

    def _set_zoom(self, v: float) -> None:
        self._zoom = v
        self.update()

    def _get_wipe(self) -> float:
        return self._wipe_progress

    def _set_wipe(self, v: float) -> None:
        self._wipe_progress = v
        self.update()

    darkness = Property(float, _get_darkness, _set_darkness)
    fly_progress = Property(float, _get_fly, _set_fly)
    zoom = Property(float, _get_zoom, _set_zoom)
    wipe_progress = Property(float, _get_wipe, _set_wipe)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        d = self._darkness
        if d > 0:
            p.fillRect(0, 0, w, h, QColor(11, 12, 16, min(230, int(230 * d))))

        fp = self._fly_progress
        zm = self._zoom
        wp = self._wipe_progress

        if self._fly_pm and fp > 0:
            sx, sy = self._src_rect.x(), self._src_rect.y()
            sw, sh = self._src_rect.width(), self._src_rect.height()
            dx, dy = self._dst_rect.x(), self._dst_rect.y()
            dw, dh = self._dst_rect.width(), self._dst_rect.height()

            e = 1.0 - (1.0 - fp) ** 2
            cx = sx + (dx - sx) * e
            cy = sy + (dy - sy) * e
            cw = sw + (dw - sw) * e
            ch = sh + (dh - sh) * e

            p.save()
            p.translate(cx + cw / 2, cy + ch / 2)
            sc = zm * (1.0 - 0.3 * (1.0 - fp))
            p.scale(sc, sc)
            p.translate(-cw / 2, -ch / 2)

            img = self._fly_pm.scaled(
                int(cw), int(ch), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            ix = (cw - img.width()) / 2
            iy = (ch - img.height()) / 2
            p.drawPixmap(int(ix), int(iy), img)
            p.restore()

            if fp >= 1.0 and wp > 0.01:
                rad = math.sqrt(w * w + h * h) * 0.76 * wp
                if rad > 1:
                    gradient = QPainterPath()
                    gradient.addRect(0, 0, w, h)
                    reveal = QPainterPath()
                    reveal.addEllipse(QPointF(w / 2, h / 2), rad, rad)
                    mask = gradient.subtracted(reveal)
                    p.fillPath(mask, QColor(11, 12, 16, 230))

        p.end()


class TransitionManager(QObject):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._active_overlay: Optional[QWidget] = None

    def set_depth_layers(self, bg: QWidget, ambient: QWidget) -> None:
        pass

    def cancel(self) -> None:
        if self._active_overlay is not None:
            self._active_overlay.deleteLater()
            self._active_overlay = None

    def _find_carousel_center(self, widget: QWidget) -> QRectF:
        try:
            grid = getattr(widget, "_badge_grid", None)
            if grid is None:
                return QRectF()
            g = grid.geometry()
            cx = g.x() + g.width() / 2
            cy = g.y() + g.height() / 2
            size = min(g.width(), g.height()) * 0.3
            return QRectF(cx - size / 2, cy - size / 2, size, size)
        except Exception:
            return QRectF()

    def cinematic_transition(
        self,
        outgoing: QWidget,
        incoming: QWidget,
        direction: str = "left",
        on_finished: Optional[Callable[[], None]] = None,
        shared_image_path: str = "",
    ) -> None:
        if _reduced():
            if on_finished:
                on_finished()
            return

        stack = outgoing.parent()
        if stack is None:
            if on_finished:
                on_finished()
            return

        stack_rect = stack.rect()
        self.cancel()
        overlay = _TransitionOverlay(stack)
        self._active_overlay = overlay
        overlay.setGeometry(stack_rect)
        overlay.show()
        overlay.raise_()

        fly_pm: Optional[QPixmap] = None
        if shared_image_path:
            pm = QPixmap(shared_image_path)
            if not pm.isNull():
                fly_pm = pm.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        has_shared = fly_pm is not None and not fly_pm.isNull()

        if has_shared:
            src = self._find_carousel_center(outgoing)
            if src.isNull() or src.width() < 1:
                src = QRectF(
                    stack_rect.width() * 0.5 - 40,
                    stack_rect.height() * 0.45 - 40,
                    80, 80
                )
            dst = QRectF(
                stack_rect.width() * 0.6 - 100,
                stack_rect.height() * 0.35 - 60,
                200, 200
            )
            overlay.set_source_rect(src)
            overlay.set_dest_rect(dst)
            overlay.set_fly_pixmap(fly_pm)

        phase1 = QParallelAnimationGroup(self)

        dark_anim = QPropertyAnimation(overlay, b"darkness")
        dark_anim.setDuration(180)
        dark_anim.setStartValue(0.0)
        dark_anim.setEndValue(1.0)
        dark_anim.setEasingCurve(QEasingCurve.OutCubic)
        phase1.addAnimation(dark_anim)

        if has_shared:
            fly_anim = QPropertyAnimation(overlay, b"fly_progress")
            fly_anim.setDuration(400)
            fly_anim.setStartValue(0.0)
            fly_anim.setEndValue(1.0)
            fly_anim.setEasingCurve(QEasingCurve.OutCubic)
            phase1.addAnimation(fly_anim)

            zoom_anim = QPropertyAnimation(overlay, b"zoom")
            zoom_anim.setDuration(400)
            zoom_anim.setStartValue(1.0)
            zoom_anim.setEndValue(1.0)
            zoom_anim.setKeyValueAt(0.5, 1.08)
            zoom_anim.setEasingCurve(QEasingCurve.OutQuart)
            phase1.addAnimation(zoom_anim)

        def _phase1_done() -> None:
            if on_finished:
                on_finished()

            wipe_anim = QPropertyAnimation(overlay, b"wipe_progress")
            wipe_anim.setDuration(350)
            wipe_anim.setStartValue(0.0)
            wipe_anim.setEndValue(1.0)
            wipe_anim.setEasingCurve(QEasingCurve.OutCubic)

            def _wipe_done() -> None:
                if self._active_overlay is overlay:
                    self._active_overlay = None
                overlay.deleteLater()

            wipe_anim.finished.connect(_wipe_done)
            wipe_anim.start()

        phase1.finished.connect(_phase1_done)
        phase1.start(QAbstractAnimation.DeleteWhenStopped)
