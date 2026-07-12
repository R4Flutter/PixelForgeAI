from __future__ import annotations

import math
import os
import random
import time
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QPointF, QRectF, QSizeF, QByteArray, Property, QElapsedTimer,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPauseAnimation,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QConicalGradient,
    QEnterEvent, QMouseEvent, QRegion,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QGraphicsBlurEffect,
    QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QSizePolicy, QVBoxLayout, QWidget, QPushButton,
)

from backend.job import RunSummary
from components.buttons import DangerButton, PrimaryButton


from design_system.tokens.colors import Colors
from design_system.tokens.spacing import Spacing
from design_system.tokens.typography import Typography
from design_system.tokens.elevation import Elevation


COL = Colors()
SP = Spacing()
TYP = Typography()
ELV = Elevation()

STAGE_NAMES = ["Load Image", "Remove BG", "AI Upscale", "Resize", "Save"]
_STAGE_DESCRIPTIONS = [
    "Analyzing source image data...",
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


ANIM_CONSTRUCTION = 2000
ANIM_CHECKMARK = 200
ANIM_BEAM_TRAVEL = 300
ANIM_IMAGE_TRANSITION = 400
ANIM_COMPLETION = 600
ANIM_NODE_ACTIVATE = 150
ANIM_CONNECTOR_LIQUID = 500
ANIM_NODE_BREATHE = 2000
ANIM_STAGE_DELAY = 250
ANIM_CARD_STAGGER = 70
ANIM_BUTTON_HOVER = 200
ANIM_BUTTON_PRESS = 100


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _fmt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _tk(color_hex: str) -> QColor:
    return QColor(color_hex)


def _tk_a(color_hex: str, alpha: int) -> QColor:
    c = QColor(color_hex)
    c.setAlpha(alpha)
    return c


def _sin(t: float, offset: float = 0.0, speed: float = 1.0) -> float:
    return 0.5 + 0.5 * math.sin(t * speed * math.tau + offset)


class _StageLabelMap:
    def __init__(self) -> None:
        self._current: str | None = None

    def map(self, stage: str) -> str | None:
        if stage == self._current:
            return None
        self._current = stage
        return stage


class _FloatingBg(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._angle = 0.0
        self._phase = 0.0
        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(50)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _tick(self) -> None:
        self._angle += 0.003
        self._phase += 0.02
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        cx1 = w * 0.5 + math.cos(self._angle) * w * 0.15
        cy1 = h * 0.3 + math.sin(self._angle * 0.7) * h * 0.12
        g1 = QRadialGradient(cx1, cy1, max(w, h) * 0.5)
        g1.setColorAt(0.0, _tk_a(COL.accent, 8))
        g1.setColorAt(0.5, _tk_a(COL.accent, 3))
        g1.setColorAt(1.0, _tk(COL.bg_primary))
        p.fillRect(self.rect(), QBrush(g1))

        cx2 = w * 0.7 - math.cos(self._phase * 0.5) * w * 0.1
        cy2 = h * 0.7 + math.sin(self._phase * 0.3) * h * 0.1
        g2 = QRadialGradient(cx2, cy2, max(w, h) * 0.35)
        g2.setColorAt(0.0, _tk_a(COL.accent_hover, 6))
        g2.setColorAt(1.0, _tk(COL.bg_primary))
        p.fillRect(self.rect(), QBrush(g2))

        cx3 = w * 0.2 + math.cos(self._angle * 0.4) * w * 0.08
        cy3 = h * 0.5 + math.sin(self._angle * 0.5) * h * 0.08
        g3 = QRadialGradient(cx3, cy3, max(w, h) * 0.25)
        g3.setColorAt(0.0, _tk_a(COL.accent, 4))
        g3.setColorAt(1.0, _tk(COL.bg_primary))
        p.fillRect(self.rect(), QBrush(g3))

        p.end()


class _RotatingIndicator(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(16, 16)
        self._angle = 0.0
        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(30)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _tick(self) -> None:
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = 8, 8
        pen = QPen(_tk(COL.accent), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(QRectF(1, 1, 14, 14), int((self._angle - 60) * 16), int(300 * 16))
        p.end()


class _ImageOverlay(QWidget):
    class Phase(Enum):
        CONSTRUCTING = auto()
        ACTIVE = auto()
        SUCCESS = auto()
        HIDDEN = auto()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._phase = _ImageOverlay.Phase.HIDDEN
        self._time = 0.0
        self._construction_progress = 0.0
        self._shimmer_pos = 0.0
        self._scan_pos = 0.0
        self._grid_opacity = 0.0
        self._ring_progress = 0.0
        self._sparkles: list[dict] = []
        self._particles: list[dict] = []
        self._blur_amount = 8.0
        self._edge_mask = 0.0
        self._success_glow = 0.0

        self._init_particles()
        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _init_particles(self) -> None:
        for i in range(16):
            angle = random.random() * 360
            self._particles.append({
                "angle": angle,
                "speed": 0.2 + random.random() * 0.4,
                "radius": 0.0,
                "phase": random.random() * 360,
                "size": 1 + random.random() * 2,
                "orbit": 0.3 + random.random() * 0.4,
            })

    def start_construction(self) -> None:
        self._phase = _ImageOverlay.Phase.CONSTRUCTING
        self._construction_progress = 0.0
        self._blur_amount = 8.0
        self._edge_mask = 0.0
        self._grid_opacity = 0.5
        self._shimmer_pos = 0.0
        self._scan_pos = 0.0
        self._ring_progress = 0.0
        self._success_glow = 0.0
        self.show()

    def start_active(self) -> None:
        self._phase = _ImageOverlay.Phase.ACTIVE
        self._construction_progress = 1.0
        self._blur_amount = 0.0
        self._edge_mask = 1.0
        self._grid_opacity = 0.0
        self.show()

    def start_success(self) -> None:
        self._phase = _ImageOverlay.Phase.SUCCESS
        self._ring_progress = 0.0
        self._success_glow = 0.0
        self._sparkles = []
        for i in range(12):
            a = random.random() * 360
            r = 15 + random.random() * 50
            self._sparkles.append({
                "angle": a, "radius": r,
                "speed": 1 + random.random() * 2,
                "life": 1.0, "size": 1.5 + random.random() * 3,
            })
        self.show()

    def hide_overlay(self) -> None:
        self._phase = _ImageOverlay.Phase.HIDDEN
        self.hide()

    def _tick(self) -> None:
        dt = 0.016
        self._time += dt
        if self._phase is _ImageOverlay.Phase.CONSTRUCTING:
            self._construction_progress = min(1.0, self._construction_progress + dt * 0.5)
            self._blur_amount = max(0.0, 8.0 * (1.0 - self._construction_progress * 1.5))
            self._edge_mask = min(1.0, self._construction_progress * 1.2)
            self._grid_opacity = max(0.0, 0.5 * (1.0 - self._construction_progress * 1.5))
        if self._phase in (_ImageOverlay.Phase.CONSTRUCTING, _ImageOverlay.Phase.ACTIVE):
            self._shimmer_pos = (self._shimmer_pos + dt * 0.06) % 2.0
            self._scan_pos = (self._scan_pos + dt * 0.025) % 1.0
            for p in self._particles:
                p["angle"] = (p["angle"] + p["speed"] * dt * 12) % 360
        if self._phase is _ImageOverlay.Phase.SUCCESS:
            self._ring_progress = min(1.0, self._ring_progress + dt * 1.2)
            self._success_glow = min(1.0, self._success_glow + dt * 0.8)
            for s in self._sparkles:
                s["radius"] += s["speed"] * dt * 60
                s["life"] = max(0.0, s["life"] - dt * 0.4)
        self.update()

    def _get_construction(self) -> float:
        return self._construction_progress

    def _set_construction(self, v: float) -> None:
        self._construction_progress = v
        self.update()

    construction_progress = Property(float, _get_construction, _set_construction)

    def paintEvent(self, event) -> None:
        if self._phase is _ImageOverlay.Phase.HIDDEN:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        if w < 1 or h < 1:
            p.end()
            return

        self._draw_edge_build(p, w, h)
        self._draw_grid(p, w, h)
        self._draw_shimmer(p, w, h)
        self._draw_scan_line(p, w, h)
        self._draw_particles(p, w, h)
        self._draw_success_ring(p, w, h)
        self._draw_sparkles(p, w, h)
        p.end()

    def _draw_edge_build(self, p: QPainter, w: int, h: int) -> None:
        if self._phase is not _ImageOverlay.Phase.CONSTRUCTING:
            return
        progress = min(1.0, self._construction_progress * 1.5)
        if progress <= 0:
            return
        mask = QPainterPath()
        margin = w * (1.0 - progress) * 0.5
        aspect = h / w
        inner_w = w - margin * 2
        inner_h = h - margin * 2 * aspect
        inner_rect = QRectF(margin, (h - inner_h) * 0.5, inner_w, inner_h)
        mask.addRoundedRect(inner_rect, 20 * progress, 20 * progress)
        full = QPainterPath()
        full.addRect(0, 0, w, h)
        reveal = full.subtracted(mask)
        p.setClipPath(reveal)
        p.fillRect(self.rect(), QColor(COL.bg_primary))

    def _draw_grid(self, p: QPainter, w: int, h: int) -> None:
        if self._grid_opacity <= 0:
            return
        p.setOpacity(self._grid_opacity)
        p.setPen(QPen(_tk_a(COL.accent, 12), 0.5))
        grid_size = 28
        for x in range(0, w, grid_size):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, grid_size):
            p.drawLine(0, y, w, y)
        p.setOpacity(1.0)

    def _draw_shimmer(self, p: QPainter, w: int, h: int) -> None:
        if self._phase not in (_ImageOverlay.Phase.CONSTRUCTING, _ImageOverlay.Phase.ACTIVE):
            return
        cx = self._shimmer_pos * w
        g = QLinearGradient(cx - w * 0.25, 0, cx + w * 0.25, 0)
        g.setColorAt(0.0, _tk_a(COL.accent, 0))
        g.setColorAt(0.4, _tk_a(COL.accent, 10))
        g.setColorAt(0.5, _tk_a("#A78BFA", 15))
        g.setColorAt(0.6, _tk_a(COL.accent, 10))
        g.setColorAt(1.0, _tk_a(COL.accent, 0))
        p.fillRect(self.rect(), QBrush(g))

    def _draw_scan_line(self, p: QPainter, w: int, h: int) -> None:
        if self._phase not in (_ImageOverlay.Phase.CONSTRUCTING, _ImageOverlay.Phase.ACTIVE):
            return
        sy = self._scan_pos * h
        g = QLinearGradient(0, sy - 3, 0, sy + 3)
        g.setColorAt(0.0, _tk_a(COL.accent, 0))
        g.setColorAt(0.5, _tk_a(COL.accent, 15))
        g.setColorAt(1.0, _tk_a(COL.accent, 0))
        p.fillRect(0, round(sy - 3), w, 6, QBrush(g))

    def _draw_particles(self, p: QPainter, w: int, h: int) -> None:
        if self._phase is _ImageOverlay.Phase.HIDDEN:
            return
        cx, cy = w / 2, h / 2
        for pt in self._particles:
            a_rad = math.radians(pt["angle"])
            orbit = min(w, h) * pt["orbit"] * 0.8
            px = cx + orbit * math.cos(a_rad)
            py = cy + orbit * math.sin(a_rad)
            alpha = int(50 + 40 * math.sin(self._time * pt["speed"] + pt["phase"]))
            p.setPen(Qt.NoPen)
            p.setBrush(_tk_a(COL.accent, alpha))
            p.drawEllipse(QPointF(px, py), pt["size"], pt["size"])

    def _draw_success_ring(self, p: QPainter, w: int, h: int) -> None:
        if self._phase is not _ImageOverlay.Phase.SUCCESS:
            return
        cx, cy = w / 2, h / 2
        outer = min(w, h) * 0.48
        if self._ring_progress > 0:
            path = QPainterPath()
            path.arcMoveTo(cx - outer, cy - outer, outer * 2, outer * 2, -90)
            path.arcTo(cx - outer, cy - outer, outer * 2, outer * 2, -90, -360 * self._ring_progress)
            pen = QPen(_tk(COL.success), 2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        if self._success_glow > 0:
            g = QRadialGradient(cx, cy, outer)
            g.setColorAt(0.0, _tk_a(COL.success, int(10 * self._success_glow)))
            g.setColorAt(0.8, _tk_a(COL.success, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), outer, outer)

    def _draw_sparkles(self, p: QPainter, w: int, h: int) -> None:
        if not self._sparkles:
            return
        cx, cy = w / 2, h / 2
        for s in self._sparkles:
            if s["life"] <= 0:
                continue
            a = math.radians(s["angle"])
            px = cx + s["radius"] * math.cos(a)
            py = cy + s["radius"] * math.sin(a)
            alpha = int(200 * s["life"])
            p.setPen(Qt.NoPen)
            p.setBrush(_tk_a(COL.success, alpha))
            p.drawEllipse(QPointF(px, py), s["size"], s["size"])


class _ProcessingOverlay(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._visible = False
        self._opacity = 0.0
        self._stage_text = ""
        self._percent = 0
        self._eta_text = ""
        self._phase = 0.0
        self._anim_opacity = 0.0
        self._dot_phase = 0.0
        self._loader_time = 0.0

        svg_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "flower-loader.svg")
        )
        self._renderer: QSvgRenderer | None = None
        try:
            with open(svg_path, "rb") as f:
                self._renderer = QSvgRenderer(QByteArray(f.read()))
        except Exception:
            pass

        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def show_overlay(self) -> None:
        self._visible = True
        self._anim_opacity = 0.0
        self.show()

    def hide_overlay(self) -> None:
        self._visible = False
        self.hide()

    def update_info(self, stage: str, percent: int, eta: str) -> None:
        self._stage_text = stage
        self._percent = percent
        self._eta_text = eta
        self.update()

    def _tick(self) -> None:
        if self._visible:
            self._anim_opacity = min(1.0, self._anim_opacity + 0.035)
            self._phase += 0.05
            self._dot_phase += 0.02
            self._loader_time += 0.016
            self.update()

    def paintEvent(self, event) -> None:
        if not self._visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w < 1 or h < 1:
            p.end()
            return

        p.fillRect(self.rect(), _tk_a(COL.bg_primary, int(120 * self._anim_opacity)))

        cx, cy = w / 2, h * 0.45

        r = 32
        arc_pen = QPen(_tk_a(COL.accent, int(25 * self._anim_opacity)), 3)
        p.setPen(arc_pen)
        p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 0, 360 * 16)

        sweep = self._percent * 360 / 100
        fill_pen = QPen(_tk(COL.accent), 3)
        fill_pen.setCapStyle(Qt.RoundCap)
        p.setPen(fill_pen)
        p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), -90 * 16, int(-sweep * 16))

        p.setPen(_tk_a(COL.text_primary, int(255 * self._anim_opacity)))
        pf = QFont()
        pf.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        pf.setPointSize(16)
        pf.setWeight(QFont.Bold)
        p.setFont(pf)
        p.drawText(QRectF(0, cy - 16, w, 32), Qt.AlignCenter, f"{self._percent}%")

        p.setPen(_tk_a(COL.text_secondary, int(200 * self._anim_opacity)))
        sf = QFont()
        sf.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        sf.setPointSize(11)
        sf.setWeight(QFont.Medium)
        p.setFont(sf)

        title_rect = QRectF(0, cy + r + 14, w, 22)
        p.drawText(title_rect, Qt.AlignCenter, "AI Processing")

        stage_rect = QRectF(0, cy + r + 38, w, 20)
        p.setPen(_tk_a(COL.text_primary, int(220 * self._anim_opacity)))
        sf2 = QFont()
        sf2.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        sf2.setPointSize(12)
        sf2.setWeight(QFont.DemiBold)
        p.setFont(sf2)
        p.drawText(stage_rect, Qt.AlignCenter, self._stage_text)

        eta_rect = QRectF(0, cy + r + 60, w, 16)
        if self._eta_text and "ETA" in self._eta_text:
            p.setPen(_tk_a(COL.text_muted, int(160 * self._anim_opacity)))
            ef = QFont()
            ef.setFamilies(["Inter", "Segoe UI", "sans-serif"])
            ef.setPointSize(9)
            p.setFont(ef)
            p.drawText(eta_rect, Qt.AlignCenter, self._eta_text)

        if self._anim_opacity > 0.05:
            dots = "." * (int(self._dot_phase * 3) % 4)
            dr = QRectF(0, cy + r + 78, w, 14)
            p.setPen(_tk_a(COL.text_muted, int(120 * self._anim_opacity)))
            df = QFont()
            df.setFamilies(["Inter", "Segoe UI", "sans-serif"])
            df.setPointSize(8)
            p.setFont(df)
            p.drawText(dr, Qt.AlignCenter, f"reconstructing{dots}")

        self._draw_loader(p, w, h)
        p.end()

    def _draw_loader(self, p: QPainter, w: int, h: int) -> None:
        if self._renderer is None:
            return
        base_size = 48
        cx = w / 2
        ay = h * 0.35

        for i, delay in enumerate([0.0, 0.3, 0.6]):
            t = (self._loader_time - delay) % 1.0
            if t < 0:
                t += 1.0

            if t < 0.25:
                progress = t / 0.25
                scale = 0.5 + 0.25 * progress
                y_off = -50 + 25 * progress
                opacity = self._anim_opacity * progress
            elif t < 0.5:
                progress = (t - 0.25) / 0.25
                scale = 0.75 + 0.25 * progress
                y_off = -25 + 25 * progress
                opacity = self._anim_opacity * 1.0
            elif t < 0.75:
                progress = (t - 0.5) / 0.25
                scale = 1.0 - 0.5 * progress
                y_off = 0 + 15 * progress
                opacity = self._anim_opacity * 1.0
            else:
                progress = (t - 0.75) / 0.25
                scale = 0.5 - 0.5 * progress
                y_off = 15 + 10 * progress
                opacity = self._anim_opacity * (1.0 - progress)

            sz = base_size * scale
            rot = t * 10
            p.save()
            p.translate(cx, ay + y_off)
            p.rotate(rot)
            p.setOpacity(opacity)
            self._renderer.render(p, QRectF(-sz / 2, -sz / 2, sz, sz))
            p.restore()


