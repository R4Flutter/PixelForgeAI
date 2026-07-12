from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QUrl,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPauseAnimation,
    QPointF, QRectF, QSize, QMargins, Property, QEvent, QRect,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QFontMetrics,
    QEnterEvent, QMouseEvent, QWheelEvent, QAction, QDesktopServices,
    QClipboard, QRegion, QPalette, QKeyEvent,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QMenu, QApplication, QLayout, QGridLayout,
    QStyle, QStyleOption,
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


def _fmt_size(w: int, h: int) -> str:
    return f"{w}\u00d7{h}"


def _fmt_size_bytes(path: str) -> str:
    try:
        b = os.path.getsize(path)
        if b < 1024:
            return f"{b}B"
        if b < 1024 * 1024:
            return f"{b / 1024:.1f}KB"
        return f"{b / (1024 * 1024):.1f}MB"
    except Exception:
        return ""


_PIPELINE_STEPS = ["Load", "Remove BG", "Upscale", "Resize", "Save"]


def _try_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None

# ---------------------------------------------------------------------------
# FlowLayout — reflowing grid for the output gallery
# ---------------------------------------------------------------------------

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin: int = 0, spacing: int = S.md):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: List[QLayoutItem] = []

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_h = 0
        spacing = self.spacing()
        effective_w = rect.width() - m.left() - m.right()

        for item in self._items:
            hint = item.sizeHint()
            if hint.width() < 1 or hint.height() < 1:
                hint = item.widget().size() if item.widget() else QSize(176, 184)
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective_w + rect.x() and line_h > 0:
                x = rect.x() + m.left()
                y += line_h + spacing
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(int(x), int(y)), hint))
            x += hint.width() + spacing
            line_h = max(line_h, hint.height())

        return y + line_h + m.bottom() - rect.y()


# ---------------------------------------------------------------------------
# _ResultHero
# ---------------------------------------------------------------------------

class _ResultHero(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultHero")
        self._succeeded = True
        self._cancelled = False
        self._total = 0
        self._failed = 0
        self._elapsed = 0.0

        inner = QHBoxLayout(self)
        inner.setContentsMargins(S.xxl, S.xl, S.xxl, S.xl)
        inner.setSpacing(S.xl)

        left = QVBoxLayout()
        left.setSpacing(S.sm)

        title_row = QHBoxLayout()
        title_row.setSpacing(S.md)
        self._status_icon = QLabel()
        self._status_icon.setFixedSize(36, 36)
        title_row.addWidget(self._status_icon)
        self._title = QLabel()
        self._title.setStyleSheet(
            f"color:{C.text_primary}; font-size:26px; font-weight:{T.weight_bold}; background:transparent;"
        )
        title_row.addWidget(self._title)
        self._title.setStyleSheet(
            f"color:{C.text_primary}; font-size:26px; font-weight:{T.weight_bold}; background:transparent;"
        )
        title_row.addStretch(1)
        left.addLayout(title_row)

        self._subtitle = QLabel()
        self._subtitle.setStyleSheet(
            f"color:{C.text_secondary}; font-size:{T.size_lg}px; background:transparent;"
        )
        self._subtitle.setContentsMargins(44, 0, 0, 0)
        left.addWidget(self._subtitle)

        left.addStretch(1)

        left.addLayout(self._build_summary_row())

        left.addLayout(self._build_action_row())

        inner.addLayout(left, 1)

        right = self._build_metric_col()
        inner.addWidget(right)

    def _build_summary_row(self):
        row = QHBoxLayout()
        row.setSpacing(S.lg)
        row.setContentsMargins(44, 0, 0, 0)
        self._summary_labels = []
        for key in ("processed", "rate", "avg_time", "throughput"):
            col = QVBoxLayout()
            col.setSpacing(1)
            v = QLabel("\u2014")
            v.setStyleSheet(
                f"color:{C.text_primary}; font-size:{T.size_lg}px; font-weight:{T.weight_bold}; "
                f"font-family:'Cascadia Mono','Consolas',monospace; background:transparent;"
            )
            c = QLabel(key.replace("_", " ").upper())
            c.setStyleSheet(
                f"color:{C.text_muted}; font-size:{T.size_xs}px; font-weight:{T.weight_semibold}; "
                f"letter-spacing:1.2px; background:transparent;"
            )
            c.setAttribute(Qt.WA_TransparentForMouseEvents)
            col.addWidget(v)
            col.addWidget(c)
            row.addLayout(col)
            self._summary_labels.append(v)
        row.addStretch(1)
        return row

    def _build_action_row(self):
        row = QHBoxLayout()
        row.setSpacing(S.sm)
        row.setContentsMargins(44, 0, 0, 0)
        self._open_btn = QPushButton()
        self._open_btn.setObjectName("GhostButton")
        self._open_btn.setIcon(icon("folder_open", size=14, color=C.text_secondary))
        self._open_btn.setText("  Open Folder")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        row.addWidget(self._open_btn)
        self._again_btn = QPushButton()
        self._again_btn.setObjectName("SecondaryButton")
        self._again_btn.setText("  Process Again")
        self._again_btn.setCursor(Qt.PointingHandCursor)
        self._again_btn.setFixedHeight(32)
        row.addWidget(self._again_btn)
        row.addStretch(1)
        return row

    def _build_metric_col(self):
        col = QFrame()
        col.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._time_label = QLabel()
        self._time_label.setStyleSheet(
            f"color:{C.text_primary}; font-size:30px; font-weight:{T.weight_bold}; "
            f"font-family:'Cascadia Mono','Consolas',monospace; background:transparent;"
        )
        tl = QLabel("DURATION")
        tl.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_xs}px; font-weight:{T.weight_semibold}; "
            f"letter-spacing:1.5px; background:transparent;"
        )
        tl.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self._time_label)
        lay.addWidget(tl)
        lay.addStretch(1)
        col.setFixedWidth(160)
        return col

    def set_data(self, succeeded: bool, cancelled: bool, total: int, failed: int, elapsed: float) -> None:
        self._succeeded = succeeded
        self._cancelled = cancelled
        self._total = total
        self._failed = failed
        self._elapsed = elapsed

        if succeeded and not cancelled:
            self.setObjectName("ResultHero")
            self._title.setText("Processing Complete")
            self._subtitle.setText("Every image processed successfully.")
            self._status_icon.setPixmap(pixmap("check", size=36, color=C.success))
        elif cancelled:
            self.setObjectName("ResultHeroCancelled")
            self._title.setText("Processing Cancelled")
            self._subtitle.setText("The operation was cancelled before completion.")
            self._status_icon.setPixmap(pixmap("stop", size=36, color=C.warning))
        else:
            self.setObjectName("ResultHeroFailed")
            self._title.setText("Completed with Errors")
            self._subtitle.setText(f"{failed} image(s) could not be processed.")
            self._status_icon.setPixmap(pixmap("warn", size=36, color=C.error))

        self._time_label.setText(_fmt_time(elapsed))
        succeeded_count = total - failed
        rate = (succeeded_count / total * 100) if total > 0 else 0
        avg = elapsed / succeeded_count if succeeded_count > 0 else 0
        tp = total / elapsed if elapsed > 0 else 0
        vals = [str(total), f"{rate:.0f}%", f"{avg:.1f}s", f"{tp:.1f}/s"]
        for lbl, v in zip(self._summary_labels, vals):
            lbl.setText(v)
        self._polish()

    def animate_in(self) -> QPropertyAnimation:
        eff = QGraphicsOpacityEffect(self)
        eff.setOpacity(0.0)
        self.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", self)
        a.setDuration(500)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        return a

    def _polish(self) -> None:
        style = self.style()
        if style:
            style.unpolish(self)
            style.polish(self)


