
from __future__ import annotations

import math
import os
import time
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QPointF, QRectF, Property,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from backend.job import RunSummary
from components.buttons import PrimaryButton, DangerButton
from components.icons import icon


COLOR_BG = QColor("#09090B")
COLOR_ACTIVE = QColor("#7C5CFF")
COLOR_COMPLETED = QColor("#34D399")
COLOR_WAITING = QColor("#6B7280")
COLOR_ERROR = QColor("#EF4444")
COLOR_TEXT_PRIMARY = QColor("#F4F5FB")
COLOR_TEXT_SECONDARY = QColor("#8A90A6")
COLOR_TEXT_MUTED = QColor("#6B7186")
COLOR_BORDER = QColor("#1E2230")
COLOR_SURFACE = QColor("#12141C")

STAGE_NAMES = ["Load Image", "Remove BG", "AI Upscale", "Resize", "Save"]
_STAGE_DESCRIPTIONS = [
    "Reading source image...",
    "Detecting foreground and separating subject...",
    "Restoring fine image details...",
    "Optimizing for print dimensions...",
    "Writing final image...",
]
_STAGE_LABEL_TO_INDEX = {
    "Loading AI model\u2026": 0,
    "Removing Background\u2026": 1,
    "Upscaling\u2026": 2,
    "Optimizing Design\u2026": 2,
    "Resizing\u2026": 3,
    "Saving\u2026": 4,
}
_STAGE_KEYS: tuple[str, ...] = (*_STAGE_LABEL_TO_INDEX.keys(), "Completed")

ANIM_NODE_ACTIVATE = 220
ANIM_CHECKMARK = 180
ANIM_BEAM_TRAVEL = 250
ANIM_IMAGE_TRANSITION = 350
ANIM_COMPLETION = 500


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _fmt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


class _StageLabelMap:
    def __init__(self) -> None:
        self._current: str | None = None

    def map(self, stage: str) -> str | None:
        if stage == self._current:
            return None
        self._current = stage
        return stage


class _AmbientBg(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._angle = 0.0
        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(50)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _tick(self) -> None:
        self._angle += 0.005
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), COLOR_BG)
        cx = w / 2 + math.cos(self._angle) * 40
        cy = h * 0.3 + math.sin(self._angle * 0.6) * 30
        g = QRadialGradient(cx, cy, max(w, h) * 0.55)
        g.setColorAt(0.0, QColor(124, 92, 255, 12))
        g.setColorAt(0.4, QColor(124, 92, 255, 5))
        g.setColorAt(1.0, QColor(9, 9, 11, 0))
        p.fillRect(self.rect(), QBrush(g))
        g2 = QRadialGradient(w / 2, 0, max(w, h) * 0.4)
        g2.setColorAt(0.0, QColor(124, 92, 255, 8))
        g2.setColorAt(1.0, QColor(9, 9, 11, 0))
        p.fillRect(self.rect(), QBrush(g2))
        p.end()


