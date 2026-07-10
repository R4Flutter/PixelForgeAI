from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Sequence

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QPointF, QRectF, Property,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap,
)
from PySide6.QtWidgets import QWidget


_COLOR_BG = QColor("#09090B")
_COLOR_SURFACE = QColor("#12141C")
_COLOR_BORDER = QColor("#1E2230")
_COLOR_ACTIVE = QColor("#7C5CFF")
_COLOR_TEXT_PRIMARY = QColor("#F4F5FB")
_COLOR_TEXT_MUTED = QColor("#6B7186")
_COLOR_TEXT_SECONDARY = QColor("#8A90A6")

_DOT_SIZE = 6
_DOT_GAP = 8
_DOT_ACTIVE_SIZE = 8


class CoverFlowCarousel(QWidget):
    current_index_changed = Signal(int)
    images_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._paths: List[str] = []
        self._pixmaps: Dict[int, QPixmap] = {}
        self._current: float = 0.0
        self._target: int = 0
        self._animating: bool = False
        self._pulse: float = 0.0

        self._active_rect: QRectF = QRectF()
        self._remove_rect: QRectF = QRectF()
        self._remove_opacity: float = 0.0
        self._remove_hovered: bool = False
        self._mouse_over_active: bool = False

        self.setMinimumHeight(260)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._anim = QPropertyAnimation(self, b"current", self)
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        self._remove_fade_anim = QPropertyAnimation(self, b"remove_opacity", self)
        self._remove_fade_anim.setDuration(180)
        self._remove_fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        if not _reduced():
            self._pulse_timer = QTimer(self)
            self._pulse_timer.setInterval(40)
            self._pulse_timer.timeout.connect(self._pulse_tick)
            self._pulse_timer.start()

    def _pulse_tick(self) -> None:
        self._pulse += 0.04
        if self._pulse > math.pi * 2:
            self._pulse -= math.pi * 2
        self.update()

    # ---- property for animation ---- #
    def _get_current(self) -> float:
        return self._current

    def _set_current(self, v: float) -> None:
        self._current = v
        self.update()

    current = Property(float, _get_current, _set_current)

    # ---- remove fade property ---- #
    def _get_remove_opacity(self) -> float:
        return self._remove_opacity

    def _set_remove_opacity(self, v: float) -> None:
        self._remove_opacity = v
        self.update()

    remove_opacity = Property(float, _get_remove_opacity, _set_remove_opacity)

    # ---- public API ---- #
    def set_paths(self, paths: Sequence[str]) -> None:
        self._paths = list(paths)
        self._pixmaps.clear()
        self._current = 0.0
        self._target = 0
        self._anim.stop()
        self._animating = False
        self.update()

    def add_paths(self, paths: Sequence[str]) -> None:
        existing = set(self._paths)
        added = False
        for p in paths:
            if p not in existing:
                self._paths.append(p)
                existing.add(p)
                added = True
        if added:
            self.update()

    def get_paths(self) -> List[str]:
        return list(self._paths)

    def clear(self) -> None:
        self._paths.clear()
        self._pixmaps.clear()
        self._current = 0.0
        self._target = 0
        self._anim.stop()
        self._animating = False
        self.update()

    def current_index(self) -> int:
        return round(self._current)

    def set_current_index(self, idx: int) -> None:
        idx = max(0, min(idx, len(self._paths) - 1))
        if idx == round(self._current):
            return
        self._go_to(idx)

    def select_next(self) -> None:
        if self._paths:
            self._go_to(min(round(self._current) + 1, len(self._paths) - 1))

    def select_previous(self) -> None:
        if self._paths:
            self._go_to(max(round(self._current) - 1, 0))

    # ---- internal navigation ---- #
    def _go_to(self, target: int) -> None:
        if not self._paths or target == round(self._current):
            return
        target = max(0, min(target, len(self._paths) - 1))
        self._target = target
        self._anim.stop()
        self._anim.setStartValue(self._current)
        self._anim.setEndValue(float(target))
        self._anim.finished.connect(self._on_anim_finished)
        self._anim.start()
        self._animating = True

    def _on_anim_finished(self) -> None:
        self._current = float(self._target)
        self._animating = False
        self.current_index_changed.emit(self._target)
        self.update()

    # ---- pixmap cache ---- #
    def _pixmap(self, idx: int) -> Optional[QPixmap]:
        if idx < 0 or idx >= len(self._paths):
            return None
        if idx not in self._pixmaps:
            pm = QPixmap(self._paths[idx])
            if not pm.isNull():
                self._pixmaps[idx] = pm
        return self._pixmaps.get(idx)

    # ---- image removal ---- #
    def remove_image(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._paths):
            return
        self._paths.pop(idx)
        self._pixmaps.pop(idx, None)
        self._active_rect = QRectF()
        self._remove_rect = QRectF()

        ci = round(self._current)
        if idx < ci:
            self._current = max(0.0, self._current - 1.0)
        elif idx == ci:
            self._current = max(0.0, min(float(ci), len(self._paths) - 1.0))

        self._target = round(self._current)
        self._anim.stop()
        self._animating = False
        self.images_changed.emit()
        self.current_index_changed.emit(round(self._current))
        self._mouse_over_active = False
        self._remove_hovered = False
        self._remove_opacity = 0.0
        self._remove_fade_anim.stop()
        self.update()

    # ---- user interaction ---- #
    def mousePressEvent(self, event) -> None:
        if not self._paths:
            return

        click_pos = QPointF(
            event.position().x() if hasattr(event, 'position') else event.x(),
            event.position().y() if hasattr(event, 'position') else event.y(),
        )

        if self._remove_opacity > 0.3 and self._remove_rect.contains(click_pos):
            self.remove_image(round(self._current))
            return

        w = self.width()
        h = self.height()
        base_h = round(h * 0.55)
        spacing = base_h * 0.65
        cx = w / 2
        delta = click_pos.x() - cx
        nearest = round(self._current + delta / spacing)
        nearest = max(0, min(nearest, len(self._paths) - 1))

        if nearest != round(self._current) and nearest != self._target:
            self._go_to(nearest)

    def mouseMoveEvent(self, event) -> None:
        if not self._paths:
            return
        mx = event.position().x() if hasattr(event, 'position') else event.x()
        my = event.position().y() if hasattr(event, 'position') else event.y()
        mp = QPointF(mx, my)

        over_active = self._active_rect.contains(mp) if self._active_rect.isValid() else False
        over_remove = self._remove_rect.contains(mp) if self._remove_rect.isValid() else False

        if over_remove != self._remove_hovered:
            self._remove_hovered = over_remove
            self.update()

        if over_active != self._mouse_over_active:
            self._mouse_over_active = over_active
            self._remove_fade_anim.stop()
            self._remove_fade_anim.setStartValue(self._remove_opacity)
            self._remove_fade_anim.setEndValue(1.0 if over_active else 0.0)
            self._remove_fade_anim.start()

        if over_remove and self._remove_opacity > 0.3:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._mouse_over_active = False
        self._remove_hovered = False
        self._remove_fade_anim.stop()
        self._remove_fade_anim.setStartValue(self._remove_opacity)
        self._remove_fade_anim.setEndValue(0.0)
        self._remove_fade_anim.start()
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta < 0:
            self.select_next()
        else:
            self.select_previous()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Left:
            self.select_previous()
        elif event.key() == Qt.Key_Right:
            self.select_next()
        super().keyPressEvent(event)

    # ---- paint ---- #
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        count = len(self._paths)

        if count == 0:
            p.setPen(QColor(_COLOR_TEXT_MUTED))
            f = QFont()
            f.setPointSize(11)
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No images selected")
            p.end()
            return

        cx = w / 2
        cy = h / 2
        base_h = round(h * 0.55)
        spacing = base_h * 0.65
        visible = 3

        def _scale_at(pos: float) -> float:
            t = abs(pos)
            if t < 1.0:
                return 1.3 - 0.3 * t * t
            return 1.0 / (1.0 + 0.6 * (t - 1.0) * (t - 1.0))

        def _opacity_at(pos: float) -> float:
            t = abs(pos) / visible
            return max(0.15, 1.0 - t * t * 0.6)

        drawn: List[tuple[int, float]] = []

        for i in range(count):
            pos = i - self._current
            if abs(pos) > visible + 0.5:
                continue
            drawn.append((i, pos))

        drawn.sort(key=lambda x: -abs(x[1]))

        for idx, pos in drawn:
            pm = self._pixmap(idx)
            if pm is None:
                continue

            scale = _scale_at(pos)
            opacity = _opacity_at(pos)
            img_h = round(base_h * scale)
            aspect = pm.width() / pm.height()
            img_w = round(img_h * aspect)

            img_x = round(cx + pos * spacing - img_w / 2)
            img_y = round(cy - img_h / 2 - 6 * math.sin(abs(pos) * 0.8))

            rect = QRectF(img_x, img_y, img_w, img_h)

            if rect.right() < -50 or rect.left() > w + 50:
                continue

            p.save()
            p.setOpacity(opacity)

            shadow = QPainterPath()
            shadow.addRoundedRect(rect.adjusted(0, 0, 0, 0), 8, 8)
            for si in range(3, 0, -1):
                soff = si * 2
                sr = QRectF(
                    rect.x() + soff, rect.y() + soff + 4,
                    rect.width(), rect.height(),
                )
                sa = QColor(0, 0, 0, int(12 / si))
                p.setBrush(sa)
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(sr, 10, 10)

            clip = QPainterPath()
            clip.addRoundedRect(rect, 8, 8)
            p.setClipPath(clip)

            scaled = pm.scaled(
                round(img_w), round(img_h),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            sx = round(img_x + (img_w - scaled.width()) / 2)
            sy = round(img_y + (img_h - scaled.height()) / 2)
            p.drawPixmap(sx, sy, scaled)
            p.setClipping(False)

            if abs(pos) < 0.5:
                self._active_rect = rect

                glow = QPen(QColor(_COLOR_ACTIVE), 2)
                glow.setCosmetic(True)
                p.setBrush(Qt.NoBrush)
                p.setPen(glow)
                p.drawRoundedRect(rect, 8, 8)

                glow_inner = QRectF(rect.x() + 2, rect.y() + 2,
                                    rect.width() - 4, rect.height() - 4)
                g = QLinearGradient(glow_inner.topLeft(), glow_inner.bottomRight())
                g.setColorAt(0.0, QColor(124, 92, 255, 30))
                g.setColorAt(0.5, QColor(124, 92, 255, 10))
                g.setColorAt(1.0, QColor(124, 92, 255, 0))
                p.setBrush(QBrush(g))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(glow_inner, 6, 6)

            p.restore()

        p.setOpacity(1.0)

        # ---- remove overlay bar ---- #
        if self._remove_opacity > 0.01 and self._active_rect.isValid():
            p.save()

            bar_h = 34
            bar_margin = 4
            bar_rect = QRectF(
                self._active_rect.x() + bar_margin,
                self._active_rect.y() + bar_margin,
                self._active_rect.width() - bar_margin * 2,
                bar_h,
            )
            self._remove_rect = bar_rect

            clip = QPainterPath()
            clip.addRoundedRect(self._active_rect, 8, 8)
            p.setClipPath(clip)

            p.setOpacity(self._remove_opacity)

            if self._remove_hovered:
                bg_color = QColor("#DC2626")
            else:
                bg_color = QColor(0, 0, 0, 180)
            p.setBrush(bg_color)
            p.setPen(Qt.NoPen)
            p.drawRect(bar_rect)

            p.setPen(QPen(QColor(255, 255, 255, 30), 1))
            p.drawLine(
                QPointF(bar_rect.left(), bar_rect.bottom()),
                QPointF(bar_rect.right(), bar_rect.bottom()),
            )

            tf = QFont()
            tf.setPointSize(10)
            tf.setWeight(QFont.DemiBold)
            p.setFont(tf)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(bar_rect, Qt.AlignCenter, "  \u2715  Remove")

            p.restore()

        # ---- dots ---- #
        dot_y = h - 28
        total_dots = min(count, 9)
        if count > 1:
            start_idx = max(0, min(
                round(self._current) - total_dots // 2,
                count - total_dots,
            ))
            dots_w = total_dots * (_DOT_GAP + _DOT_SIZE) - _DOT_GAP
            dots_x = (w - dots_w) / 2

            for di in range(total_dots):
                idx = start_idx + di
                is_active = idx == round(self._current)
                ds = _DOT_ACTIVE_SIZE if is_active else _DOT_SIZE
                dy = dot_y + (_DOT_ACTIVE_SIZE - ds) / 2
                dx = dots_x + di * (_DOT_GAP + _DOT_SIZE) + (_DOT_ACTIVE_SIZE - ds) / 2

                if is_active:
                    pulse = 0.85 + 0.15 * math.sin(self._pulse)
                    c = QColor(_COLOR_ACTIVE)
                    c.setAlpha(int(255 * pulse))
                    p.setBrush(c)
                else:
                    p.setBrush(QColor("#2B3042"))

                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(dx + ds / 2, dy + ds / 2), ds / 2, ds / 2)

        # ---- position label ---- #
        pos_str = f"{round(self._current) + 1} / {count}"
        f = QFont()
        f.setPointSize(9)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        p.setPen(QColor(_COLOR_TEXT_SECONDARY))
        p.drawText(QRectF(0, dot_y - 18, w, 16), Qt.AlignCenter, pos_str)

        p.end()


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")
