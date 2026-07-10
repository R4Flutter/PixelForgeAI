"""
splash.py
---------
Branded launch splash for PixelForgeAI — a faithful PySide6 port of the
"background paths" web component.

Two opposing fields of 36 cubic Bezier paths each (the component's
``position`` +1 and −1, 72 lines total) draw themselves on across a
staggered cascade (the ``pathLength`` 0.3 → 1 entrance), then live
forever: dashes slip along each curve (the ``pathOffset`` [0,1,0] shift)
while opacity breathes (the [0.3, 0.6, 0.3] keyframe). Tinted along the
indigo → violet → magenta brand gradient — never the source's neutral
slate — so the splash belongs to the app, not the template. The wordmark
enters letter-by-letter with a spring settle and a gradient clipping fill.
Auto-transitions to the main window after 5 seconds.

No external dependencies; everything ships in the existing PyInstaller
bundle (QPainter + QSvgRenderer only).

ui-ux notes
  * One ambient system (the path field) + two focal marks (logo, title) —
    no excessive motion.
  * Animation is paint-only (transform/opacity), never layout.
  * Honors a reduced-motion env switch: full field, settled title, enabled
    Enter button, no timers.
  * Opacity never lingers below ~0.16 (stays clearly visible or fully gone).
  * Enter is gated until the title has settled AND a minimum hold has
    elapsed, so the entrance is seen before it can be dismissed; the
    reduced-motion path enables it immediately.
  * Fade-out is ~70% of the entrance (350ms vs the leading animations) so
    the hand-off to the main window feels responsive.
"""
from __future__ import annotations

import math
import os
from typing import List, Optional, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Signal,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.state import paths as app_paths
from backend.updater import APP_NAME, APP_VERSION

# --- Ambient tuning ---------------------------------------------------------
_PATH_COUNT = 36                # per direction (×2 directions = 72 total)
_PULSE_PERIOD = 6.0             # seconds per opacity breathe cycle
_FLOW_SPEED = 16.0              # dash px travelling per second along each path
_DASH_PATTERN = (3.0, 6.5)      # ambient flowing dashes (pen-width units)
_FRAME_MS = 40                  # ~25 fps — ambient, not chasing 60
_BUILDUP_S = 1.4                # pathLength draw-on duration
_DRAW_START = 0.3               # initial fraction drawn (matches source)
_ENTRY_MS = 500                 # content fade-in
_EXIT_MS = 350                  # hand-off fade-out

_BASE_ALPHA = 0.16
_AMP_ALPHA = 0.18

# Title
_TITLE_FONT_PX = 44
_TITLE_RISE_PX = 34             # how far each letter rises from below
_TITLE_STEP_S = 0.035           # per-letter stagger (wordIndex*0.1 folded in)
_TITLE_LETTER_DUR = 0.7         # settle time per letter (spring ≈ near-critical)

# Brand gradient stops (matches assets/logo.svg).
_BRAND_STOPS: List[Tuple[float, QColor]] = [
    (0.00, QColor("#6366F1")),
    (0.55, QColor("#8B5CF6")),
    (1.00, QColor("#D946EF")),
]


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


def _brand_color(frac: float, shift: float = 0.0) -> QColor:
    """Interpolate along the brand gradient for ``frac`` in [0, 1]."""
    f = (frac + shift) % 1.0
    for i in range(len(_BRAND_STOPS) - 1):
        t0, c0 = _BRAND_STOPS[i]
        t1, c1 = _BRAND_STOPS[i + 1]
        if f <= t1:
            local = (f - t0) / max(1e-6, (t1 - t0))
            return _lerp_color(c0, c1, local)
    return _BRAND_STOPS[-1][1]


def _reduced_motion() -> bool:
    """Honor an explicit opt-out for users who want a still splash."""
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _ease_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3


# --------------------------------------------------------------------------- #
# Path field
# --------------------------------------------------------------------------- #
class _PathLayer:
    """One floating Bezier path plus its animation phase anchors."""

    __slots__ = ("path", "color", "width", "phase", "length")

    def __init__(self, path: QPainterPath, color: QColor,
                 width: float, phase: float, length: float) -> None:
        self.path = path
        self.color = color
        self.width = width
        self.phase = phase
        self.length = length


def _build_layer(position: int) -> List[_PathLayer]:
    """Build one 36-path direction. ``position`` ∈ {+1, -1} mirrors the field."""
    layers: List[_PathLayer] = []
    for i in range(_PATH_COUNT):
        k = i * 5 * position
        p = QPainterPath()
        sx, sy = -(380 - k), -(189 + i * 6)
        c2x, c2y = -(312 - k), (216 - i * 6)
        e1x, e1y = (152 - k), (343 - i * 6)
        c3x, c3y = (616 - k), (470 - i * 6)
        c4x, c4y = (684 - k), (875 - i * 6)
        p.moveTo(sx, sy)
        p.cubicTo(sx, sy, c2x, c2y, e1x, e1y)
        p.cubicTo(c3x, c3y, c4x, c4y, c4x, c4y)
        frac = i / max(1, _PATH_COUNT - 1)
        # The mirrored direction shifts a half-step along the gradient so the
        # two fields weave into each other rather than echoing.
        color = _brand_color(frac, shift=0.0 if position > 0 else 0.22)
        layers.append(_PathLayer(p, color, 0.5 + i * 0.03, frac, p.length()))
    return layers