# ---------------------------------------------------------------------------
# _ResultStatTile
# ---------------------------------------------------------------------------

class _ResultStatTile(QWidget):
    def __init__(self, value: str, label: str, micro: str,
                 accent_color: str, accent_end: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultStatTile")
        self.setFixedSize(180, 118)
        self.setCursor(Qt.PointingHandCursor)
        self._display = value
        self._target_value = value
        self._label = label
        self._micro = micro
        self._accent = accent_color
        self._accent_end = accent_end
        self._hovered = False
        self._entrance_offset = 30.0
        self._entrance_opacity = 0.0
        self._lift = 0.0
        self._count = 0.0
        self._count_target = 0.0
        self._count_timer = QTimer(self)
        self._count_timer.setInterval(20)
        self._count_timer.timeout.connect(self._count_tick)
        self._is_time = "%" not in micro and "clock" not in micro.lower()
        self._is_rate = "%" in micro or "rate" in micro.lower()

    def set_value(self, text: str) -> None:
        self._target_value = text
        self._display = text
        num = _try_float(text)
        if num is not None and ":" not in text:
            self._count = 0.0
            self._count_target = num
            if not _reduced():
                self._count_timer.start()
        self.update()

    def _count_tick(self) -> None:
        step = max(1.0, self._count_target / 30)
        self._count = min(self._count_target, self._count + step)
        if self._count >= self._count_target:
            self._count = self._count_target
            self._count_timer.stop()
        self._display = str(int(self._count)) if self._count_target == int(self._count_target) else f"{self._count:.1f}"
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
            self._glow_anim(0.08)
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
            self._glow_anim(0.0)
        self.update()

    def _glow_anim(self, target: float) -> None:
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            a = QPropertyAnimation(eff, b"opacity", self)
            a.setDuration(200)
            a.setStartValue(eff.opacity() if hasattr(eff, 'opacity') else 0)
            a.setEndValue(target)
            a.start()

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

        bg = _tk(C.bg_card)
        if self._hovered:
            bg = _tk(C.bg_surface)
        p.setBrush(bg)
        border_c = _tk(C.border_hover) if self._hovered else _tk(C.border)
        p.setPen(QPen(border_c, 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, S.card_radius, S.card_radius)

        acc_grad = QLinearGradient(0, 0, 0, h)
        acc_grad.setColorAt(0.0, _tk(self._accent))
        acc_grad.setColorAt(1.0, _tk(self._accent_end))
        p.setBrush(QBrush(acc_grad))
        p.setPen(Qt.NoPen)
        bar = QPainterPath()
        bar.addRoundedRect(0, 0, 4, h - 1, 2, 2)
        p.drawPath(bar)

        sz = 30 if len(self._display) > 5 else 28
        f = QFont(["Cascadia Mono", "Consolas", "monospace"], sz, QFont.Bold)
        p.setFont(f)
        val_rect = QRectF(S.xl, S.sm, w - S.xl * 2, 44)
        p.setPen(_tk(C.text_primary))
        p.drawText(val_rect, Qt.AlignLeft | Qt.AlignBottom, self._display)

        f2 = QFont(["Inter", "Segoe UI"], 9, QFont.Medium)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f2)
        lbl_rect = QRectF(S.xl, 58, w - S.xl * 2, S.lg)
        p.setPen(_tk(C.text_muted))
        p.drawText(lbl_rect, Qt.AlignLeft | Qt.AlignVCenter, self._label.upper())

        f3 = QFont(["Inter", "Segoe UI"], 8, QFont.Medium)
        p.setFont(f3)
        p.setPen(_tk(self._accent))
        micro_rect = QRectF(S.xl, 78, w - S.xl * 2, S.md)
        p.drawText(micro_rect, Qt.AlignLeft | Qt.AlignVCenter, self._micro)

        p.end()


# ---------------------------------------------------------------------------
# _PipelineStepper
# ---------------------------------------------------------------------------

class _PipelineStepper(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PipelineStepper")
        self.setFixedHeight(56)
        self._completed_steps: Set[str] = set()
        self._entrance_offset = 20.0
        self._entrance_opacity = 0.0

    def set_completed(self, steps: List[str]) -> None:
        self._completed_steps = set(steps)
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

        bg = _tk(C.bg_card)
        p.setBrush(bg)
        p.setPen(QPen(_tk(C.border), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        steps = _PIPELINE_STEPS
        n = len(steps)

        total_dots = sum(self._dot_diameter for _ in steps)
        total_gaps = (n - 1) * 80
        total_labels = sum(p.fontMetrics().horizontalAdvance(s) for s in steps)
        layout_w = total_dots + total_gaps + 40
        start_x = (w - layout_w) / 2
        cy = h / 2

        x = start_x
        for i, step in enumerate(steps):
            done = step in self._completed_steps
            dd = self._dot_diameter

            if done:
                p.setBrush(_tk(C.success))
                p.setPen(QPen(_tk(C.success), 1))
            else:
                p.setBrush(_tk(C.bg_surface))
                p.setPen(QPen(_tk(C.border), 1))

            p.drawEllipse(QPointF(x + dd / 2, cy), dd / 2, dd / 2)

            if done:
                p.setPen(QPen(_tk(C.text_primary), 2))
                chk = QPainterPath()
                chk.moveTo(x + dd / 2 - 3, cy)
                chk.lineTo(x + dd / 2, cy + 3)
                chk.lineTo(x + dd / 2 + 4, cy - 3)
                p.drawPath(chk)

            label_x = x + dd + S.sm
            f_lbl = QFont(["Inter", "Segoe UI"], 9, QFont.Semibold)
            p.setFont(f_lbl)
            if done:
                p.setPen(_tk(C.text_primary))
            else:
                p.setPen(_tk(C.text_muted))
            p.drawText(QRectF(label_x, cy - 8, 200, 16), Qt.AlignLeft | Qt.AlignVCenter, step)

            if i < n - 1:
                line_x = x + dd + S.sm + p.fontMetrics().horizontalAdvance(step) + S.md
                line_end = x + dd + 80
                p.setPen(QPen(_tk(C.success) if done else _tk(C.border), 1.5,
                              Qt.DashLine if not done else Qt.SolidLine))
                p.drawLine(QPointF(line_x, cy), QPointF(line_end, cy))

            x += dd + 80

        p.end()

    @property
    def _dot_diameter(self) -> int:
        return 14


# ---------------------------------------------------------------------------
# _OutputFolderTile
# ---------------------------------------------------------------------------

class _OutputFolderTile(QFrame):
    path_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OutputTile")
        self.setFixedHeight(76)
        self._folder_path = ""
        self._copy_state = "idle"  # idle | copied

        inner = QHBoxLayout(self)
        inner.setContentsMargins(S.xl, S.lg, S.xl, S.lg)
        inner.setSpacing(S.md)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(pixmap("folder", size=22, color=C.text_secondary))
        icon_lbl.setFixedSize(22, 22)
        inner.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        section = QLabel("OUTPUT FOLDER")
        section.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_xs}px; font-weight:{T.weight_semibold}; "
            f"letter-spacing:1.5px; background:transparent;"
        )
        text_col.addWidget(section)

        self._path_display = QLabel()
        self._path_display.setStyleSheet(
            f"color:{C.text_secondary}; font-size:{T.size_sm}px; "
            f"font-family:'Cascadia Mono','Consolas',monospace; background:transparent;"
        )
        self._path_display.setWordWrap(False)
        text_col.addWidget(self._path_display)
        inner.addLayout(text_col, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.sm)

        self._copy_btn = QPushButton()
        self._copy_btn.setObjectName("GhostButton")
        self._copy_btn.setIcon(icon("copy", size=16, color=C.text_secondary))
        self._copy_btn.setToolTip("Copy path")
        self._copy_btn.setFixedSize(34, 34)
        self._copy_btn.clicked.connect(self._copy_path)
        btn_row.addWidget(self._copy_btn)

        self._open_btn = QPushButton()
        self._open_btn.setObjectName("GhostButton")
        self._open_btn.setIcon(icon("external", size=16, color=C.text_secondary))
        self._open_btn.setToolTip("Open in file manager")
        self._open_btn.setFixedSize(34, 34)
        self._open_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(self._open_btn)

        inner.addLayout(btn_row)

        self._toast = QLabel()
        self._toast.setObjectName("Toasted")
        self._toast.setVisible(False)
        inner.addWidget(self._toast)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.setVisible(False))

    def set_path(self, path: str) -> None:
        self._folder_path = path
        metrics = self._path_display.fontMetrics()
        elided = metrics.elidedText(path, Qt.ElideMiddle, 400)
        self._path_display.setText(elided)
        self._path_display.setToolTip(path)

    def _copy_path(self) -> None:
        if not self._folder_path:
            return
        cb = QApplication.clipboard()
        cb.setText(self._folder_path)
        self._toast.setText("\u2713 Copied")
        self._toast.setVisible(True)
        self._toast_timer.start(1200)

    def _open_folder(self) -> None:
        if not self._folder_path:
            return
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._folder_path))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# _ImagePreview  — large Lightroom-style preview with cross-fade + keyboard nav
# ---------------------------------------------------------------------------