class _StepperNode(QWidget):
    class State(Enum):
        WAITING = auto()
        ACTIVE = auto()
        COMPLETED = auto()
        FAILED = auto()

    CIR = 20
    GAP = 14

    def __init__(self, index: int, name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._index = index
        self._name = name
        self._status_text = ""
        self._time_text = ""
        self._state = _StepperNode.State.WAITING
        self._glow_phase = 0.0
        self._check_progress = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(30)
        self._pulse_timer.timeout.connect(self._pulse_tick)

        self._title_lbl = QLabel(name, self)
        self._title_lbl.setFont(QFont(["Inter", "Segoe UI", "sans-serif"], 14, QFont.DemiBold))

        self._badge_lbl = QLabel("Pending", self)
        self._badge_lbl.setFont(QFont(["Inter", "Segoe UI", "sans-serif"], 11))
        self._badge_lbl.setStyleSheet(
            f"color: {COL.text_muted}; background: transparent;"
        )

        self._time_lbl = QLabel("", self)
        self._time_lbl.setFont(QFont(["Inter", "Segoe UI", "sans-serif"], 10))
        self._time_lbl.setStyleSheet(
            f"color: {COL.text_muted}; background: transparent;"
        )
        self._time_lbl.hide()

        self.setFixedHeight(84)
        self.setMinimumWidth(180)

    @property
    def state(self) -> State:
        return self._state

    def set_state(self, state: State, animate: bool = True) -> None:
        if self._state == state:
            return
        self._state = state
        if state is _StepperNode.State.ACTIVE:
            self._glow_phase = 0.0
            self._pulse_timer.start()
            self._badge_lbl.setText("In Progress")
            self._time_lbl.hide()
        elif state is _StepperNode.State.COMPLETED:
            self._pulse_timer.stop()
            self._glow_phase = 0.0
            self._check_progress = 0.0
            self._badge_lbl.setText("Completed")
            if animate and not _reduced():
                anim = QPropertyAnimation(self, b"check_progress", self)
                anim.setDuration(ANIM_CHECKMARK)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.OutBack)
                anim.start()
            else:
                self._check_progress = 1.0
        elif state is _StepperNode.State.WAITING:
            self._pulse_timer.stop()
            self._glow_phase = 0.0
            self._badge_lbl.setText("Pending")
            self._time_lbl.setText("Waiting...")
            self._time_lbl.show()
        else:
            self._pulse_timer.stop()
            self._glow_phase = 0.0
            self._badge_lbl.setText("Failed")
            self._time_lbl.hide()
        self._update_label_styles()
        self.update()

    def set_status(self, text: str) -> None:
        self._status_text = text
        self._badge_lbl.setText(text)
        self._badge_lbl.setVisible(True)
        self._update_label_styles()
        self.update()

    def set_time(self, text: str) -> None:
        self._time_text = text
        self._time_lbl.setText(text)
        self._time_lbl.setVisible(bool(text))
        self.update()

    def _update_label_styles(self) -> None:
        if self._state is _StepperNode.State.COMPLETED:
            self._title_lbl.setStyleSheet(f"color: {COL.text_primary}; background: transparent;")
            self._badge_lbl.setStyleSheet(f"color: {COL.success}; background: {COL.success}20; border-radius: 8px; padding: 1px 7px;")
        elif self._state is _StepperNode.State.ACTIVE:
            self._title_lbl.setStyleSheet(f"color: {COL.text_primary}; background: transparent;")
            self._badge_lbl.setStyleSheet(f"color: {COL.accent}; background: {COL.accent}20; border-radius: 8px; padding: 1px 7px;")
        elif self._state is _StepperNode.State.WAITING:
            self._title_lbl.setStyleSheet(f"color: {COL.text_muted}; background: transparent;")
            self._badge_lbl.setStyleSheet(f"color: {COL.text_muted}; background: {COL.text_muted}20; border-radius: 8px; padding: 1px 7px;")
        elif self._state is _StepperNode.State.FAILED:
            self._title_lbl.setStyleSheet(f"color: {COL.text_primary}; background: transparent;")
            self._badge_lbl.setStyleSheet(f"color: {COL.error}; background: {COL.error}20; border-radius: 8px; padding: 1px 7px;")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        r = self.CIR
        tx = self.CIR + r + self.GAP
        cy = self.height() / 2
        self._title_lbl.setGeometry(tx, int(cy - 22), self.width() - tx - 8, 20)
        self._badge_lbl.setGeometry(tx, int(cy + 2), self.width() - tx - 8, 20)
        self._time_lbl.setGeometry(tx, int(cy + 24), self.width() - tx - 8, 16)

    def _pulse_tick(self) -> None:
        self._glow_phase += 0.05
        self.update()

    def _get_check(self) -> float:
        return self._check_progress

    def _set_check(self, v: float) -> None:
        self._check_progress = v
        self.update()

    check_progress = Property(float, _get_check, _set_check)

    def _draw_check(self, p: QPainter, cx: int, cy: int, d: float) -> None:
        pen = QPen(_tk(COL.bg_active), 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cx - 4, cy)
        path.lineTo(cx - 1, cy + 3)
        path.lineTo(cx + 5, cy - 3)
        if d < 1.0:
            p.setOpacity(d)
        p.drawPath(path)
        if d < 1.0:
            p.setOpacity(1.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        if w < 1 or h < 1:
            p.end()
            return
        cx = self.CIR
        cy = h / 2
        r = self.CIR

        conn_col = _tk(COL.border)
        if self._state is _StepperNode.State.COMPLETED:
            conn_col = _tk_a(COL.success, 120)
        elif self._state is _StepperNode.State.ACTIVE:
            conn_col = _tk_a(COL.accent, 80)

        p.setPen(QPen(conn_col, 2))
        p.drawLine(cx, int(cy + r + 1), cx, h)

        if self._state is _StepperNode.State.WAITING:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(_tk_a(COL.text_muted, 80), 1.5))
            p.drawEllipse(QPointF(cx, cy), r, r)

        elif self._state is _StepperNode.State.ACTIVE:
            glow = 0.35 + 0.25 * math.sin(self._glow_phase)
            g = QRadialGradient(cx, cy, r * 2.2)
            g.setColorAt(0.0, _tk_a(COL.accent, int(50 * glow)))
            g.setColorAt(1.0, _tk_a(COL.accent, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r * 2.2, r * 2.2)
            p.setBrush(_tk(COL.accent))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setPen(_tk_a(COL.bg_active, 200))
            nf = QFont(["Inter", "Segoe UI", "sans-serif"], 11, QFont.Medium)
            p.setFont(nf)
            p.drawText(QRectF(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, str(self._index + 1))

        elif self._state is _StepperNode.State.COMPLETED:
            p.setBrush(_tk(COL.success))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r, r)
            if self._check_progress > 0:
                self._draw_check(p, cx, cy, self._check_progress)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(_tk(COL.bg_active))
                p.drawEllipse(QPointF(cx, cy), 4, 4)

        elif self._state is _StepperNode.State.FAILED:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(_tk(COL.error), 2))
            p.drawEllipse(QPointF(cx, cy), r, r)
            pen = QPen(_tk(COL.error), 2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            p.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)

        p.end()


