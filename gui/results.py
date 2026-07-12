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
        try:
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
        finally:
            p.end()


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

        self._prev_btn = QPushButton(self)
        self._prev_btn.setFixedSize(36, 36)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(14,15,20,200); border: 1px solid #262A37;"
            "  border-radius: 18px;"
            "  font-size: 18px; color: #7A7F93;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(38,42,55,220); border-color: #3A3F52; color: #E8E9ED;"
            "}"
        )
        self._prev_btn.setText("\u25C0")
        self._prev_btn.setToolTip("Previous image")
        self._prev_btn.hide()

        self._next_btn = QPushButton(self)
        self._next_btn.setFixedSize(36, 36)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setStyleSheet(self._prev_btn.styleSheet())
        self._next_btn.setText("\u25B6")
        self._next_btn.setToolTip("Next image")
        self._next_btn.hide()

        self._prev_btn.clicked.connect(self._prev_image)
        self._next_btn.clicked.connect(self._next_image)

        self._btn_timer = QTimer(self)
        self._btn_timer.setSingleShot(True)
        self._btn_timer.setInterval(3000)
        self._btn_timer.timeout.connect(lambda: (self._prev_btn.hide(), self._next_btn.hide()))

    def set_items(self, items: List[ImageResultData], index: int = 0) -> None:
        self._items = items
        self._index = index if 0 <= index < len(items) else (0 if items else -1)
        single = len(items) <= 1
        self._nav_hint.setVisible(not single)
        self._pos_label.setVisible(not single)
        self._prev_btn.setVisible(False)
        self._next_btn.setVisible(False)
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
        dx = abs(event.angleDelta().x())
        dy = abs(event.angleDelta().y())
        if dx > dy:
            delta = 1 if event.angleDelta().x() > 0 else -1
            idx = max(0, min(len(self._items) - 1, self._index + delta))
            if idx != self._index:
                self.select(idx)
        else:
            event.ignore()
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._index >= 0:
            data = self._items[self._index]
            if data.output_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(data.output_path)))
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_display()
        self._reposition_buttons()

    def enterEvent(self, event) -> None:
        if len(self._items) > 1:
            self._prev_btn.show()
            self._next_btn.show()
            self._btn_timer.start()

    def leaveEvent(self, event) -> None:
        self._btn_timer.start()

    def _reposition_buttons(self) -> None:
        ia = self._image_area
        sy = ia.y() + (ia.height() - 36) // 2
        self._prev_btn.move(ia.x() + 12, sy)
        self._next_btn.move(ia.x() + ia.width() - 48, sy)
        self._prev_btn.raise_()
        self._next_btn.raise_()

    def _prev_image(self) -> None:
        self.select(max(0, self._index - 1))

    def _next_image(self) -> None:
        self.select(min(len(self._items) - 1, self._index + 1))


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
        try:
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
        finally:
            p.end()


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
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 8px;"
            "  margin: 0; padding: 0;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: #262A37; border-radius: 4px;"
            "  min-height: 40px;"
            "}"
            "QScrollBar::handle:vertical:hover { background: #3A3F52; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "  background: transparent;"
            "}"
        )
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.viewport().setStyleSheet("background: transparent;")

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
        # Large image preview
        self._preview = _ImagePreview()
        self._preview.setVisible(False)
        root.addWidget(self._preview)

        # Output folder tile
        self._output_tile = _OutputFolderTile()
        self._output_tile.path_changed.connect(self.output_path_changed.emit)
        root.addWidget(self._output_tile)

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
        seq = QSequentialAnimationGroup(self)
        seq.addPause(600)
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

        self._output_tile.set_path(output_folder)

        images = result.image_results

        succeeded = [i for i in images if i.succeeded]
        if succeeded:
            self._preview.set_items(succeeded)
            self._preview.setVisible(True)

        self._failed_card.set_files(result.failed_files)

        if not self._full_entered:
            self._full_entered = True
            self._play_entrance_sequence()