class _ImagePreview(QFrame):
    selected = Signal(int)
    open_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GalleryWrap")
        self.setFixedHeight(420)
        self._items: List[ImageResultData] = []
        self._index = -1
        self._pixmap: QPixmap | None = None
        self._old_pixmap: QPixmap | None = None
        self._crossfade = 0.0
        self._is_fading = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(S.lg, S.lg, S.lg, S.lg)
        lay.setSpacing(S.sm)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(S.sm)
        self._name_label = QLabel()
        self._name_label.setStyleSheet(
            f"color:{C.text_primary}; font-size:{T.size_lg}px; font-weight:{T.weight_semibold}; background:transparent;"
        )
        meta_row.addWidget(self._name_label)
        meta_row.addStretch(1)
        self._dims_label = QLabel()
        self._dims_label.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_sm}px; "
            f"font-family:'Cascadia Mono','Consolas',monospace; background:transparent;"
        )
        meta_row.addWidget(self._dims_label)
        self._size_label = QLabel()
        self._size_label.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_sm}px; "
            f"font-family:'Cascadia Mono','Consolas',monospace; background:transparent;"
        )
        meta_row.addWidget(self._size_label)
        self._pos_label = QLabel()
        self._pos_label.setStyleSheet(
            f"color:{C.text_secondary}; font-size:{T.size_sm}px; background:transparent;"
        )
        meta_row.addWidget(self._pos_label)
        lay.addLayout(meta_row)

        self._image_area = QLabel()
        self._image_area.setAlignment(Qt.AlignCenter)
        self._image_area.setStyleSheet("background:transparent;")
        self._image_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        fade_eff = QGraphicsOpacityEffect(self._image_area)
        fade_eff.setOpacity(1.0)
        self._image_area.setGraphicsEffect(fade_eff)
        lay.addWidget(self._image_area, 1)

        self._nav_hint = QLabel("Arrow keys to navigate  \u00b7  Click to open")
        self._nav_hint.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_xs}px; background:transparent;"
        )
        self._nav_hint.setAlignment(Qt.AlignCenter)
        self._nav_hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self._nav_hint)

        self._crossfade_timer = QTimer(self)
        self._crossfade_timer.setInterval(16)
        self._crossfade_timer.timeout.connect(self._fade_tick)

        self.setAcceptDrops(False)

    def set_items(self, items: List[ImageResultData], index: int = 0) -> None:
        self._items = items
        self._index = index if 0 <= index < len(items) else (0 if items else -1)
        self._show_current()

    def select(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._old_pixmap = self._pixmap
            self._index = index
            self._crossfade = 0.0
            self._is_fading = True
            self._crossfade_timer.start()
            self._load_current()
            self.selected.emit(index)

    def _load_current(self) -> None:
        if self._index < 0 or self._index >= len(self._items):
            self._pixmap = None
            return
        data = self._items[self._index]
        if data.succeeded and data.output_path:
            pm = QPixmap(str(data.output_path))
            self._pixmap = pm if not pm.isNull() else None
        else:
            self._pixmap = None
        self._update_meta()

    def _show_current(self) -> None:
        self._load_current()
        self._crossfade = 1.0
        self._update_display()

    def _update_meta(self) -> None:
        if self._index < 0 or self._index >= len(self._items):
            self._name_label.clear()
            self._dims_label.clear()
            self._size_label.clear()
            self._pos_label.clear()
            return
        data = self._items[self._index]
        name = data.output_path.name if data.output_path else "unknown"
        self._name_label.setText(name)
        if data.output_size:
            self._dims_label.setText(_fmt_size(*data.output_size))
        else:
            self._dims_label.clear()
        if data.output_path:
            self._size_label.setText(_fmt_size_bytes(str(data.output_path)))
        else:
            self._size_label.clear()
        self._pos_label.setText(f"{self._index + 1} / {len(self._items)}")

    def _update_display(self) -> None:
        if self._pixmap and not self._pixmap.isNull():
            area = self._image_area.size()
            scaled = self._pixmap.scaled(area.width(), area.height(),
                                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._image_area.setPixmap(scaled)
        else:
            self._image_area.setText("No preview available")
            self._image_area.setStyleSheet(
                f"color:{C.text_muted}; font-size:{T.size_lg}px; background:transparent;"
            )

    def _fade_tick(self) -> None:
        self._crossfade = min(1.0, self._crossfade + 0.06)
        opacity = self._crossfade
        eff = self._image_area.graphicsEffect()
        if isinstance(eff, QGraphicsOpacityEffect):
            eff.setOpacity(opacity)
        if self._crossfade >= 1.0:
            self._is_fading = False
            self._crossfade_timer.stop()
            self._old_pixmap = None
            self._update_display()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Left:
            self.select(max(0, self._index - 1))
        elif event.key() == Qt.Key_Right:
            self.select(min(len(self._items) - 1, self._index + 1))
        elif event.key() == Qt.Key_Home:
            self.select(0)
        elif event.key() == Qt.Key_End:
            self.select(len(self._items) - 1)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = 1 if event.angleDelta().y() > 0 else -1
        idx = max(0, min(len(self._items) - 1, self._index + delta))
        if idx != self._index:
            self.select(idx)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._index >= 0:
            data = self._items[self._index]
            if data.output_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(data.output_path)))
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_display()