class _PacmanLoader(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._running = False
        self._time = 0.0
        self.setFixedHeight(60)
        self.setMinimumWidth(200)
        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _tick(self) -> None:
        if self._running:
            self._time += 0.016
            self.update()

    def start(self) -> None:
        self._running = True
        self.show()

    def stop(self) -> None:
        self._running = False
        self.hide()

    def set_value(self, fraction: float) -> None:
        was_running = self._running
        self._running = fraction >= 0 and fraction < 1.0
        if self._running:
            if not was_running:
                self._time = 0.0
            self.show()
        else:
            self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        t = self._time

        cx = w / 2 - 8
        cy = h / 2
        pr = 20

        cycle = (t % 0.125) / 0.125
        mouth_angle = 35 * (1 - abs(2 * cycle - 1))

        pac_rect = QRectF(cx - pr, cy - pr, pr * 2, pr * 2)
        p.setBrush(QColor("#EFF107"))
        p.setPen(Qt.NoPen)
        p.drawPie(pac_rect, mouth_angle * 16, (360 - 2 * mouth_angle) * 16)

        p.setBrush(QColor("#000000"))
        p.drawEllipse(QRectF(cx - pr * 0.2 - 3, cy - pr * 0.35 - 3, 6, 6))

        dot_r = 4
        p.setBrush(QColor("#FFFFFF"))
        offset = cycle * 26
        starts = [34, 58, 82, 106]

        for i in range(4):
            dx = starts[i] - offset
            if dx < -dot_r:
                continue

            if i == 3 and dx < pr + dot_r:
                s = max(0, (dx - dot_r) / pr)
                if s > 0.05:
                    p.save()
                    p.translate(cx + dx, cy)
                    p.scale(s, s)
                    p.drawEllipse(QRectF(-dot_r, -dot_r, dot_r * 2, dot_r * 2))
                    p.restore()
            else:
                p.drawEllipse(QRectF(cx + dx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2))

        p.end()


class _PillButton(QPushButton):
    def __init__(self, text: str = "", icon_char: str = "", style: str = "primary", parent=None) -> None:
        super().__init__(text, parent)
        self._icon_char = icon_char
        self._style = style
        self._pressed = False
        self._hovered = False
        self._hover_progress = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setMinimumWidth(100)
        self.setMouseTracking(True)

    def configure(self, bg: str = "", text: str = "", border: str = "", hover_brightness: float = 1.15) -> None:
        pass

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._hovered = True
        if self._style == "cancel":
            self._anim_hover(1.0)
        else:
            self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._hovered = False
        if self._style == "cancel":
            self._anim_hover(0.0)
        else:
            self.update()

    def _anim_hover(self, target: float) -> None:
        self._ha = QPropertyAnimation(self, b"hover_progress", self)
        self._ha.setDuration(250)
        self._ha.setEasingCurve(QEasingCurve.OutCubic)
        self._ha.setStartValue(self._hover_progress)
        self._ha.setEndValue(target)
        self._ha.start()

    def _get_hp(self) -> float:
        return self._hover_progress

    def _set_hp(self, v: float) -> None:
        self._hover_progress = v
        self.update()

    hover_progress = Property(float, _get_hp, _set_hp)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        self._pressed = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rr = h / 2

        if self._style == "cancel":
            red = QColor(252, 70, 100)
            clip = QRectF(0, 0, w * self._hover_progress, h)
            p.setClipRect(clip)
            p.setBrush(red)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(0, 0, w, h), rr, rr)
            p.setClipping(False)
            p.setPen(QPen(red, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1.5, 1.5, w - 3, h - 3), rr, rr)
            p.setPen(QColor("#FFFFFF"))
            f = QFont(["Inter", "Segoe UI", "sans-serif"], 13, QFont.Bold)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self.text())
        else:
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0.0, QColor(77, 54, 208))
            g.setColorAt(1.0, QColor(132, 116, 254))
            p.setBrush(QBrush(g))
            if self._hovered:
                p.setPen(QPen(QColor("#f4f5f2"), 1.5))
            else:
                p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(0, 0, w, h), rr, rr)

            for i in range(3):
                a = int(30 - i * 8)
                c = QColor(77, 54, 208, a)
                p.setPen(QPen(c, 0))
                p.drawRoundedRect(QRectF(-i, -i, w + i * 2, h + i * 2), rr, rr)

            sc = 0.98 if self._pressed else 1.0
            p.save()
            p.translate(w / 2, h / 2)
            p.scale(sc, sc)
            p.translate(-w / 2, -h / 2)

            p.setPen(QColor("#FFFFFF"))
            f = QFont(["Inter", "Segoe UI", "sans-serif"], 13, QFont.Bold)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self.text())

            p.restore()
        p.end()