# --------------------------------------------------------------------------- #
# Animated wordmark
# --------------------------------------------------------------------------- #
class _AnimatedTitle(QWidget):
    """Wordmark painted letter-by-letter with a spring settle + gradient fill.

    Faithful to the source's per-letter entrance (initial y=100, opacity 0 →
    spring to 0 / 1 with stagger delay ``wordIndex*0.1 + letterIndex*0.03``).
    The source spring (stiffness 150, damping 25) is near-critical / lightly
    overdamped → ``_ease_out_cubic`` reproduces its settle without overshoot,
    and the gradient fill stands in for the source's ``bg-clip-text``.
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SplashTitle")
        self._text = text
        self._reduced = _reduced_motion()
        self._start: Optional[float] = None
        self._t = 0.0

        self._font = QFont("Segoe UI")
        self._font.setPixelSize(_TITLE_FONT_PX)
        self._font.setWeight(QFont.Bold)
        try:
            self._font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -1.2)
        except Exception:
            pass

        fm = QFontMetrics(self._font)
        self._ascent = fm.ascent()
        self._glyphs: List[QPainterPath] = []
        self._adv: List[int] = []
        total = 0
        for ch in text:
            gp = QPainterPath()
            gp.addText(0, 0, self._font, ch)
            self._glyphs.append(gp)
            adv = fm.horizontalAdvance(ch)
            self._adv.append(adv)
            total += adv
        self._total_w = max(1, total)
        self._last_delay = (max(0, len(text) - 1)) * _TITLE_STEP_S
        h = fm.height() + _TITLE_RISE_PX + 4
        self.setFixedSize(int(self._total_w) + 8, h)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_time(self, t: float) -> None:
        if self._start is None:
            self._start = t
        self._t = t
        self.update()

    def settled(self) -> bool:
        if self._reduced:
            return True
        if self._start is None:
            return False
        return (self._t - self._start) >= self._last_delay + _TITLE_LETTER_DUR

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        baseline = self._ascent + _TITLE_RISE_PX // 2

        # Horizontal white → white/82 clip-text gradient (source dark mode).
        grad = QLinearGradient(0, 0, self._total_w, 0)
        grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        grad.setColorAt(1.0, QColor(255, 255, 255, int(255 * 0.82)))
        brush = QBrush(grad)

        x = 0.0
        for i, _ in enumerate(self._text):
            delay = i * _TITLE_STEP_S
            if self._reduced:
                yy, alpha = 0.0, 1.0
            else:
                local = max(0.0, min(1.0,
                            (self._t - (self._start or 0.0) - delay) / _TITLE_LETTER_DUR))
                eased = _ease_out_cubic(local)
                yy = _TITLE_RISE_PX * (1.0 - eased)
                alpha = eased
            gp = QPainterPath(self._glyphs[i])
            gp.translate(x, baseline + yy)
            p.setOpacity(alpha)
            p.fillPath(gp, brush)
            x += self._adv[i]
        p.setOpacity(1.0)
        p.end()

# --------------------------------------------------------------------------- #
# Splash window
# --------------------------------------------------------------------------- #
class SplashScreen(QWidget):
    """Frameless branded splash. Auto-transitions to main window after 5s.
    ``entered`` also fires on Return/Space/Escape key press.
    """

    entered = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("SplashRoot")
        self.setFixedSize(800, 500)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._elapsed = 0.0
        self._reduced = _reduced_motion()
        self._layers: List[_PathLayer] = []
        self._field_transform = QTransform()
        self._field_scale = 1.0
        self._handoff_done = False
        self._logo: QPixmap = self._render_logo(72)

        self._build_field()
        self._build_content()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)

        self._clock = QElapsedTimer()
        self._auto_enter = QTimer(self)
        self._auto_enter.setSingleShot(True)
        self._auto_enter.timeout.connect(self._trigger_enter)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def _build_content(self) -> None:
        col = QWidget(self)
        col.setObjectName("SplashContent")
        col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addStretch(1)

        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        logo = QLabel()
        logo.setPixmap(self._logo)
        logo.setAlignment(Qt.AlignCenter)
        logo_row.addWidget(logo)
        logo_row.addStretch(1)
        v.addLayout(logo_row)

        v.addSpacing(22)

        title_row = QHBoxLayout()
        title_row.addStretch(1)
        self._title = _AnimatedTitle(APP_NAME)
        title_row.addWidget(self._title)
        title_row.addStretch(1)
        v.addLayout(title_row)

        v.addSpacing(8)

        tag = QLabel("AI IMAGE PIPELINE")
        tag.setObjectName("SplashTag")
        tag.setAlignment(Qt.AlignCenter)
        v.addWidget(tag)

        v.addSpacing(36)

        v.addStretch(1)

        foot = QLabel(f"v{APP_VERSION}")
        foot.setObjectName("SplashVersion")
        foot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        foot_row = QHBoxLayout()
        foot_row.setContentsMargins(0, 0, 24, 0)
        foot_row.addStretch(1)
        foot_row.addWidget(foot)
        v.addLayout(foot_row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 16)
        outer.setSpacing(0)
        outer.addWidget(col)
        self._content = col

        # Content fade-in so the window paints before the marks resolve.
        self._content_effect = QGraphicsOpacityEffect(self._content)
        self._content_effect.setOpacity(0.0 if not self._reduced else 1.0)
        self._content.setGraphicsEffect(self._content_effect)
        self._entry = QVariantAnimation(self)
        self._entry.setDuration(_ENTRY_MS)
        self._entry.setStartValue(0.0)
        self._entry.setEndValue(1.0)
        self._entry.setEasingCurve(QEasingCurve.OutCubic)
        self._entry.valueChanged.connect(self._content_effect.setOpacity)

    def _render_logo(self, size: int) -> QPixmap:
        pm = QPixmap(size * 2, size * 2)  # 2× for crisp HiDPI
        pm.fill(Qt.transparent)
        renderer = QSvgRenderer(str(app_paths().asset("logo.svg")))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
        painter.end()
        return pm

    def _build_field(self) -> None:
        """Reconstruct the 72-path field (two directions) and a framing transform."""
        self._layers = _build_layer(1) + _build_layer(-1)
        brs = [layer.path.boundingRect() for layer in self._layers]
        min_x = min(r.left() for r in brs)
        max_x = max(r.right() for r in brs)
        min_y = min(r.top() for r in brs)
        max_y = max(r.bottom() for r in brs)
        bw = max(1.0, max_x - min_x)
        bh = max(1.0, max_y - min_y)
        cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        w, h = self.width(), self.height()
        scale = max(w / bw, h / bh) * 1.12
        self._field_scale = scale
        t = QTransform()
        t.translate(w / 2.0, h / 2.0)
        t.scale(scale, scale)
        t.translate(-cx, -cy)
        self._field_transform = t

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Centre on the screen that owns the splash.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            self.move(g.center() - self.rect().center())
        if not self._reduced:
            self._timer.start(_FRAME_MS)
        self._entry.start()
        self._clock.start()
        self._auto_enter.start(5000)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._auto_enter.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Escape):
            self._trigger_enter()
            event.accept()
            return
        super().keyPressEvent(event)

    def _trigger_enter(self) -> None:
        if self._handoff_done:
            return
        self._handoff_done = True
        self._auto_enter.stop()
        self.entered.emit()

    def finish_and_close(self, window: QWidget) -> None:
        """Reveal the main window, then fade the splash out and delete it."""
        window.show()
        window.raise_()
        window.activateWindow()
        self._timer.stop()
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(_EXIT_MS)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.InCubic)
        fade.finished.connect(self.close)
        fade.finished.connect(self.deleteLater)
        fade.start()
        self._fade = fade  # keep a reference so it isn't GC'd mid-run

    # ------------------------------------------------------------------ #
    # Frame
    # ------------------------------------------------------------------ #
    def _on_tick(self) -> None:
        if self._reduced:
            return
        self._elapsed = self._clock.elapsed() / 1000.0
        self._title.set_time(self._elapsed)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#0B0C10"))

        # Soft brand glow anchors the logo against the field.
        glow = QRadialGradient(self.width() / 2.0, self.height() / 2.0 - 24, 290)
        glow.setColorAt(0.0, QColor(99, 102, 241, 70))
        glow.setColorAt(0.55, QColor(139, 92, 246, 22))
        glow.setColorAt(1.0, QColor(11, 12, 16, 0))
        p.fillRect(self.rect(), glow)

        if not self._layers:
            p.end()
            return

        p.save()
        p.setTransform(self._field_transform, combine=False)
        t = self._elapsed
        for layer in self._layers:
            pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * (t / _PULSE_PERIOD + layer.phase))

            pen = QPen()
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setWidthF(layer.width * 2.4)
            c = layer.color

            unit_len = layer.length / max(1e-6, layer.width * 2.4)

            if self._reduced:
                alpha = _BASE_ALPHA + _AMP_ALPHA * 0.5
            else:
                delay = layer.phase * 0.45  # small cascade across the field
                local = max(0.0, min(1.0, (t - delay) / _BUILDUP_S))
                eased = _ease_out_cubic(local)
                drawn_fm = _DRAW_START + (1.0 - _DRAW_START) * eased
                breath = _BASE_ALPHA + _AMP_ALPHA * pulse
                alpha = breath * (0.35 + 0.65 * eased)

                if drawn_fm < 1.0:
                    dash = max(1e-4, drawn_fm * unit_len)
                    pen.setDashPattern([dash, unit_len * 3.0])
                    pen.setDashOffset(0.0)
                else:
                    pen.setDashPattern(list(_DASH_PATTERN))
                    pen.setDashOffset(-(t * _FLOW_SPEED + layer.phase * 12.0))

            pen.setColor(QColor(c.red(), c.green(), c.blue(),
                                 int(max(0.0, min(1.0, alpha)) * 255)))
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(layer.path)
        p.restore()
        p.end()