# ---------------------------------------------------------------------------
# _ThumbnailCarousel — horizontal filmstrip for quick preview navigation
# ---------------------------------------------------------------------------

class _ThumbnailCarousel(QWidget):
    selected = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(86)
        self._items: List[ImageResultData] = []
        self._thumb_widgets: List[_ThumbCarouselItem] = []
        self._selected = -1

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.horizontalScrollBar().setStyleSheet(
            "QScrollBar:horizontal { background:#0E0F14; height:4px; } "
            "QScrollBar::handle:horizontal { background:#262A37; border-radius:2px; min-width:30px; } "
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0px; }"
        )

        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;")
        self._inner_layout = QHBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(S.sm, S.xs, S.sm, S.xs)
        self._inner_layout.setSpacing(S.sm)
        self._inner_layout.addStretch(1)

        self._scroll.setWidget(self._inner)
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addWidget(self._scroll)

    def set_items(self, items: List[ImageResultData]) -> None:
        self._items = items
        self._selected = -1
        for w in self._thumb_widgets:
            w.setParent(None)
            w.deleteLater()
        self._thumb_widgets.clear()
        for i, data in enumerate(items):
            tw = _ThumbCarouselItem(data, i)
            tw.clicked.connect(lambda _, idx=i: self._on_thumb_clicked(idx))
            self._thumb_widgets.append(tw)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, tw)

    def select(self, index: int) -> None:
        if 0 <= index < len(self._thumb_widgets):
            if self._selected >= 0 and self._selected < len(self._thumb_widgets):
                self._thumb_widgets[self._selected].set_selected(False)
            self._selected = index
            self._thumb_widgets[index].set_selected(True)
            self.selected.emit(index)

    def _on_thumb_clicked(self, index: int) -> None:
        self.select(index)