class _PremiumImagePanel(QWidget):
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
        self._old_pixmap: QPixmap | None = None
        self._transition_progress = 0.0
        self._is_transitioning = False
        self._construction_active = False
        self._corners = 14

        self._overlay = _ImageOverlay(self)
        self._processing_overlay = _ProcessingOverlay(self)
        self._blur_effect = QGraphicsBlurEffect(self)
        self._blur_effect.setBlurRadius(0)
        self.setGraphicsEffect(self._blur_effect)

        self._slide_anim = QPropertyAnimation(self, b"slide_offset", self)
        self._slide_anim.setDuration(ANIM_IMAGE_TRANSITION)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

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
        if old_name and animate and not _reduced() and self._pixmap and not pm.isNull():
            self._old_pixmap = self._pixmap
            self._transition_progress = 0.0
            self._is_transitioning = True
        self._pixmap = pm if not pm.isNull() else None

        if animate and not _reduced():
            self._overlay.start_construction()
            self._overlay.construction_progress = 0.0
            const_anim = QPropertyAnimation(self._overlay, b"construction_progress", self)
            const_anim.setDuration(ANIM_CONSTRUCTION)
            const_anim.setStartValue(0.0)
            const_anim.setEndValue(1.0)
            const_anim.setEasingCurve(QEasingCurve.OutCubic)
            const_anim.start()
            self._blur_effect.setBlurRadius(8)
            blur_anim = QPropertyAnimation(self._blur_effect, b"blurRadius", self)
            blur_anim.setDuration(ANIM_CONSTRUCTION)
            blur_anim.setStartValue(8)
            blur_anim.setEndValue(0)
            blur_anim.setEasingCurve(QEasingCurve.OutCubic)
            blur_anim.start()
            self._construction_active = True
            QTimer.singleShot(ANIM_CONSTRUCTION, self._on_construction_done)
        else:
            self._overlay.start_active()
            self._blur_effect.setBlurRadius(0)
            self._construction_active = False

        self.update()

    def _on_construction_done(self) -> None:
        self._construction_active = False
        self._overlay.start_active()
        self._is_transitioning = False

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

    def show_processing_overlay(self, stage: str, percent: int, eta: str) -> None:
        self._processing_overlay.show_overlay()
        self._processing_overlay.update_info(stage, percent, eta)

    def hide_processing_overlay(self) -> None:
        self._processing_overlay.hide_overlay()

    def show_success(self) -> None:
        self._processing_overlay.hide_overlay()
        self._overlay.start_success()
        QTimer.singleShot(2500, self._overlay.hide_overlay)

    def _get_slide(self) -> float:
        return self._slide_offset

    def _set_slide(self, v: float) -> None:
        self._slide_offset = v
        self.update()

    slide_offset = Property(float, _get_slide, _set_slide)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w = self.width()
        h = self.height()

        preview_h = round(h * 0.62)
        margin = 0
        preview_rect = QRectF(margin, margin, w - margin * 2, preview_h - margin)

        p.setBrush(_tk(COL.bg_secondary))
        p.setPen(QPen(_tk(COL.border), 1))
        p.drawRoundedRect(preview_rect, self._corners, self._corners)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(preview_rect, self._corners, self._corners)
        p.setClipPath(clip_path)

        if self._is_transitioning and self._old_pixmap:
            progress = self._transition_progress
            old_alpha = 1.0 - progress
            new_alpha = progress

            max_w = preview_rect.width() - 40
            max_h = preview_rect.height() - 40
            scaled_old = self._old_pixmap.scaled(round(max_w), round(max_h),
                                                  Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ix = (w - scaled_old.width()) / 2
            iy = (preview_h - scaled_old.height()) / 2

            p.save()
            p.translate(w / 2, preview_h / 2)
            p.scale(1.0 - progress * 0.04, 1.0 - progress * 0.04)
            p.translate(-w / 2, -preview_h / 2)
            p.setOpacity(old_alpha)
            p.drawPixmap(round(ix), round(iy), scaled_old)
            p.restore()

        if self._pixmap:
            pm = self._pixmap
            max_w = preview_rect.width() - 40
            max_h = preview_rect.height() - 40
            scaled = pm.scaled(round(max_w), round(max_h),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ix = (w - scaled.width()) / 2
            iy = (preview_h - scaled.height()) / 2

            if self._is_transitioning:
                p.save()
                p.translate(w / 2, preview_h / 2)
                p.scale(0.96 + 0.04 * new_alpha, 0.96 + 0.04 * new_alpha)
                p.translate(-w / 2, -preview_h / 2)
                p.setOpacity(new_alpha)
                p.drawPixmap(round(ix), round(iy), scaled)
                p.restore()
            else:
                p.drawPixmap(round(ix), round(iy), scaled)

        if self._is_transitioning and self._pixmap and self._old_pixmap:
            self._transition_progress = min(1.0, self._transition_progress + 0.02)
            if self._transition_progress >= 1.0:
                self._is_transitioning = False
                self._old_pixmap = None
            else:
                self.update()

        p.setClipping(False)

        meta_y = preview_h + SP.xl
        info_x = SP.sm + SP.sm

        f = QFont()
        f.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        f.setPointSize(TYP.size_sm)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(_tk(COL.text_primary))
        p.drawText(QRectF(info_x, meta_y, w - info_x * 2, 18), Qt.AlignLeft | Qt.AlignVCenter, self._file_name)

        p.setPen(_tk(COL.text_muted))
        f2 = QFont()
        f2.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        f2.setPointSize(TYP.size_xs)
        p.setFont(f2)
        parts = [self._file_format]
        if self._file_dimensions:
            parts.append(self._file_dimensions)
        if self._file_size_str:
            parts.append(self._file_size_str)
        p.drawText(QRectF(info_x, meta_y + 20, w - info_x * 2, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   "  \u2022  ".join(parts))

        q_y = meta_y + 50
        card_h = 42
        gap = 8
        cr = 10

        p.setBrush(_tk(COL.bg_card))
        p.setPen(QPen(_tk(COL.border), 1))
        p.drawRoundedRect(QRectF(info_x, q_y, w - info_x * 2, card_h), cr, cr)

        p.setPen(_tk(COL.accent))
        p.setBrush(_tk(COL.accent))
        p.drawEllipse(QPointF(info_x + 10, q_y + card_h / 2), 3, 3)

        p.setPen(_tk(COL.text_muted))
        f_label = QFont()
        f_label.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        f_label.setPointSize(8)
        f_label.setWeight(QFont.DemiBold)
        p.setFont(f_label)
        p.drawText(QRectF(info_x + 20, q_y + 4, 60, 14), Qt.AlignLeft | Qt.AlignVCenter, "CURRENT")

        f3 = QFont()
        f3.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        f3.setPointSize(TYP.size_sm)
        f3.setWeight(QFont.Medium)
        p.setFont(f3)
        p.setPen(_tk(COL.text_primary))
        p.drawText(QRectF(info_x + 20, q_y + 18, w - info_x * 2 - 60, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   Path(self._file_name).name if self._file_name else "-")

        if self._next_file:
            ny = q_y + card_h + gap
            p.setBrush(_tk(COL.bg_secondary))
            p.setPen(QPen(_tk(COL.border), 1))
            p.drawRoundedRect(QRectF(info_x, ny, w - info_x * 2, card_h), cr, cr)

            p.setPen(_tk(COL.text_muted))
            p.setBrush(_tk(COL.text_muted))
            p.drawEllipse(QPointF(info_x + 10, ny + card_h / 2), 3, 3)

            p.setFont(f_label)
            p.drawText(QRectF(info_x + 20, ny + 4, 60, 14), Qt.AlignLeft | Qt.AlignVCenter, "NEXT")

            p.setFont(f3)
            p.setPen(_tk(COL.text_muted))
            p.drawText(QRectF(info_x + 20, ny + 18, w - info_x * 2 - 60, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       self._next_file)

        rem_y = q_y + (card_h + gap) * (2 if self._next_file else 1) + SP.md
        p.setPen(_tk(COL.text_muted))
        f4 = QFont()
        f4.setFamilies(["Inter", "Segoe UI", "sans-serif"])
        f4.setPointSize(TYP.size_xs)
        p.setFont(f4)
        remaining = max(0, self._queue_total - self._queue_current + 1)
        p.drawText(QRectF(info_x, rem_y, w - info_x * 2, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   f"Remaining: {remaining}")
        p.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
        self._processing_overlay.setGeometry(self.rect())


class _SlidingCard(QFrame):
    def __init__(self, delay: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._entered = False
        self._delay = delay
        self._opacity_effect: QGraphicsOpacityEffect | None = None

    def animate_in(self) -> None:
        if self._entered:
            return
        self._entered = True
        if _reduced():
            return
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()


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
        self._all_paths: List[str] = []
        self._current_idx: int = 0

        self._bg = _FloatingBg(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QHBoxLayout()
        content.setContentsMargins(SP.xxxl, SP.xl, SP.xxxl, SP.xl)
        content.setSpacing(SP.xxl)

        left = _SlidingCard(0)
        left.setObjectName("Card")
        left.setFixedWidth(380)
        left.setStyleSheet(f"#Card {{ background-color: {COL.bg_card}; border: 1px solid {COL.border}; border-radius: 16px; }}")
        shadow = QGraphicsDropShadowEffect(left)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(_tk_a("#000000", 50))
        left.setGraphicsEffect(shadow)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(SP.xl, SP.xl, SP.xl, SP.lg)
        left_lay.setSpacing(0)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(SP.sm)

        status_dot = QLabel()
        status_dot.setFixedSize(10, 10)
        status_dot.setStyleSheet(
            f"background-color: {COL.accent}; border-radius: 5px;"
            f"border: 2px solid {COL.accent_hover};"
        )
        header_row.addWidget(status_dot)

        header = QLabel("Processing")
        header.setObjectName("PageTitle")
        header_row.addWidget(header)
        header_row.addStretch(1)

        self._count_badge = QLabel("0 / 0")
        self._count_badge.setStyleSheet(
            f"color: {COL.text_muted}; font-size: {TYP.size_xs}px; "
            f"font-weight: 600; letter-spacing: 0.5px; "
            f"background-color: {COL.bg_surface}; border-radius: 8px; "
            f"padding: 3px 10px;"
        )
        header_row.addWidget(self._count_badge)
        left_lay.addLayout(header_row)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("PageSubtitle")
        left_lay.addWidget(self._subtitle)

        left_lay.addSpacing(SP.xl)

        pipe_section = QWidget()
        pipe_section.setStyleSheet("background: transparent;")
        pipe_lay = QVBoxLayout(pipe_section)
        pipe_lay.setContentsMargins(0, 0, 0, 0)
        pipe_lay.setSpacing(SP.sm)

        pipe_header = QHBoxLayout()
        pipe_header.setSpacing(SP.sm)
        dot_ic = QLabel()
        dot_ic.setFixedSize(4, 4)
        dot_ic.setStyleSheet(f"background-color: {COL.accent}; border-radius: 2px;")
        pipe_header.addWidget(dot_ic)
        pipe_label = QLabel("TIMELINE")
        pipe_label.setObjectName("SectionLabel")
        pipe_header.addWidget(pipe_label)
        pipe_header.addStretch(1)
        pipe_lay.addLayout(pipe_header)

        pipe_lay.addSpacing(SP.xs)

        self._nodes: List[_StepperNode] = []
        pipeline_widget = QWidget()
        pipeline_widget.setStyleSheet("background: transparent;")
        pipeline_lay = QVBoxLayout(pipeline_widget)
        pipeline_lay.setContentsMargins(0, 0, 0, 0)
        pipeline_lay.setSpacing(0)

        for i, name in enumerate(STAGE_NAMES):
            node = _StepperNode(i, name)
            self._nodes.append(node)
            row = QHBoxLayout()
            row.setSpacing(0)
            row.addWidget(node)
            row.addStretch(1)
            pipeline_lay.addLayout(row)

        pipe_lay.addWidget(pipeline_widget)
        left_lay.addWidget(pipe_section)

        div = QFrame()
        div.setObjectName("Divider")
        div.setFixedHeight(1)
        left_lay.addWidget(div)

        left_lay.addSpacing(SP.md)

        progress_section = QWidget()
        progress_section.setStyleSheet("background: transparent;")
        progress_lay = QVBoxLayout(progress_section)
        progress_lay.setContentsMargins(0, 0, 0, 0)
        progress_lay.setSpacing(SP.xs)

        progress_header = QHBoxLayout()
        progress_header.setSpacing(SP.sm)
        prog_ic = QLabel()
        prog_ic.setFixedSize(4, 4)
        prog_ic.setStyleSheet(f"background-color: {COL.accent}; border-radius: 2px;")
        progress_header.addWidget(prog_ic)
        prog_label = QLabel("PROGRESS")
        prog_label.setObjectName("SectionLabel")
        progress_header.addWidget(prog_label)
        progress_header.addStretch(1)
        self._perc_label = QLabel("0%")
        self._perc_label.setStyleSheet(
            f"color: {COL.text_secondary}; font-size: {TYP.size_lg}px; "
            f"font-weight: 700; background: transparent;"
        )
        progress_header.addWidget(self._perc_label)
        progress_lay.addLayout(progress_header)

        progress_lay.addSpacing(SP.xs)

        self._bar = _PacmanLoader()
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress_lay.addWidget(self._bar)

        left_lay.addWidget(progress_section)

        status_section = QWidget()
        status_section.setStyleSheet("background: transparent;")
        status_lay = QHBoxLayout(status_section)
        status_lay.setContentsMargins(0, 0, 0, 0)
        status_lay.setSpacing(SP.md)

        status_left = QVBoxLayout()
        status_left.setSpacing(2)
        self._stage_status = QLabel("Idle")
        self._stage_status.setStyleSheet(
            f"color: {COL.text_secondary}; font-size: {TYP.size_md}px; "
            f"font-weight: 600; background: transparent;"
        )
        status_left.addWidget(self._stage_status)
        self._failed_list = QLabel("")
        self._failed_list.setStyleSheet(
            f"color: {COL.error}; font-size: {TYP.size_xs}px; background: transparent;"
        )
        self._failed_list.setWordWrap(True)
        self._failed_list.setVisible(False)
        status_left.addWidget(self._failed_list)
        status_lay.addLayout(status_left, 1)

        status_right = QVBoxLayout()
        status_right.setSpacing(2)
        status_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._eta_label = QLabel("ETA  --:--")
        self._eta_label.setAlignment(Qt.AlignRight)
        self._eta_label.setStyleSheet(
            f"color: {COL.text_muted}; font-family: 'Cascadia Mono', 'Consolas', monospace; "
            f"font-size: {TYP.size_sm}px; background: transparent;"
        )
        status_right.addWidget(self._eta_label)
        status_lay.addLayout(status_right)

        left_lay.addWidget(status_section)

        left_lay.addSpacing(SP.lg)

        btn_div = QFrame()
        btn_div.setObjectName("Divider")
        btn_div.setFixedHeight(1)
        left_lay.addWidget(btn_div)

        left_lay.addSpacing(SP.md)

        controls = QHBoxLayout()
        controls.setSpacing(50)
        controls.addStretch(1)

        self._btn_pause = _PillButton("Pause")
        self._btn_pause.setFixedWidth(130)
        self._btn_pause.clicked.connect(self._toggle_pause)
        self._btn_resume = _PillButton("Resume")
        self._btn_resume.setFixedWidth(130)
        self._btn_resume.clicked.connect(self._toggle_pause)
        self._btn_resume.hide()
        self._btn_cancel = _PillButton("Cancel", style="cancel")
        self._btn_cancel.setFixedWidth(130)
        self._btn_cancel.clicked.connect(self.cancel_requested.emit)

        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_resume)
        controls.addWidget(self._btn_cancel)
        controls.addStretch(1)

        left_lay.addLayout(controls)
        left_lay.addStretch(1)

        content.addWidget(left)

        self._preview = _PremiumImagePanel()
        content.addWidget(self._preview, 1)

        root.addLayout(content, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())

    def begin(self, total: int, paths: Optional[List[str]] = None) -> None:
        self._t0 = time.monotonic()
        self._done = 0
        self._failed = 0
        self._total = max(0, total)
        self._completed = False
        self._stage_index = -1
        self._current_file = ""
        self._previous_files = []
        self._stage_map = _StageLabelMap()
        self._all_paths = list(paths) if paths else []
        self._current_idx = 0

        self._subtitle.setText(f"Batch of {self._total} image{'s' if self._total != 1 else ''}")
        pass
        self._stage_status.setText("Preparing...")
        self._eta_label.setText("ETA  --:--")
        self._count_badge.setText(f"0 / {self._total}")
        self._perc_label.setText("0%")
        self._bar.set_value(0.0)
        self._failed_list.setVisible(False)
        self._failed_list.setText("")
        self._preview._file_name = ""
        self._preview._next_file = ""
        self._preview._queue_current = 0
        self._preview._queue_total = self._total
        self._preview.update()

        for node in self._nodes:
            node.set_state(_StepperNode.State.WAITING, animate=False)

        self._set_paused(False)
        self._enable_controls(True)
        self._timer.start()
        for child in self.findChildren(_SlidingCard):
            child.animate_in()

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
        self._all_paths = []
        self._current_idx = 0
        for node in self._nodes:
            node.set_state(_StepperNode.State.WAITING, animate=False)
        self._bar.set_value(0.0)
        self._perc_label.setText("0%")
        self._stage_status.setText("Idle")
        self._eta_label.setText("ETA  --:--")
        self._count_badge.setText("0 / 0")
        self._subtitle.setText("")
        self._failed_list.setVisible(False)
        self._failed_list.setText("")
        self._preview.hide_processing_overlay()

    def on_stage(self, stage: str) -> None:
        if stage == "Completed":
            self._stage_status.setText("Complete")
            return

        idx = _STAGE_LABEL_TO_INDEX.get(stage, -1)
        if idx < 0:
            return

        if idx > self._stage_index:
            self._advance_stages(idx)

        if idx < len(self._nodes) and self._nodes[idx].state is _StepperNode.State.WAITING:
            self._nodes[idx].set_state(_StepperNode.State.ACTIVE)
            self._nodes[idx].set_status("Processing...")

        if idx < len(STAGE_NAMES):
            self._stage_status.setText(STAGE_NAMES[idx])
            self._preview.show_processing_overlay(
                STAGE_NAMES[idx],
                round((idx + 1) / len(STAGE_NAMES) * 100),
                self._eta_label.text()
            )

    def _advance_stages(self, new_idx: int) -> None:
        start = max(0, self._stage_index)
        for pi in range(start, new_idx):
            if pi < len(self._nodes):
                self._nodes[pi].set_state(_StepperNode.State.COMPLETED)
                eta = self._eta_label.text().replace("ETA ", "").strip()
                if eta and eta != "--:--":
                    self._nodes[pi].set_time(f"Completed in {eta}")
        self._stage_index = new_idx

    def _mark_all_completed(self) -> None:
        for node in self._nodes:
            node.set_state(_StepperNode.State.COMPLETED, animate=False)
            eta = self._eta_label.text().replace("ETA ", "").strip()
            if eta and eta != "--:--":
                node.set_time(f"Completed in {eta}")

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
            self._current_idx = max(self._current_idx, len(self._previous_files))
        self._current_file = file_name

        self._preview.set_image(file_name)

        p = Path(file_name)
        fmt = p.suffix.lstrip(".").upper() or "UNKNOWN"
        dims = ""
        size_str = ""
        try:
            from PIL import Image
            with Image.open(file_name) as img:
                w, h = img.size
                dims = f"{w} x {h}"
        except Exception:
            pass
        try:
            sz = os.path.getsize(file_name)
            if sz < 1024:
                size_str = f"{sz} B"
            elif sz < 1024 * 1024:
                size_str = f"{sz / 1024:.1f} KB"
            else:
                size_str = f"{sz / (1024 * 1024):.1f} MB"
        except Exception:
            pass
        self._preview.set_metadata(fmt, dims, size_str)

        current = len(self._previous_files) + 1
        next_file = ""
        if self._all_paths:
            idx = self._all_paths.index(file_name) if file_name in self._all_paths else -1
            if idx >= 0 and idx + 1 < len(self._all_paths):
                next_file = Path(self._all_paths[idx + 1]).name
        self._preview.set_queue(current, self._total, next_file)

    def on_progress(self, done: int, total: int, current_file: str) -> None:
        self._done = done
        self._total = max(0, total)
        pct = (done / self._total * 100) if self._total > 0 else 0.0
        self._bar.set_value(pct / 100.0)
        self._perc_label.setText(f"{round(pct)}%")
        self._count_badge.setText(f"{done} / {self._total}")
        if current_file and current_file != self._current_file:
            self._current_file = current_file
            self._preview.set_image(current_file)
            current = len(self._previous_files) + 1
            next_file = ""
            if self._all_paths:
                idx = self._all_paths.index(current_file) if current_file in self._all_paths else -1
                if idx >= 0 and idx + 1 < len(self._all_paths):
                    next_file = Path(self._all_paths[idx + 1]).name
            self._preview.set_queue(current, self._total, next_file)
        self._recalc_eta()

    def on_log(self, level: str, logger: str, message: str) -> None:
        pass

    def on_image_failed(self, file_name: str, message: str) -> None:
        self._failed += 1
        idx = self._stage_index if self._stage_index >= 0 else 0
        if idx < len(self._nodes):
            self._nodes[idx].set_state(_StepperNode.State.FAILED)
        fails = []
        if self._failed_list.text():
            fails = self._failed_list.text().split("\n")
        name = Path(file_name).name if file_name else file_name
        fails.append(f"{name}: {message}")
        if len(fails) > 5:
            fails = fails[-5:]
        self._failed_list.setText("\n".join(fails))
        self._failed_list.setVisible(True)

    def on_summary(self, summary: RunSummary) -> None:
        self.end()
        if not summary.cancelled:
            self._mark_all_completed()
            self._stage_status.setText("Completed" if summary.all_succeeded else "Completed with errors")
            self._preview.show_success()
            if not summary.all_succeeded:
                self._stage_status.setStyleSheet(
                    f"color: {COL.warning}; font-size: {TYP.size_md}px; font-weight: 600; background: transparent;"
                )
        else:
            self._stage_status.setText("Cancelled")
            self._stage_status.setStyleSheet(
                f"color: {COL.warning}; font-size: {TYP.size_md}px; font-weight: 600; background: transparent;"
            )
        self._completed = True
        self._preview.hide_processing_overlay()
        if _reduced():
            self._on_completion_done()

    def on_failed(self, message: str) -> None:
        self._stage_status.setText("Failed")
        self._stage_status.setStyleSheet(
            f"color: {COL.error}; font-size: {TYP.size_md}px; font-weight: 600; background: transparent;"
        )
        self._failed_list.setText(message)
        self._failed_list.setVisible(True)
        self._preview.hide_processing_overlay()
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
