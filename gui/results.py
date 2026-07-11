from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QUrl,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPauseAnimation,
    QPointF, QRectF, QSize, Property, QEvent,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QFontMetrics,
    QEnterEvent, QMouseEvent, QWheelEvent, QAction, QDesktopServices,
    QClipboard,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QMenu, QApplication,
)

from components.icons import icon, pixmap
from core.event_bus import EventBus
from models.pipeline_result import ImageResultData, PipelineResult

from design_system.tokens.colors import Colors as C
from design_system.tokens.spacing import Spacing as S
from design_system.tokens.typography import Typography as T


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _fmt_time(seconds: float) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def _tk(hex_str: str) -> QColor:
    return QColor(hex_str)


def _brighten(c: QColor, factor: float = 1.25) -> QColor:
    h, s, v, a = c.getHsvF()
    return QColor.fromHsvF(h, max(0.0, min(1.0, s * 0.85)), max(0.0, min(1.0, v * factor)))


_PIPELINE_STEPS = ["Load", "Remove BG", "Upscale", "Resize", "Save"]


class _HeroCard(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._succeeded = True
        self._cancelled = False
        self._total = 0
        self._failed = 0
        self._elapsed = 0.0
        self._entrance_offset = 40.0
        self._entrance_opacity = 0.0
        self.setFixedHeight(180)
        self.setMinimumWidth(600)

    def set_data(self, succeeded: bool, cancelled: bool, total: int, failed: int, elapsed: float) -> None:
        self._succeeded = succeeded
        self._cancelled = cancelled
        self._total = total
        self._failed = failed
        self._elapsed = elapsed
        self.update()

    def animate_in(self) -> QPropertyAnimation:
        a = QPropertyAnimation(self, b"hero_offset", self)
        a.setDuration(600)
        a.setStartValue(40.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        return a

    def _get_ho(self) -> float:
        return self._entrance_offset

    def _set_ho(self, v: float) -> None:
        self._entrance_offset = v
        self._entrance_opacity = max(0.0, 1.0 - v / 40.0)
        self.update()

    hero_offset = Property(float, _get_ho, _set_ho)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.translate(0, self._entrance_offset)
        p.setOpacity(self._entrance_opacity)

        bg = QColor(C.bg_card)
        p.setBrush(bg)
        p.setPen(QPen(QColor(C.border), 1))
        pr = 14
        p.drawRoundedRect(1, 1, w - 2, h - 2, pr, pr)

        grad = QLinearGradient(0, h - 4, w, h - 4)
        if self._succeeded and not self._cancelled:
            grad.setColorAt(0.0, QColor(C.success))
            grad.setColorAt(1.0, QColor(C.gradient_end))
        elif self._cancelled:
            grad.setColorAt(0.0, QColor(C.warning))
            grad.setColorAt(1.0, QColor(C.gradient_end))
        else:
            grad.setColorAt(0.0, QColor(C.error))
            grad.setColorAt(1.0, QColor(C.gradient_end))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(pr + 2, h - 4, w - pr * 2 - 4, 3, 1.5, 1.5)
        p.drawPath(bar_path)

        gb_size = 72
        gb_x = S.xxl
        gb_y = (h - gb_size) / 2
        cx = gb_x + gb_size / 2
        cy = gb_y + gb_size / 2

        status_color = (
            QColor(C.success) if self._succeeded and not self._cancelled
            else QColor(C.warning) if self._cancelled
            else QColor(C.error)
        )

        glow_r = gb_size / 2 + 6
        glow = QRadialGradient(cx, cy, glow_r)
        ct = status_color.toTuple()
        glow.setColorAt(0.0, QColor(ct[0], ct[1], ct[2], 40))
        glow.setColorAt(0.5, QColor(ct[0], ct[1], ct[2], 15))
        glow.setColorAt(1.0, QColor(ct[0], ct[1], ct[2], 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        p.setBrush(status_color)
        p.drawEllipse(QPointF(cx, cy), gb_size / 2 - 2, gb_size / 2 - 2)

        p.setPen(QPen(QColor("#FFFFFF"), 3))
        p.setBrush(Qt.NoBrush)
        if self._succeeded and not self._cancelled:
            chk = QPainterPath()
            chk.moveTo(cx - 10, cy + 1)
            chk.lineTo(cx - 3, cy + 7)
            chk.lineTo(cx + 10, cy - 6)
            p.drawPath(chk)
        elif self._cancelled:
            f = QFont(["Inter", "Segoe UI"], 20, QFont.Bold)
            p.setFont(f)
            p.setPen(QPen(QColor("#FFFFFF"), 0))
            p.drawText(QRectF(gb_x, gb_y, gb_size, gb_size), Qt.AlignCenter, "\u23F9")
        else:
            off = 8
            p.drawLine(QPointF(cx - off, cy - off), QPointF(cx + off, cy + off))
            p.drawLine(QPointF(cx + off, cy - off), QPointF(cx - off, cy + off))

        title_x = gb_x + gb_size + S.lg
        title_y = S.xxl + 8
        f = QFont(["Inter", "Segoe UI"], 22, QFont.Bold)
        p.setFont(f)
        p.setPen(QColor(C.text_primary))
        p.drawText(title_x, title_y, (
            "Processing Complete" if self._succeeded and not self._cancelled
            else "Processing Cancelled" if self._cancelled
            else "Completed with Errors"
        ))

        f2 = QFont(["Inter", "Segoe UI"], 12, QFont.Medium)
        p.setFont(f2)
        p.setPen(QColor(C.text_secondary))
        subtitle = (
            "Every image processed successfully."
            if self._succeeded and not self._cancelled
            else "The operation was cancelled before completion."
            if self._cancelled
            else             f"{self._failed} image(s) could not be processed."
        )
        p.drawText(QRectF(title_x, title_y + 32, w - title_x - S.xxl, 24), Qt.AlignLeft | Qt.AlignTop, subtitle)

        right_x = w - S.xxl
        f3 = QFont(["Cascadia Mono", "Consolas", "monospace"], 20, QFont.Bold)
        p.setFont(f3)
        p.setPen(QColor(C.text_primary))
        time_str = _fmt_time(self._elapsed)
        tw = p.fontMetrics().horizontalAdvance(time_str)
        p.drawText(QRectF(right_x - tw, S.xxl, tw, 28), Qt.AlignRight | Qt.AlignTop, time_str)

        f4 = QFont(["Inter", "Segoe UI"], 9, QFont.Medium)
        f4.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        p.setFont(f4)
        p.setPen(QColor(C.text_muted))
        p.drawText(QRectF(right_x - 100, S.xxl + 32, 100, 16), Qt.AlignRight | Qt.AlignTop, "DURATION")

        if self._elapsed > 0:
            throughput = self._total / self._elapsed
            tp_str = f"{throughput:.1f}/s"
            f5 = QFont(["Cascadia Mono", "Consolas", "monospace"], 14, QFont.Bold)
            p.setFont(f5)
            p.setPen(QColor(C.text_primary))
            tp_w = p.fontMetrics().horizontalAdvance(tp_str)
            p.drawText(QRectF(right_x - tp_w, S.xxl + 62, tp_w, 24), Qt.AlignRight | Qt.AlignTop, tp_str)

            f6 = QFont(["Inter", "Segoe UI"], 9, QFont.Medium)
            f6.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
            p.setFont(f6)
            p.setPen(QColor(C.text_muted))
            p.drawText(QRectF(right_x - 100, S.xxl + 86, 100, 16), Qt.AlignRight | Qt.AlignTop, "THROUGHPUT")

        p.end()

    def total_success(self) -> int:
        return 0


class _StatTile(QWidget):
    def __init__(self, value: str, label: str, micro: str, color: QColor, accent_color: str, parent=None) -> None:
        super().__init__(parent)
        self._value = value
        self._label = label
        self._micro = micro
        self._color = color
        self._accent = accent_color
        self._hovered = False
        self._entrance_offset = 30.0
        self._entrance_opacity = 0.0
        self._lift = 0.0
        self.setFixedSize(180, 110)
        self.setCursor(Qt.PointingHandCursor)

    def set_value(self, text: str) -> None:
        self._value = text
        self.update()

    def animate_in(self, delay: int = 0) -> QSequentialAnimationGroup:
        a = QPropertyAnimation(self, b"tile_offset", self)
        a.setDuration(500)
        a.setStartValue(30.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        g = QSequentialAnimationGroup(self)
        g.addPause(delay)
        g.addAnimation(a)
        return g

    def _get_to(self) -> float:
        return self._entrance_offset

    def _set_to(self, v: float) -> None:
        self._entrance_offset = v
        self._entrance_opacity = max(0.0, 1.0 - v / 30.0)
        self.update()

    tile_offset = Property(float, _get_to, _set_to)

    def enterEvent(self, event) -> None:
        self._hovered = True
        if not _reduced():
            a = QPropertyAnimation(self, b"lift", self)
            a.setDuration(200)
            a.setStartValue(0.0)
            a.setEndValue(-4.0)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.start()
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        if not _reduced():
            a = QPropertyAnimation(self, b"lift", self)
            a.setDuration(200)
            a.setStartValue(self._lift)
            a.setEndValue(0.0)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.start()
        self.update()

    def _get_lift(self) -> float:
        return self._lift

    def _set_lift(self, v: float) -> None:
        self._lift = v
        self.update()

    lift = Property(float, _get_lift, _set_lift)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.translate(0, self._lift)
        p.setOpacity(self._entrance_opacity)
        p.translate(0, self._entrance_offset)

        bg = QColor(C.bg_card)
        if self._hovered:
            bg = bg.lighter(115)
        p.setBrush(bg)
        border_c = QColor(C.border_hover) if self._hovered else QColor(C.border)
        p.setPen(QPen(border_c, 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, S.card_radius, S.card_radius)

        acc_grad = QLinearGradient(0, 0, 0, h)
        acc_grad.setColorAt(0.0, self._color)
        acc_grad.setColorAt(1.0, QColor(self._accent))
        p.setBrush(QBrush(acc_grad))
        p.setPen(Qt.NoPen)
        bar = QPainterPath()
        bar.addRoundedRect(0, 0, 4, h - 1, 2, 2)
        p.drawPath(bar)

        f = QFont(["Cascadia Mono", "Consolas", "monospace"], 28, QFont.Bold)
        p.setFont(f)
        val_rect = QRectF(S.xl, S.sm, w - S.xl * 2, 44)
        p.setPen(QColor(C.text_primary))
        p.drawText(val_rect, Qt.AlignLeft | Qt.AlignBottom, self._value)

        f2 = QFont(["Inter", "Segoe UI"], 9, QFont.Medium)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f2)
        lbl_rect = QRectF(S.xl, 56, w - S.xl * 2, S.lg)
        p.setPen(QColor(C.text_muted))
        p.drawText(lbl_rect, Qt.AlignLeft | Qt.AlignVCenter, self._label.upper())

        f3 = QFont(["Inter", "Segoe UI"], 8, QFont.Medium)
        p.setFont(f3)
        p.setPen(self._color)
        micro_rect = QRectF(S.xl, 74, w - S.xl * 2, S.md)
        p.drawText(micro_rect, Qt.AlignLeft | Qt.AlignVCenter, self._micro)

        p.end()


class _PipelineSummary(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._completed_steps: List[str] = []
        self._entrance_offset = 20.0
        self._entrance_opacity = 0.0
        self.setFixedHeight(50)

    def set_completed(self, steps: List[str]) -> None:
        self._completed_steps = steps
        self.update()

    def animate_in(self, delay: int = 0) -> QSequentialAnimationGroup:
        a = QPropertyAnimation(self, b"ps_offset", self)
        a.setDuration(400)
        a.setStartValue(20.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        g = QSequentialAnimationGroup(self)
        g.addPause(delay)
        g.addAnimation(a)
        return g

    def _get_pso(self) -> float:
        return self._entrance_offset

    def _set_pso(self, v: float) -> None:
        self._entrance_offset = v
        self._entrance_opacity = max(0.0, 1.0 - v / 20.0)
        self.update()

    ps_offset = Property(float, _get_pso, _set_pso)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.translate(0, self._entrance_offset)
        p.setOpacity(self._entrance_opacity)

        p.setBrush(QColor(C.bg_card))
        p.setPen(QPen(QColor(C.border), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        steps = _PIPELINE_STEPS
        total_w = sum(self._pill_w(step, p) for step in steps) + (len(steps) - 1) * S.md
        start_x = (w - total_w) / 2
        cy = h / 2

        x = start_x
        for step in steps:
            done = step in self._completed_steps
            pw = self._pill_w(step, p)
            ph = 28

            if done:
                bg_c = QColor(C.success)
                bg_c.setAlpha(25)
                p.setBrush(bg_c)
                p.setPen(QPen(QColor(C.success), 1))
            else:
                p.setBrush(QColor(C.bg_surface))
                p.setPen(QPen(QColor(C.border), 1))

            p.drawRoundedRect(QRectF(x, cy - ph / 2, pw, ph), ph / 2, ph / 2)

            f = QFont(["Inter", "Segoe UI"], 9, QFont.Semibold)
            p.setFont(f)
            if done:
                p.setPen(QColor(C.success))
                icon_text = "\u2713 "
            else:
                p.setPen(QColor(C.text_muted))
                icon_text = ""
            p.drawText(QRectF(x, cy - ph / 2, pw, ph), Qt.AlignCenter, icon_text + step)

            x += pw + S.md

        p.end()

    def _pill_w(self, text: str, p: QPainter) -> int:
        f = QFont(["Inter", "Segoe UI"], 9, QFont.Semibold)
        p.setFont(f)
        return p.fontMetrics().horizontalAdvance(text) + 28


class _FailedFileCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("FailedCard")
        self._collapsed = False
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._native = QFrame()
        self._native.setObjectName("Card")
        nat_layout = QVBoxLayout(self._native)
        nat_layout.setContentsMargins(S.xl, S.lg, S.xl, S.lg)
        nat_layout.setSpacing(S.sm)

        header_row = QHBoxLayout()
        header_row.setSpacing(S.xs)

        self._title = QLabel("FAILED FILES")
        self._title.setObjectName("SectionLabel")
        header_row.addWidget(self._title)

        self._count_badge = QLabel("0")
        self._count_badge.setStyleSheet(
            f"color:{C.error}; font-size:{T.size_xs}px; font-weight:700; "
            f"background:#2A1018; border-radius:8px; padding:2px 8px;"
        )
        header_row.addWidget(self._count_badge)
        header_row.addStretch(1)

        self._toggle_btn = QPushButton("\u25BC")
        self._toggle_btn.setObjectName("GhostButton")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self._toggle_btn)
        nat_layout.addLayout(header_row)

        self._list_widget = QListWidget()
        self._list_widget.setFrameShape(QListWidget.NoFrame)
        self._list_widget.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; }}"
            f"QListWidget::item {{ color: {C.text_primary}; padding: {S.xs}px {S.xs}px; "
            f"border-bottom: 1px solid {C.border}; font-size: {T.size_sm}px; }}"
        )
        nat_layout.addWidget(self._list_widget)
        outer.addWidget(self._native)

    def set_files(self, files: List[str]) -> None:
        self._list_widget.clear()
        for f in files:
            item = QListWidgetItem(f)
            self._list_widget.addItem(item)
        self._count_badge.setText(str(len(files)))
        self.setVisible(len(files) > 0)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._list_widget.setVisible(not self._collapsed)
        self._toggle_btn.setText("\u25B6" if self._collapsed else "\u25BC")


class _OutputFolderTile(QWidget):
    path_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._folder_path = ""
        self.setFixedHeight(72)
        self.setCursor(Qt.PointingHandCursor)

    def set_path(self, path: str) -> None:
        self._folder_path = path
        self.update()

    def _open(self) -> None:
        if not self._folder_path:
            return
        try:
            if sys.platform == "win32":
                os.startfile(self._folder_path)
        except Exception:
            pass

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._open()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setBrush(QColor(C.bg_card))
        p.setPen(QPen(QColor(C.border), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, S.card_radius, S.card_radius)

        f_lbl = QFont(["Inter", "Segoe UI"], 8, QFont.Medium)
        f_lbl.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        p.setFont(f_lbl)
        p.setPen(QColor(C.text_muted))
        p.drawText(QRectF(S.xl, S.sm, 120, 14), Qt.AlignLeft | Qt.AlignBottom, "OUTPUT FOLDER")

        f_path = QFont(["Cascadia Mono", "Consolas", "monospace"], 10, QFont.Medium)
        p.setFont(f_path)
        p.setPen(QColor(C.text_secondary))
        path_w = w - S.xxl * 2 - 80
        elided = p.fontMetrics().elidedText(self._folder_path, Qt.ElideMiddle, int(path_w))
        p.drawText(QRectF(S.xl, 28, path_w, 24), Qt.AlignLeft | Qt.AlignVCenter, elided)

        p.setPen(QColor(C.text_muted))
        f_hint = QFont(["Inter", "Segoe UI"], 9, QFont.Medium)
        p.setFont(f_hint)
        p.drawText(QRectF(w - S.xxl - 100, 0, 100, h), Qt.AlignRight | Qt.AlignVCenter, "\U0001F4C2  Open")

        p.end()


class _ProcessAgainCTA(QWidget):
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._hovered = False
        self._shimmer = 0.0
        self.setFixedSize(240, 52)
        self.setCursor(Qt.PointingHandCursor)

        if not _reduced():
            self._shimmer_timer = QTimer(self)
            self._shimmer_timer.setInterval(16)
            self._shimmer_timer.timeout.connect(self._tick)
            self._shimmer_timer.start()

    def _tick(self) -> None:
        self._shimmer += 0.02
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(C.accent))
        grad.setColorAt(1.0, QColor(C.gradient_end))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)

        lift = -2 if self._hovered else 0
        p.drawRoundedRect(1, 1 + lift, w - 2, h - 2, h / 2, h / 2)

        if self._hovered:
            inner = QColor("#FFFFFF")
            inner.setAlpha(15)
            p.setBrush(inner)
            p.drawRoundedRect(1, 1 + lift, w - 2, h - 2, h / 2, h / 2)

        shimmer_x = (self._shimmer * 2 % 3 - 1) * w * 0.5
        if not _reduced():
            sh = QLinearGradient(shimmer_x - 40, 0, shimmer_x + 40, 0)
            sh.setColorAt(0.0, QColor(255, 255, 255, 0))
            sh.setColorAt(0.5, QColor(255, 255, 255, 60))
            sh.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(sh))
            p.drawRoundedRect(1, 1 + lift, w - 2, h - 2, h / 2, h / 2)

        f = QFont(["Inter", "Segoe UI"], 13, QFont.Bold)
        p.setFont(f)
        p.setPen(QPen(QColor("#FFFFFF"), 0))
        p.drawText(QRectF(0, lift, w, h), Qt.AlignCenter, "\u21BB  Process Again")

        p.end()


class ResultsPage(QWidget):
    process_again = Signal()
    output_path_changed = Signal(str)

    def __init__(self, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")

        self._event_bus = event_bus
        self._result: Optional[PipelineResult] = None
        self._output_folder: str = ""
        self._full_entered = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        scroll.horizontalScrollBar().setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        root = QVBoxLayout(inner)
        root.setContentsMargins(S.xxl, S.xl, S.xxl, S.xxl)
        root.setSpacing(S.xl)

        self._hero = _HeroCard()
        root.addWidget(self._hero)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(S.md)
        self._stats: List[_StatTile] = []
        stat_configs = [
            ("0", "Total", "\u2211 processed", QColor(C.accent), C.gradient_end),
            ("0", "Succeeded", "100% rate", QColor(C.success), C.success),
            ("0", "Failed", "needs review", QColor(C.error), C.error),
            ("00:00", "Elapsed", "wall clock", QColor(C.text_secondary), C.text_muted),
        ]
        for val, label, micro, color, acc in stat_configs:
            tile = _StatTile(val, label, micro, color, acc)
            self._stats.append(tile)
            stats_row.addWidget(tile)
        root.addLayout(stats_row)

        self._pipeline_summary = _PipelineSummary()
        root.addWidget(self._pipeline_summary)

        self._failed_card = _FailedFileCard()
        root.addWidget(self._failed_card)

        self._output_tile = _OutputFolderTile()
        self._output_tile.path_changed.connect(self.output_path_changed.emit)
        root.addWidget(self._output_tile)

        cta_row = QHBoxLayout()
        cta_row.setSpacing(S.md)
        cta_row.addStretch(1)
        self._cta = _ProcessAgainCTA()
        self._cta.clicked.connect(self._on_process_again)
        cta_row.addWidget(self._cta)
        root.addLayout(cta_row)
        root.addStretch(1)

        scroll.setWidget(inner)
        outer_root = QVBoxLayout(self)
        outer_root.setContentsMargins(0, 0, 0, 0)
        outer_root.setSpacing(0)
        outer_root.addWidget(scroll, 1)

    def _on_process_again(self) -> None:
        self.process_again.emit()

    def _play_entrance_sequence(self) -> None:
        if _reduced():
            return
        group = QParallelAnimationGroup(self)
        group.addAnimation(self._hero.animate_in())
        for i, tile in enumerate(self._stats):
            group.addAnimation(tile.animate_in(delay=150 + i * 80))
        group.addAnimation(self._pipeline_summary.animate_in(delay=500))
        group.start()

    def show_result(self, result: PipelineResult, output_folder: str) -> None:
        self._result = result
        self._output_folder = output_folder

        is_success = result.all_succeeded and not result.cancelled
        is_cancelled = result.cancelled

        self._hero.set_data(is_success, is_cancelled, result.total, result.failed, result.elapsed_seconds)

        for i, tile in enumerate(self._stats):
            vals = [str(result.total), str(result.succeeded), str(result.failed), _fmt_time(result.elapsed_seconds)]
            tile.set_value(vals[i])

        completed = []
        if result.succeeded > 0:
            completed = ["Load", "Remove BG", "Upscale", "Resize", "Save"]
        self._pipeline_summary.set_completed(completed)

        self._failed_card.set_files(result.failed_files)
        self._output_tile.set_path(output_folder)

        if not self._full_entered:
            self._full_entered = True
            self._play_entrance_sequence()