class _ThumbCarouselItem(QWidget):
    clicked = Signal()

    def __init__(self, data: ImageResultData, index: int, parent=None) -> None:
        super().__init__(parent)
        self._data = data
        self._index = index
        self._selected = False
        self._hovered = False
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)

        pm = QPixmap(str(data.output_path)) if data.succeeded and data.output_path else QPixmap()
        self._pm = pm.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not pm.isNull() else pixmap("image", size=28, color=C.text_muted)

    def set_selected(self, sel: bool) -> None:
        self._selected = sel
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
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        rr = 8
        if self._selected:
            p.setBrush(_tk(C.accent))
            p.setPen(QPen(_tk(C.accent), 2))
        elif self._hovered:
            p.setBrush(_tk(C.bg_surface))
            p.setPen(QPen(_tk(C.border_hover), 1))
        else:
            p.setBrush(_tk(C.bg_card))
            p.setPen(QPen(_tk(C.border), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, rr, rr)
        if self._selected:
            p.setBrush(_tk(C.bg_primary))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(2, 2, w - 5, h - 5, rr - 2, rr - 2)
        if not self._pm.isNull():
            pw, ph = self._pm.width(), self._pm.height()
            p.drawPixmap(int((w - pw) / 2), int((h - ph) / 2), self._pm)
        if not self._data.succeeded and not self._pm.isNull():
            p.setPen(QPen(_tk(C.error), 2))
            p.drawLine(8, 8, w - 8, h - 8)
            p.drawLine(w - 8, 8, 8, h - 8)
        p.end()


# ---------------------------------------------------------------------------
# _ResultThumbnail
# ---------------------------------------------------------------------------

class _ResultThumbnail(QWidget):
    clicked = Signal(str)

    def __init__(self, data: ImageResultData, parent=None) -> None:
        super().__init__(parent)
        self._data = data
        self._hovered = False
        self._lift = 0.0
        self.setFixedSize(196, 200)
        self.setCursor(Qt.PointingHandCursor)
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(12)
        eff.setOffset(0, 2)
        eff.setColor(QColor(0, 0, 0, 30))
        eff.setEnabled(False)
        self._shadow = eff
        self.setGraphicsEffect(eff)

        if data.succeeded and data.output_path:
            pm = QPixmap(str(data.output_path))
            if not pm.isNull():
                self._thumb_pm = pm.scaled(156, 116, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                self._thumb_pm = pixmap("image", size=60, color=C.text_muted)
        else:
            self._thumb_pm = pixmap("warn", size=48, color=C.error)

    def animate_in(self, delay: int = 0) -> QSequentialAnimationGroup:
        a = QPropertyAnimation(self, b"thumb_offset", self)
        a.setDuration(350)
        a.setStartValue(24.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        g = QSequentialAnimationGroup(self)
        g.addPause(delay)
        g.addAnimation(a)
        return g

    def _get_to(self) -> float:
        return self._entrance_offset if hasattr(self, '_entrance_offset') else 0.0

    def _set_to(self, v: float) -> None:
        self._entrance_offset = v
        self._entrance_opacity = max(0.0, 1.0 - v / 24.0)
        self.update()

    thumb_offset = Property(float, _get_to, _set_to)

    def sizeHint(self) -> QSize:
        return QSize(196, 200)

    def _init_anim_props(self):
        if not hasattr(self, '_entrance_offset'):
            self._entrance_offset = 24.0
            self._entrance_opacity = 0.0

    def enterEvent(self, event) -> None:
        self._hovered = True
        if not _reduced():
            a = QPropertyAnimation(self, b"thumb_lift", self)
            a.setDuration(200)
            a.setStartValue(0.0)
            a.setEndValue(-4.0)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.start()
            self._shadow_anim(0.35)
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        if not _reduced():
            a = QPropertyAnimation(self, b"thumb_lift", self)
            a.setDuration(200)
            a.setStartValue(self._lift)
            a.setEndValue(0.0)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.start()
            self._shadow_anim(0.0)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(str(self._data.output_path) if self._data.output_path else "")
        super().mousePressEvent(event)

    def _shadow_anim(self, target: float) -> None:
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            was_enabled = eff.isEnabled()
            if target > 0 and not was_enabled:
                eff.setEnabled(True)
            a = QPropertyAnimation(eff, b"opacity", self)
            a.setDuration(200)
            last = getattr(eff, '_shadow_opacity', eff.opacity() if hasattr(eff, 'opacity') else 0.0)
            a.setStartValue(last)
            a.setEndValue(target)
            a.finished.connect(lambda e=eff, t=target: e.setEnabled(t > 0))
            a.start()
            eff._shadow_opacity = target

    def _get_lift(self) -> float:
        return self._lift

    def _set_lift(self, v: float) -> None:
        self._lift = v
        self.update()

    thumb_lift = Property(float, _get_lift, _set_lift)

    def paintEvent(self, event) -> None:
        self._init_anim_props()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        p.translate(0, self._lift)
        p.setOpacity(self._entrance_opacity)
        p.translate(0, self._entrance_offset)

        is_fail = not self._data.succeeded
        bg = _tk(C.bg_card) if not is_fail else QColor("#16101A")
        if self._hovered:
            bg = bg.lighter(108)
        p.setBrush(bg)
        border_c = _tk(C.border_hover) if self._hovered else (
            _tk(C.border) if not is_fail else QColor("#3A2230")
        )
        p.setPen(QPen(border_c, 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 10, 10)

        thumb_rect = QRectF(10, 10, w - 20, 116)
        p.drawRoundedRect(thumb_rect, 8, 8)

        if not self._thumb_pm.isNull():
            pm = self._thumb_pm
            pm_rect = QRectF(
                thumb_rect.center().x() - pm.width() / 2,
                thumb_rect.center().y() - pm.height() / 2,
                pm.width(), pm.height(),
            )
            p.drawPixmap(pm_rect, pm, pm.rect())

        if is_fail:
            overlay = QColor(C.error)
            overlay.setAlpha(20)
            p.setBrush(overlay)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(thumb_rect, 8, 8)

            p.setPen(QPen(_tk(C.error), 2))
            p.drawLine(QPointF(thumb_rect.center().x() - 8, thumb_rect.center().y() - 8),
                       QPointF(thumb_rect.center().x() + 8, thumb_rect.center().y() + 8))
            p.drawLine(QPointF(thumb_rect.center().x() + 8, thumb_rect.center().y() - 8),
                       QPointF(thumb_rect.center().x() - 8, thumb_rect.center().y() + 8))

        f_name = QFont(["Inter", "Segoe UI"], 10, QFont.Medium)
        p.setFont(f_name)
        p.setPen(_tk(C.text_secondary))
        name = self._data.output_path.name if self._data.output_path else "unknown"
        name_rect = QRectF(10, 132, w - 20, 18)
        elided_name = p.fontMetrics().elidedText(name, Qt.ElideMiddle, int(w - 20))
        p.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_name)

        f_meta = QFont(["Cascadia Mono", "Consolas", "monospace"], 8, QFont.Medium)
        p.setFont(f_meta)
        p.setPen(_tk(C.text_muted))
        meta_parts = []
        if self._data.output_size:
            meta_parts.append(_fmt_size(*self._data.output_size))
        if self._data.output_path:
            meta_parts.append(_fmt_size_bytes(str(self._data.output_path)))
        meta = "  \u00b7  ".join(meta_parts)
        meta_rect = QRectF(10, 150, w - 20, 16)
        p.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, meta)

        if is_fail and self._data.error:
            f_err = QFont(["Inter", "Segoe UI"], 8, QFont.Medium)
            p.setFont(f_err)
            p.setPen(_tk(C.error))
            err_rect = QRectF(10, 166, w - 20, 14)
            elided_err = p.fontMetrics().elidedText(self._data.error, Qt.ElideRight, int(w - 20))
            p.drawText(err_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_err)

        p.end()


# ---------------------------------------------------------------------------
# _OutputGallery
# ---------------------------------------------------------------------------

class _OutputGallery(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GalleryWrap")
        self._all_thumbnails: List[_ResultThumbnail] = []
        self._current_filter = "all"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.lg, S.lg, S.lg, S.lg)
        outer.setSpacing(S.md)

        header_row = QHBoxLayout()
        header_row.setSpacing(S.sm)

        gallery_title = QLabel("OUTPUT GALLERY")
        gallery_title.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_xs}px; font-weight:{T.weight_semibold}; "
            f"letter-spacing:1.5px; background:transparent;"
        )
        header_row.addWidget(gallery_title)

        header_row.addStretch(1)

        self._count_label = QLabel("0 images")
        self._count_label.setStyleSheet(
            f"color:{C.text_muted}; font-size:{T.size_sm}px; background:transparent;"
        )
        header_row.addWidget(self._count_label)

        outer.addLayout(header_row)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(S.sm)

        self._pills: Dict[str, QPushButton] = {}
        for key, label in [("all", "All"), ("success", "Succeeded"), ("fail", "Failed")]:
            pill = QPushButton(label)
            pill.setObjectName("FilterPill")
            pill.setCheckable(True)
            pill.setChecked(key == "all")
            pill.clicked.connect(lambda _, k=key: self._set_filter(k))
            self._pills[key] = pill
            pill_row.addWidget(pill)

        pill_row.addStretch(1)
        outer.addLayout(pill_row)

        self._flow_container = QWidget()
        self._flow_container.setStyleSheet("background: transparent;")
        self._flow = FlowLayout(self._flow_container, margin=0, spacing=S.md)
        outer.addWidget(self._flow_container, 1)

    def set_images(self, results: List[ImageResultData]) -> None:
        self._all_thumbnails.clear()
        self._clear_flow()
        for data in results:
            thumb = _ResultThumbnail(data)
            thumb.clicked.connect(lambda path: getattr(self, '_on_thumb_clicked', lambda _: None)(path))
            self._all_thumbnails.append(thumb)
        self._apply_filter()
        total_success = sum(1 for r in results if r.succeeded)
        total_fail = len(results) - total_success
        parts = [f"{len(results)} total"]
        if total_success:
            parts.append(f"{total_success} ok")
        if total_fail:
            parts.append(f"{total_fail} failed")
        self._count_label.setText("  \u00b7  ".join(parts))

    def _clear_flow(self) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

    def _set_filter(self, key: str) -> None:
        self._current_filter = key
        for k, pill in self._pills.items():
            pill.setChecked(k == key)
        self._apply_filter()

    def _apply_filter(self) -> None:
        self._clear_flow()
        for thumb in self._all_thumbnails:
            show = (
                self._current_filter == "all"
                or (self._current_filter == "success" and thumb._data.succeeded)
                or (self._current_filter == "fail" and not thumb._data.succeeded)
            )
            if show:
                self._flow.addWidget(thumb)

    def animate_in(self) -> QParallelAnimationGroup:
        group = QParallelAnimationGroup(self)
        delay = 0
        for thumb in self._all_thumbnails:
            group.addAnimation(thumb.animate_in(delay=delay))
            delay = min(delay + 25, 300)
        return group