class _PipelineNode(QWidget):
    class State(Enum):
        WAITING = auto()
        ACTIVE = auto()
        COMPLETED = auto()
        FAILED = auto()

    RADIUS = 12

    def __init__(self, index: int, name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._index = index
        self._name = name
        self._state = _PipelineNode.State.WAITING
        self._pulse = 0.0
        self._progress = 0.0
        self._checkmark_progress = 0.0
        self._glow_opacity = 0.0
        self._shake_offset = 0.0
        self._shake_timer: QTimer | None = None
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(30)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self.setFixedHeight(self.RADIUS * 2 + 4)
        self.setMinimumWidth(150)

    @property
    def state(self) -> State:
        return self._state

    def set_state(self, state: State, animate: bool = True) -> None:
        if self._state == state:
            return
        self._state = state
        if state is _PipelineNode.State.ACTIVE:
            self._pulse = 0.0
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self._pulse = 0.0
            self._glow_opacity = 0.0

        if state is _PipelineNode.State.COMPLETED and animate and not _reduced():
            self._progress = 0.0
            self._checkmark_progress = 0.0
            anim = QPropertyAnimation(self, b"ring_progress", self)
            anim.setDuration(ANIM_CHECKMARK)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(self._start_checkmark)
            anim.start()
        elif state is _PipelineNode.State.COMPLETED and not animate:
            self._progress = 1.0
            self._checkmark_progress = 1.0

        if state is _PipelineNode.State.FAILED:
            self._start_shake()

        self.update()

    def _start_checkmark(self) -> None:
        anim = QPropertyAnimation(self, b"checkmark_progress", self)
        anim.setDuration(ANIM_CHECKMARK)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutBack)
        anim.start()

    def _start_shake(self) -> None:
        if _reduced():
            return
        self._shake_timer = QTimer(self)
        self._shake_timer.setInterval(20)
        self._shake_timer.timeout.connect(self._shake_tick)
        self._shake_timer.start()

    def _shake_tick(self) -> None:
        if self._shake_offset == 0.0:
            self._shake_offset = 0.0
        decay = getattr(self, "_shake_decay", 1.0)
        self._shake_offset = math.sin(time.time() * 120) * 3 * decay
        self._shake_decay = max(0.0, decay - 0.04)
        self.update()
        if self._shake_decay <= 0.0 and self._shake_timer:
            self._shake_offset = 0.0
            self._shake_timer.stop()

    def _pulse_tick(self) -> None:
        self._pulse += 0.025
        self._glow_opacity = 0.3 + 0.3 * math.sin(self._pulse * 2 * math.pi / 100)
        self.update()

    def _get_ring(self) -> float:
        return self._progress

    def _set_ring(self, v: float) -> None:
        self._progress = v
        self.update()

    ring_progress = Property(float, _get_ring, _set_ring)

    def _get_check(self) -> float:
        return self._checkmark_progress

    def _set_check(self, v: float) -> None:
        self._checkmark_progress = v
        self.update()

    checkmark_progress = Property(float, _get_check, _set_check)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.RADIUS
        cx = r + 6
        cy = r + 2

        p.save()
        if self._shake_offset != 0.0:
            p.translate(self._shake_offset, 0)

        if self._state is _PipelineNode.State.ACTIVE and self._glow_opacity > 0:
            g = QRadialGradient(cx, cy, r * 2.5)
            g.setColorAt(0.0, QColor(124, 92, 255, int(60 * self._glow_opacity)))
            g.setColorAt(1.0, QColor(124, 92, 255, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r * 2.5, r * 2.5)

        if self._state is _PipelineNode.State.WAITING:
            p.setBrush(QColor("#262A37"))
            p.setPen(QPen(QColor("#3A4054"), 1.5))
        elif self._state is _PipelineNode.State.ACTIVE:
            p.setBrush(QColor("#1A1552"))
            p.setPen(QPen(COLOR_ACTIVE, 2))
        elif self._state is _PipelineNode.State.COMPLETED:
            p.setBrush(QColor("#0A2E1A"))
            p.setPen(QPen(COLOR_COMPLETED, 2))
        elif self._state is _PipelineNode.State.FAILED:
            p.setBrush(QColor("#2A1018"))
            p.setPen(QPen(COLOR_ERROR, 2))

        p.drawEllipse(QPointF(cx, cy), r, r)

        if self._state is _PipelineNode.State.COMPLETED and self._progress > 0:
            path = QPainterPath()
            path.arcMoveTo(cx - r, cy - r, r * 2, r * 2, 90)
            path.arcTo(cx - r, cy - r, r * 2, r * 2, 90, -360 * self._progress)
            p.setPen(QPen(COLOR_COMPLETED, 2.5, cap=Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

        inner_r = r - 4
        if self._state is _PipelineNode.State.WAITING:
            p.setBrush(QColor("#6B7280"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 3, 3)
        elif self._state is _PipelineNode.State.ACTIVE:
            angle = (time.time() * 180) % 360
            path = QPainterPath()
            path.arcMoveTo(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2, angle)
            path.arcTo(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2, angle, 270)
            p.setPen(QPen(COLOR_ACTIVE, 2.5, cap=Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        elif self._state is _PipelineNode.State.COMPLETED:
            if self._checkmark_progress > 0:
                p.setPen(QPen(COLOR_COMPLETED, 2.5, cap=Qt.RoundCap, join=Qt.RoundJoin))
                p.setBrush(Qt.NoBrush)
                path = QPainterPath()
                path.moveTo(cx - 4, cy + 1)
                path.lineTo(cx - 1, cy + 4)
                path.lineTo(cx + 5, cy - 3)
                if self._checkmark_progress < 1.0:
                    p.setOpacity(self._checkmark_progress)
                p.drawPath(path)
                if self._checkmark_progress < 1.0:
                    p.setOpacity(1.0)
            else:
                p.setBrush(COLOR_COMPLETED)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), 4, 4)
        elif self._state is _PipelineNode.State.FAILED:
            p.setPen(QPen(COLOR_ERROR, 2.5, cap=Qt.RoundCap))
            p.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
            p.drawLine(cx + 4, cy - 4, cx - 4, cy + 4)

        p.restore()

        p.setPen(COLOR_TEXT_PRIMARY if self._state is not _PipelineNode.State.WAITING else COLOR_TEXT_MUTED)
        f = QFont()
        f.setPointSize(10)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        p.drawText(cx + r + 14, cy - 6, self._name)
        p.end()


class _PipelineConnection(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._beam_progress = 0.0
        self._beam_opacity = 0.0
        self._beam_active = False
        self._beam_timer = QTimer(self)
        self._beam_timer.setInterval(30)
        self._beam_timer.timeout.connect(lambda: self.update())
        self.setFixedWidth(36)

    def fire_beam(self, duration: int = ANIM_BEAM_TRAVEL) -> None:
        if _reduced():
            return
        self._beam_active = True
        self._beam_progress = 0.0
        self._beam_opacity = 1.0
        anim = QPropertyAnimation(self, b"beam_progress", self)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.finished.connect(self._beam_finished)
        anim.start()
        self._beam_timer.start()

    def _beam_finished(self) -> None:
        self._beam_opacity = 0.0
        self._beam_active = False
        self._beam_timer.stop()
        self.update()

    def _get_beam(self) -> float:
        return self._beam_progress

    def _set_beam(self, v: float) -> None:
        self._beam_progress = v
        self.update()

    beam_progress = Property(float, _get_beam, _set_beam)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        cx = w / 2

        p.setPen(QPen(QColor("#2B3042"), 1.5))
        p.drawLine(round(cx), 0, round(cx), h)

        if self._beam_active and self._beam_opacity > 0:
            beam_y = self._beam_progress * h
            beam_h = 36
            g = QLinearGradient(0, beam_y - beam_h / 2, 0, beam_y + beam_h / 2)
            g.setColorAt(0.0, QColor(124, 92, 255, 0))
            g.setColorAt(0.3, QColor(124, 92, 255, int(80 * self._beam_opacity)))
            g.setColorAt(0.5, QColor(168, 148, 255, int(130 * self._beam_opacity)))
            g.setColorAt(0.7, QColor(124, 92, 255, int(80 * self._beam_opacity)))
            g.setColorAt(1.0, QColor(124, 92, 255, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            br = 4
            p.drawRoundedRect(round(cx - br), round(beam_y - beam_h / 2), br * 2, round(beam_h), br, br)
            p.setPen(QPen(QColor(200, 190, 255, int(180 * self._beam_opacity)), 2))
            p.drawLine(round(cx), round(beam_y - 6), round(cx), round(beam_y + 6))

        p.end()


class _ProgressBarCustom(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._target = 0.0
        self._shimmer_pos = 0.0
        self.setFixedHeight(20)
        if not _reduced():
            self._shimmer_timer = QTimer(self)
            self._shimmer_timer.setInterval(30)
            self._shimmer_timer.timeout.connect(self._shimmer_tick)
            self._shimmer_timer.start()

    def _shimmer_tick(self) -> None:
        self._shimmer_pos += 0.018
        self.update()

    def set_value(self, fraction: float) -> None:
        self._target = max(0.0, min(1.0, fraction))
        if _reduced():
            self._value = self._target
            self.update()
            return
        anim = QPropertyAnimation(self, b"display_value", self)
        anim.setDuration(300)
        anim.setStartValue(self._value)
        anim.setEndValue(self._target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

    def _get_display(self) -> float:
        return self._value

    def _set_display(self, v: float) -> None:
        self._value = v
        self.update()

    display_value = Property(float, _get_display, _set_display)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        radius = h / 2

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1A1D2B"))
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        fill_w = round(w * self._value)
        if fill_w > radius * 2:
            path = QPainterPath()
            path.addRoundedRect(0, 0, fill_w, h, radius, radius)
            clip = QPainterPath()
            clip.addRect(0, 0, fill_w, h)
            path = path.intersected(clip)
            g = QLinearGradient(0, 0, fill_w, 0)
            g.setColorAt(0.0, QColor("#7C5CFF"))
            g.setColorAt(1.0, QColor("#6366F1"))
            p.setBrush(QBrush(g))
            p.drawPath(path)

            if self._value > 0.05:
                sx = (math.sin(self._shimmer_pos * 2 * math.pi) * 0.3 + 0.3) * fill_w
                sg = QLinearGradient(sx - 20, 0, sx + 20, 0)
                sg.setColorAt(0.0, QColor(255, 255, 255, 0))
                sg.setColorAt(0.5, QColor(255, 255, 255, 25))
                sg.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.setBrush(QBrush(sg))
                p.drawPath(path)

        p.setPen(QPen(QColor("#2B3042"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(0, 0, w - 1, h - 1, radius, radius)
        p.end()


class _ImagePreviewPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._file_name = ""
        self._file_format = ""
        self._file_dimensions = ""
        self._file_size_str = ""
        self._queue_current = 0
        self._queue_total = 0
        self._next_file = ""
        self._slide_offset = 0.0
        self._slide_anim = QPropertyAnimation(self, b"slide_offset", self)
        self._slide_anim.setDuration(ANIM_IMAGE_TRANSITION)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._corners = 14

    def set_image(self, file_name: str, animate: bool = True) -> None:
        if not file_name:
            return
        old_name = self._file_name
        self._file_name = file_name
        path = file_name
        if not os.path.exists(path):
            from backend.state import paths
            candidate = paths().root / "input" / "original" / path
            if candidate.exists():
                path = str(candidate)
            else:
                self._pixmap = None
                self.update()
                return
        pm = QPixmap(path)
        self._pixmap = pm if not pm.isNull() else None

        if old_name and animate and not _reduced():
            self._slide_offset = 0.0
            self._is_transitioning = True
            self._slide_anim.setStartValue(0.0)
            self._slide_anim.setEndValue(1.0)
            try:
                self._slide_anim.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._slide_anim.finished.connect(self._slide_finished)
            self._slide_anim.start()

        self.update()

    def _slide_finished(self) -> None:
        self._is_transitioning = False
        self._slide_offset = 0.0
        self.update()

    def _get_slide(self) -> float:
        return self._slide_offset

    def _set_slide(self, v: float) -> None:
        self._slide_offset = v
        self.update()

    slide_offset = Property(float, _get_slide, _set_slide)

    def set_metadata(self, fmt: str, dims: str, size_str: str) -> None:
        self._file_format = fmt
        self._file_dimensions = dims
        self._file_size_str = size_str
        self.update()

    def set_queue(self, current: int, total: int, next_file: str = "") -> None:
        self._queue_current = current
        self._queue_total = total
        self._next_file = next_file
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w = self.width()
        h = self.height()

        preview_h = round(h * 0.62)
        margin = 0
        preview_rect = QRectF(margin, margin, w - margin * 2, preview_h - margin)

        p.setBrush(QColor("#0E0F14"))
        p.setPen(QPen(COLOR_BORDER, 1))
        p.drawRoundedRect(preview_rect, self._corners, self._corners)

        if self._pixmap:
            pm = self._pixmap
            max_w = preview_rect.width() - 30
            max_h = preview_rect.height() - 30
            scaled = pm.scaled(round(max_w), round(max_h),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ix = (w - scaled.width()) / 2
            iy = (preview_h - scaled.height()) / 2

            if getattr(self, "_is_transitioning", False) and self._slide_offset > 0:
                off = self._slide_offset
                p.save()
                p.setOpacity(1.0 - off)
                p.drawPixmap(round(ix - off * 30), round(iy), scaled)
                p.restore()
                p.save()
                p.setOpacity(off)
                clip_path = QPainterPath()
                clip_path.addRoundedRect(preview_rect, self._corners, self._corners)
                p.setClipPath(clip_path)
                p.drawPixmap(round(ix + (1.0 - off) * 50), round(iy), scaled)
                p.restore()
            else:
                p.drawPixmap(round(ix), round(iy), scaled)
        else:
            p.setPen(COLOR_TEXT_MUTED)
            f = QFont()
            f.setPointSize(11)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, preview_h), Qt.AlignCenter, "No preview")

        meta_y = preview_h + 16
        f = QFont()
        f.setPointSize(11)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(COLOR_TEXT_PRIMARY)
        p.drawText(QRectF(4, meta_y, w - 8, 18), Qt.AlignLeft | Qt.AlignVCenter, self._file_name)

        p.setPen(COLOR_TEXT_MUTED)
        f.setPointSize(9)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        parts = [self._file_format]
        if self._file_dimensions:
            parts.append(self._file_dimensions)
        if self._file_size_str:
            parts.append(self._file_size_str)
        p.drawText(QRectF(4, meta_y + 18, w - 8, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   "  \u2022  ".join(parts))

        q_y = meta_y + 48
        card_h = 40
        gap = 6
        cr = 10

        p.setBrush(COLOR_SURFACE)
        p.setPen(QPen(COLOR_BORDER, 1))
        p.drawRoundedRect(QRectF(4, q_y, w - 8, card_h), cr, cr)

        p.setPen(COLOR_TEXT_MUTED)
        f2 = QFont()
        f2.setPointSize(8)
        f2.setWeight(QFont.DemiBold)
        p.setFont(f2)
        p.drawText(QRectF(16, q_y + 4, 50, 14), Qt.AlignLeft | Qt.AlignVCenter, "CURRENT")

        p.setPen(COLOR_TEXT_PRIMARY)
        f3 = QFont()
        f3.setPointSize(10)
        f3.setWeight(QFont.Medium)
        p.setFont(f3)
        p.drawText(QRectF(16, q_y + 18, w - 40, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   Path(self._file_name).name if self._file_name else "-")

        p.setBrush(COLOR_ACTIVE)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(12, q_y + card_h / 2), 3, 3)

        if self._next_file:
            ny = q_y + card_h + gap
            p.setBrush(QColor("#0E0F14"))
            p.setPen(QPen(COLOR_BORDER, 1))
            p.drawRoundedRect(QRectF(4, ny, w - 8, card_h), cr, cr)
            p.setPen(COLOR_TEXT_MUTED)
            p.setFont(f2)
            p.drawText(QRectF(16, ny + 4, 50, 14), Qt.AlignLeft | Qt.AlignVCenter, "NEXT")
            p.setPen(COLOR_TEXT_MUTED)
            p.setFont(f3)
            p.drawText(QRectF(16, ny + 18, w - 40, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       self._next_file)
            p.setBrush(COLOR_TEXT_MUTED)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(12, ny + card_h / 2), 3, 3)

        rem_y = q_y + (card_h + gap) * (2 if self._next_file else 1) + 12
        p.setPen(COLOR_TEXT_MUTED)
        f4 = QFont()
        f4.setPointSize(9)
        p.setFont(f4)
        remaining = max(0, self._queue_total - self._queue_current + 1)
        p.drawText(QRectF(4, rem_y, w - 8, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   f"Remaining: {remaining}")
        p.end()


class ProcessingPage(QWidget):
    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")

        self._t0: float = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self._paused = False
        self._done = 0
        self._total = 0
        self._failed = 0
        self._current_file = ""
        self._previous_files: List[str] = []
        self._completed = False
        self._stage_index = -1
        self._stage_map = _StageLabelMap()

        self._bg = _AmbientBg(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QHBoxLayout()
        content.setContentsMargins(32, 24, 32, 24)
        content.setSpacing(24)

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(340)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(24, 20, 24, 20)
        left_lay.setSpacing(0)

        header = QLabel("Processing")
        header.setObjectName("PageTitle")
        left_lay.addWidget(header)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("PageSubtitle")
        self._subtitle.setStyleSheet("color: #8A90A6; font-size: 12px; margin-top: 2px;")
        left_lay.addWidget(self._subtitle)

        left_lay.addSpacing(24)

        pipe_label = QLabel("PIPELINE")
        pipe_label.setObjectName("SectionLabel")
        left_lay.addWidget(pipe_label)

        left_lay.addSpacing(16)

        self._nodes: List[_PipelineNode] = []
        self._connections: List[_PipelineConnection] = []
        pipeline_widget = QWidget()
        pipeline_lay = QVBoxLayout(pipeline_widget)
        pipeline_lay.setContentsMargins(0, 0, 0, 0)
        pipeline_lay.setSpacing(0)

        for i, name in enumerate(STAGE_NAMES):
            node = _PipelineNode(i, name)
            self._nodes.append(node)
            row = QHBoxLayout()
            row.setSpacing(0)
            row.addWidget(node)
            row.addStretch(1)
            pipeline_lay.addLayout(row)
            if i < len(STAGE_NAMES) - 1:
                conn = _PipelineConnection()
                self._connections.append(conn)
                row_c = QHBoxLayout()
                row_c.setSpacing(0)
                row_c.addWidget(conn)
                row_c.addStretch(1)
                pipeline_lay.addLayout(row_c)

        left_lay.addWidget(pipeline_widget)
        left_lay.addSpacing(12)

        self._desc_label = QLabel("")
        self._desc_label.setStyleSheet(
            "color: #7C5CFF; font-size: 11px; font-style: italic; padding-left: 4px;"
        )
        self._desc_label.setWordWrap(True)
        left_lay.addWidget(self._desc_label)

        left_lay.addSpacing(20)

        div = QFrame()
        div.setObjectName("Divider")
        div.setFixedHeight(1)
        left_lay.addWidget(div)

        left_lay.addSpacing(14)

        self._bar = _ProgressBarCustom()
        left_lay.addWidget(self._bar)

        left_lay.addSpacing(8)

        self._perc_label = QLabel("0%")
        self._perc_label.setStyleSheet("color: #6B7186; font-size: 11px;")
        left_lay.addWidget(self._perc_label)

        left_lay.addSpacing(4)

        status_row = QHBoxLayout()
        status_row.setSpacing(16)
        self._stage_status = QLabel("Idle")
        self._stage_status.setStyleSheet("color: #C4C8D6; font-size: 12px; font-weight: 600;")
        self._eta_label = QLabel("ETA  --:--")
        self._eta_label.setStyleSheet(
            "color: #6B7186; font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px;"
        )
        self._count_label = QLabel("0 / 0")
        self._count_label.setStyleSheet(
            "color: #6B7186; font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px;"
        )
        status_row.addWidget(self._stage_status, 1)
        status_row.addWidget(self._count_label)
        status_row.addWidget(self._eta_label)
        left_lay.addLayout(status_row)

        left_lay.addSpacing(14)

        self._failed_list = QLabel("")
        self._failed_list.setStyleSheet("color: #EF4444; font-size: 11px;")
        self._failed_list.setWordWrap(True)
        self._failed_list.setVisible(False)
        left_lay.addWidget(self._failed_list)

        left_lay.addSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addStretch(1)
        self._btn_pause = PrimaryButton("  Pause")
        self._btn_pause.setIcon(icon("pause", 16, color="#FFFFFF"))
        self._btn_pause.clicked.connect(self._toggle_pause)
        self._btn_resume = PrimaryButton("  Resume")
        self._btn_resume.setIcon(icon("play", 16, color="#FFFFFF"))
        self._btn_resume.clicked.connect(self._toggle_pause)
        self._btn_resume.hide()
        self._btn_cancel = DangerButton("  Cancel")
        self._btn_cancel.setIcon(icon("close", 16, color="#F87171"))
        self._btn_cancel.clicked.connect(self.cancel_requested.emit)
        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_resume)
        controls.addWidget(self._btn_cancel)
        left_lay.addLayout(controls)

        content.addWidget(left)

        self._preview = _ImagePreviewPanel()
        content.addWidget(self._preview, 1)

        root.addLayout(content, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())

    def begin(self, total: int) -> None:
        self._t0 = time.monotonic()
        self._done = 0
        self._failed = 0
        self._total = max(0, total)
        self._completed = False
        self._stage_index = -1
        self._current_file = ""
        self._previous_files = []
        self._stage_map = _StageLabelMap()

        self._subtitle.setText(f"Batch of {self._total} image{'s' if self._total != 1 else ''}")
        self._desc_label.setText("")
        self._stage_status.setText("Preparing...")
        self._eta_label.setText("ETA  --:--")
        self._count_label.setText(f"0 / {self._total}")
        self._perc_label.setText("0%")
        self._bar.set_value(0.0)
        self._failed_list.setVisible(False)
        self._failed_list.setText("")

        for node in self._nodes:
            node.set_state(_PipelineNode.State.WAITING, animate=False)

        self._set_paused(False)
        self._enable_controls(True)
        self._timer.start()

    def end(self) -> None:
        self._timer.stop()
        self._enable_controls(False)

    def reset(self) -> None:
        self._timer.stop()
        self._t0 = 0.0
        self._done = self._failed = self._total = 0
        self._completed = False
        self._stage_index = -1
        self._current_file = ""
        self._previous_files = []
        self._stage_map = _StageLabelMap()
        for node in self._nodes:
            node.set_state(_PipelineNode.State.WAITING, animate=False)
        self._bar.set_value(0.0)
        self._perc_label.setText("0%")
        self._stage_status.setText("Idle")
        self._eta_label.setText("ETA  --:--")
        self._count_label.setText("0 / 0")
        self._desc_label.setText("")
        self._subtitle.setText("")
        self._failed_list.setVisible(False)
        self._failed_list.setText("")

    def on_stage(self, stage: str) -> None:
        if stage == "Completed":
            return

        idx = _STAGE_LABEL_TO_INDEX.get(stage, -1)
        if idx < 0:
            return

        if idx > self._stage_index:
            start = max(0, self._stage_index)
            for pi in range(start, idx):
                if pi < len(self._nodes):
                    self._nodes[pi].set_state(_PipelineNode.State.COMPLETED)
            if idx > 0 and idx - 1 < len(self._connections):
                self._connections[idx - 1].fire_beam()
            self._stage_index = idx

        if idx < len(self._nodes) and self._nodes[idx].state is _PipelineNode.State.WAITING:
            self._nodes[idx].set_state(_PipelineNode.State.ACTIVE)

        if idx < len(STAGE_NAMES):
            self._stage_status.setText(STAGE_NAMES[idx])
            self._desc_label.setText(_STAGE_DESCRIPTIONS[idx])

    def _mark_all_completed(self) -> None:
        for i, node in enumerate(self._nodes):
            animate = i == self._stage_index and self._stage_index >= 0
            node.set_state(_PipelineNode.State.COMPLETED, animate=animate)

    def _start_completion_animation(self) -> None:
        if _reduced():
            return
        QTimer.singleShot(ANIM_COMPLETION, self._on_completion_done)

    def _on_completion_done(self) -> None:
        self._stage_status.setText("All images processed")

    def on_status(self, file_name: str) -> None:
        if not file_name:
            return
        if self._current_file and self._current_file != file_name:
            self._previous_files.append(self._current_file)
        self._current_file = file_name
        self._preview.set_image(file_name)

    def on_progress(self, done: int, total: int, current_file: str) -> None:
        self._done = done
        self._total = max(0, total)
        pct = (done / self._total * 100) if self._total > 0 else 0.0
        self._bar.set_value(pct / 100.0)
        self._perc_label.setText(f"{round(pct)}%")
        self._count_label.setText(f"{done} / {self._total}")
        if current_file and current_file != self._current_file:
            self._current_file = current_file
            self._preview.set_image(current_file)
        self._recalc_eta()

    def on_log(self, level: str, logger: str, message: str) -> None:
        pass

    def on_image_failed(self, file_name: str, message: str) -> None:
        self._failed += 1
        idx = self._stage_index if self._stage_index >= 0 else 0
        if idx < len(self._nodes):
            self._nodes[idx].set_state(_PipelineNode.State.FAILED)
        fails = []
        if self._failed_list.text():
            fails = self._failed_list.text().split("\n")
        fails.append(f"{file_name}: {message}")
        if len(fails) > 5:
            fails = fails[-5:]
        self._failed_list.setText("\n".join(fails))
        self._failed_list.setVisible(True)

    def on_summary(self, summary: RunSummary) -> None:
        self.end()
        if not summary.cancelled:
            self._mark_all_completed()
            self._stage_status.setText("Completed" if summary.all_succeeded else "Completed with errors")
            if not summary.all_succeeded:
                self._stage_status.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: 600;")
        else:
            self._stage_status.setText("Cancelled")
            self._stage_status.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: 600;")
        self._completed = True
        if _reduced():
            self._on_completion_done()

    def on_failed(self, message: str) -> None:
        self._stage_status.setText("Failed")
        self._stage_status.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: 600;")
        self._failed_list.setText(message)
        self._failed_list.setVisible(True)
        self.end()

    def _enable_controls(self, enabled: bool) -> None:
        self._btn_pause.setEnabled(enabled)
        self._btn_cancel.setEnabled(enabled)

    def _toggle_pause(self) -> None:
        if self._paused:
            self._set_paused(False)
            self.resume_requested.emit()
        else:
            self._set_paused(True)
            self.pause_requested.emit()

    def _set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._btn_pause.setVisible(not paused)
        self._btn_resume.setVisible(paused)
        if paused:
            self._timer.stop()
        else:
            self._timer.start()

    def _tick(self) -> None:
        self._recalc_eta()

    def _elapsed_seconds(self) -> float:
        if not self._t0:
            return 0.0
        return time.monotonic() - self._t0

    def _recalc_eta(self) -> None:
        done = self._done - self._failed
        if self._total <= 0 or done <= 0:
            self._eta_label.setText("ETA  --:--")
            return
        secs_per = self._elapsed_seconds() / done
        remaining = (self._total - self._done) * secs_per
        self._eta_label.setText(f"ETA  {_fmt(max(0.0, remaining))}")