# ---------------------------------------------------------------------------
# _FailedFilesCard
# ---------------------------------------------------------------------------

class _FailedFilesCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("FailedSection")
        self._collapsed = False

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
        self._count_badge.setObjectName("FailedCount")
        header_row.addWidget(self._count_badge)
        header_row.addStretch(1)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setObjectName("FailedToggle")
        self._toggle_btn.setIcon(icon("chevron_down", size=16, color=C.text_secondary))
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self._toggle_btn)
        nat_layout.addLayout(header_row)

        self._list_widget = QListWidget()
        self._list_widget.setObjectName("FailedList")
        self._list_widget.setFrameShape(QListWidget.NoFrame)
        self._list_widget.setMaximumHeight(0)
        nat_layout.addWidget(self._list_widget)
        outer.addWidget(self._native)

        self._anim = QPropertyAnimation(self._list_widget, b"maximumHeight", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def set_files(self, files: List[str]) -> None:
        self._list_widget.clear()
        for f in files:
            item = QListWidgetItem()
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(S.sm, S.xs, S.sm, S.xs)
            item_layout.setSpacing(S.sm)

            err_icon = QLabel()
            err_icon.setPixmap(pixmap("warn", size=14, color=C.error))
            err_icon.setFixedSize(14, 14)
            item_layout.addWidget(err_icon)

            name_label = QLabel(f)
            name_label.setStyleSheet(
                f"color:{C.text_secondary}; font-size:{T.size_sm}px; "
                f"font-family:'Cascadia Mono','Consolas',monospace; background:transparent;"
            )
            item_layout.addWidget(name_label, 1)

            item.setSizeHint(item_widget.sizeHint())
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, item_widget)

        self._count_badge.setText(str(len(files)))
        self.setVisible(len(files) > 0)
        if len(files) > 0:
            self._ensure_height()

    def _ensure_height(self) -> None:
        item_h = self._list_widget.sizeHintForRow(0) if self._list_widget.count() > 0 else 30
        total = self._list_widget.count() * item_h + 4
        if not self._collapsed:
            self._list_widget.setMaximumHeight(total)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            target = 0
            self._toggle_btn.setIcon(icon("chevron_right", size=16, color=C.text_secondary))
        else:
            item_h = self._list_widget.sizeHintForRow(0) if self._list_widget.count() > 0 else 30
            target = self._list_widget.count() * item_h + 4
            self._toggle_btn.setIcon(icon("chevron_down", size=16, color=C.text_secondary))

        self._anim.stop()
        self._anim.setStartValue(self._list_widget.maximumHeight())
        self._anim.setEndValue(target)
        self._anim.start()


# ---------------------------------------------------------------------------
# _ActionRow
# ---------------------------------------------------------------------------

class _ActionRow(QWidget):
    primary_clicked = Signal()
    secondary_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S.lg)

        hint = QLabel("Need to run again? Adjust your images and re-process.")
        hint.setObjectName("Hint")
        layout.addWidget(hint, 1)

        self._secondary_btn = QPushButton(" Open Folder")
        self._secondary_btn.setObjectName("SecondaryButton")
        self._secondary_btn.setIcon(icon("folder_open", size=16, color=C.text_secondary))
        self._secondary_btn.setCursor(Qt.PointingHandCursor)
        self._secondary_btn.clicked.connect(self.secondary_clicked.emit)
        layout.addWidget(self._secondary_btn)

        self._primary_btn = QPushButton("  Process Again")
        self._primary_btn.setObjectName("ActionPrimary")
        self._primary_btn.setCursor(Qt.PointingHandCursor)
        self._primary_btn.clicked.connect(self.primary_clicked.emit)
        layout.addWidget(self._primary_btn)


# ---------------------------------------------------------------------------
# ResultsPage
# ---------------------------------------------------------------------------

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
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        root = QVBoxLayout(inner)
        root.setContentsMargins(S.xxl, S.xl, S.xxl, S.xxl)
        root.setSpacing(S.xl)

        # Hero
        self._hero = _ResultHero()
        self._hero._open_btn.clicked.connect(self._open_output_folder)
        self._hero._again_btn.clicked.connect(self._on_process_again)
        root.addWidget(self._hero)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(S.md)
        self._stats: List[_ResultStatTile] = []
        stat_configs = [
            ("0", "Total", "\u2211 processed", C.accent, C.gradient_end),
            ("0", "Succeeded", "100% rate", C.success, C.success),
            ("0", "Failed", "needs review", C.error, C.error),
            ("00:00", "Elapsed", "wall clock", C.text_secondary, C.text_muted),
        ]
        for val, label, micro, color, acc in stat_configs:
            tile = _ResultStatTile(val, label, micro, color, acc)
            self._stats.append(tile)
            stats_row.addWidget(tile)
        root.addLayout(stats_row)

        # Pipeline stepper
        self._pipeline_summary = _PipelineStepper()
        root.addWidget(self._pipeline_summary)

        # Large image preview
        self._preview = _ImagePreview()
        self._preview.setVisible(False)
        root.addWidget(self._preview)

        # Thumbnail carousel
        self._carousel = _ThumbnailCarousel()
        self._carousel.setVisible(False)
        self._carousel.selected.connect(self._on_carousel_selected)
        root.addWidget(self._carousel)

        # Output folder tile
        self._output_tile = _OutputFolderTile()
        self._output_tile.path_changed.connect(self.output_path_changed.emit)
        root.addWidget(self._output_tile)

        # Output gallery
        self._gallery = _OutputGallery()
        self._gallery._on_thumb_clicked = self._on_gallery_thumb_clicked
        root.addWidget(self._gallery, 1)

        # Failed files
        self._failed_card = _FailedFilesCard()
        root.addWidget(self._failed_card)

        # Action row
        self._action_row = _ActionRow()
        self._action_row.primary_clicked.connect(self._on_process_again)
        self._action_row.secondary_clicked.connect(self._open_output_folder)
        root.addWidget(self._action_row)

        scroll.setWidget(inner)
        outer_root = QVBoxLayout(self)
        outer_root.setContentsMargins(0, 0, 0, 0)
        outer_root.setSpacing(0)
        outer_root.addWidget(scroll, 1)

    def _on_carousel_selected(self, index: int) -> None:
        self._preview.select(index)

    def _on_gallery_thumb_clicked(self, path: str) -> None:
        for i, data in enumerate(self._result.image_results if self._result else []):
            if data.output_path and str(data.output_path) == path:
                self._preview.select(i)
                self._carousel.select(i)
                break

    def _on_process_again(self) -> None:
        self.process_again.emit()

    def _open_output_folder(self) -> None:
        if self._output_folder:
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_folder))
            except Exception:
                pass

    def _play_entrance_sequence(self) -> None:
        if _reduced():
            return
        group = QParallelAnimationGroup(self)
        group.addAnimation(self._hero.animate_in())
        for i, tile in enumerate(self._stats):
            group.addAnimation(tile.animate_in(delay=150 + i * 70))
        group.addAnimation(self._pipeline_summary.animate_in(delay=500))

        seq = QSequentialAnimationGroup(self)
        seq.addPause(600)
        seq.addAnimation(self._gallery.animate_in())
        group.addAnimation(seq)

        group.start()

    def show_result(self, result: PipelineResult, output_folder: str) -> None:
        self._result = result
        self._output_folder = output_folder

        is_success = result.all_succeeded and not result.cancelled
        is_cancelled = result.cancelled

        self._hero.set_data(is_success, is_cancelled, result.total, result.failed, result.elapsed_seconds)

        vals = [
            str(result.total),
            str(result.succeeded),
            str(result.failed),
            _fmt_time(result.elapsed_seconds),
        ]
        for i, tile in enumerate(self._stats):
            tile.set_value(vals[i])

        completed = []
        if result.succeeded > 0:
            completed = list(_PIPELINE_STEPS)
        self._pipeline_summary.set_completed(completed)

        self._output_tile.set_path(output_folder)

        images = result.image_results
        self._gallery.set_images(images)

        if images:
            self._preview.set_items(images)
            self._preview.setVisible(True)
            self._carousel.set_items(images)
            self._carousel.setVisible(True)
            self._carousel.select(0)

        self._failed_card.set_files(result.failed_files)

        if not self._full_entered:
            self._full_entered = True
            self._play_entrance_sequence()
