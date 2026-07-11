from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPauseAnimation,
    QPointF, QRectF, QSize, Property, QEvent,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QFontMetrics,
    QEnterEvent, QMouseEvent, QWheelEvent, QAction,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QMenu,
)

from components.buttons import PrimaryButton, SecondaryButton
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


_BRIGHTEN = 1.25


class _GlowBadge(QWidget):
    def __init__(self, succeeded: bool, parent=None) -> None:
        super().__init__(parent)
        self._succeeded = succeeded
        self._arc_progress = 0.0
        self._check_progress = 0.0
        self._pulse = 0.0
        self._glow_opacity = 0.0
        self._glow_phase = 0.0
        self.setFixedSize(88, 88)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        if not _reduced():
            self._pulse_timer = QTimer(self)
            self._pulse_timer.setInterval(16)
            self._pulse_timer.timeout.connect(self._tick)
            self._pulse_timer.start()

    def _tick(self) -> None:
        self._pulse += 0.04
        self._glow_phase += 0.02
        self._glow_opacity = 0.35 + 0.25 * math.sin(self._glow_phase * 2 * math.pi / 60)
        self.update()

    def animate_in(self, on_finished=None) -> None:
        if _reduced():
            self._arc_progress = 1.0
            self._check_progress = 1.0
            self._glow_opacity = 0.5
            self.update()
            if on_finished:
                on_finished()
            return
        self._arc_progress = 0.0
        self._check_progress = 0.0
        self._glow_opacity = 0.0
        self._glow_phase = 0.0

        arc_anim = QPropertyAnimation(self, b"arc_progress", self)
        arc_anim.setDuration(500)
        arc_anim.setStartValue(0.0)
        arc_anim.setEndValue(1.0)
        arc_anim.setEasingCurve(QEasingCurve.OutCubic)

        check_anim = QPropertyAnimation(self, b"check_progress", self)
        check_anim.setDuration(400)
        check_anim.setStartValue(0.0)
        check_anim.setEndValue(1.0)
        check_anim.setEasingCurve(QEasingCurve.OutBack)

        group = QParallelAnimationGroup(self)
        group.addAnimation(arc_anim)
        group.addAnimation(check_anim)
        if on_finished:
            group.finished.connect(on_finished)
        group.start()

    def _get_arc(self) -> float:
        return self._arc_progress

    def _set_arc(self, v: float) -> None:
        self._arc_progress = v
        self.update()

    def _get_check(self) -> float:
        return self._check_progress

    def _set_check(self, v: float) -> None:
        self._check_progress = v
        self.update()

    arc_progress = Property(float, _get_arc, _set_arc)
    check_progress = Property(float, _get_check, _set_check)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = 34
        bar_w = 3

        color = QColor(C.success) if self._succeeded else QColor(C.error)

        glow_r = r + 12 + 8 * math.sin(self._glow_phase * 2 * math.pi / 60)
        g = QRadialGradient(cx, cy, glow_r)
        c_t = color.toTuple()
        g.setColorAt(0.0, QColor(c_t[0], c_t[1], c_t[2], int(60 * self._glow_opacity)))
        g.setColorAt(0.4, QColor(c_t[0], c_t[1], c_t[2], int(20 * self._glow_opacity)))
        g.setColorAt(0.7, QColor(c_t[0], c_t[1], c_t[2], int(6 * self._glow_opacity)))
        g.setColorAt(1.0, QColor(c_t[0], c_t[1], c_t[2], 0))
        p.setBrush(QBrush(g))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        bg_pen = QPen(QColor(C.border), bar_w)
        bg_pen.setCapStyle(Qt.RoundCap)
        p.setPen(bg_pen)
        p.drawArc(QRectF(cx - r + bar_w, cy - r + bar_w, (r - bar_w) * 2, (r - bar_w) * 2), 0, 360 * 16)

        if self._arc_progress > 0:
            arc_pen = QPen(color, bar_w)
            arc_pen.setCapStyle(Qt.RoundCap)
            p.setPen(arc_pen)
            p.drawArc(QRectF(cx - r + bar_w, cy - r + bar_w, (r - bar_w) * 2, (r - bar_w) * 2),
                      -90 * 16, int(self._arc_progress * 360 * 16))

        inner_r = r - bar_w - 5
        inner_bg = QColor(C.bg_secondary)
        p.setBrush(inner_bg)
        p.setPen(QPen(QColor(C.border), 1))
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        if self._check_progress > 0:
            check_pen = QPen(color, 3)
            check_pen.setCapStyle(Qt.RoundCap)
            check_pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(check_pen)
            p.setBrush(Qt.NoBrush)
            if self._check_progress < 1.0:
                p.setOpacity(self._check_progress)
            if self._succeeded:
                path = QPainterPath()
                path.moveTo(cx - 10, cy + 1)
                path.lineTo(cx - 3, cy + 7)
                path.lineTo(cx + 10, cy - 6)
                p.drawPath(path)
            else:
                off = 7
                p.drawLine(QPointF(cx - off, cy - off), QPointF(cx + off, cy + off))
                p.drawLine(QPointF(cx + off, cy - off), QPointF(cx - off, cy + off))
            if self._check_progress < 1.0:
                p.setOpacity(1.0)

        p.end()


class _StatTile(QWidget):
    def __init__(self, value: str, label: str, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self._value = value
        self._label = label
        self._color = color
        self._hovered = False
        self._entrance_offset = 30.0
        self._entrance_opacity = 0.0
        self.setFixedHeight(88)
        self.setCursor(Qt.PointingHandCursor)

    def set_value(self, text: str) -> None:
        self._value = text
        self.update()

    def animate_in(self, delay: int = 0) -> QSequentialAnimationGroup:
        anim = QPropertyAnimation(self, b"entrance_offset", self)
        anim.setDuration(500)
        anim.setStartValue(30.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        group = QSequentialAnimationGroup(self)
        group.addPause(delay)
        group.addAnimation(anim)
        return group

    def _get_offset(self) -> float:
        return self._entrance_offset

    def _set_offset(self, v: float) -> None:
        self._entrance_offset = v
        self._entrance_opacity = max(0.0, 1.0 - v / 30.0)
        self.update()

    entrance_offset = Property(float, _get_offset, _set_offset)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setOpacity(self._entrance_opacity)
        p.translate(0, self._entrance_offset)

        bg = QColor(C.bg_card)
        if self._hovered:
            bg = bg.lighter(120)
        p.setBrush(bg)
        p.setPen(QPen(QColor(C.border), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, S.card_radius, S.card_radius)

        acc = self._color.toTuple()
        accent_bar = QColor(acc[0], acc[1], acc[2], 30)
        p.setBrush(accent_bar)
        p.setPen(Qt.NoPen)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(0, 0, 4, h - 1, 2, 2)
        p.drawPath(bar_path)

        f = QFont()
        f.setPointSize(T.size_xxl)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        val_rect = QRectF(S.xl, S.sm, w - S.xl * 2, 40)
        p.setPen(QColor(C.text_primary))
        p.drawText(val_rect, Qt.AlignLeft | Qt.AlignBottom, self._value)

        f2 = QFont()
        f2.setPointSize(T.size_xs)
        f2.setWeight(QFont.Medium)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        p.setFont(f2)
        lbl_rect = QRectF(S.xl, 56, w - S.xl * 2, S.lg)
        p.setPen(QColor(C.text_muted))
        p.drawText(lbl_rect, Qt.AlignLeft | Qt.AlignVCenter, self._label.upper())

        p.end()


class _ThumbnailCard(QFrame):
    clicked = Signal(str)
    double_clicked = Signal(str)

    def __init__(self, path: str, index: int, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._index = index
        self._selected = False

        self.setFixedSize(180, 220)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("Card")

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        vbox.setAlignment(Qt.AlignCenter)

        self._image_label = QLabel()
        self._image_label.setFixedSize(160, 140)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            f"background-color: {C.bg_surface}; border-radius: 12px;"
        )
        vbox.addWidget(self._image_label, 0, Qt.AlignCenter)

        self._name_label = QLabel(Path(path).name)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet(
            f"color: {C.text_secondary}; font-size: {T.size_xs}px; background: transparent;"
        )
        vbox.addWidget(self._name_label)

        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.timeout.connect(self._do_load)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected

    def load_async(self, delay: int = 0) -> None:
        self._load_timer.start(delay)

    def _do_load(self) -> None:
        pm = QPixmap(self._path)
        if pm.isNull():
            self._image_label.setText("\u274c")
            return
        scaled = pm.scaled(154, 134, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._image_label.setPixmap(scaled)
        self._image_label.setStyleSheet("background: transparent; border-radius: 12px;")

    def enterEvent(self, event: QEnterEvent) -> None:
        self._image_label.setStyleSheet(
            "background: transparent; border-radius: 12px; "
            f"border: 2px solid {C.accent};"
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._image_label.setStyleSheet("background: transparent; border-radius: 12px;")
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._path)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.LeftButton:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        open_a = QAction("Open", self)
        open_a.triggered.connect(lambda: self.double_clicked.emit(self._path))
        menu.addAction(open_a)
        folder_a = QAction("Open Containing Folder", self)
        folder_a.triggered.connect(self._open_folder)
        menu.addAction(folder_a)
        copy_a = QAction("Copy Path", self)
        copy_a.triggered.connect(self._copy_path)
        menu.addAction(copy_a)
        menu.exec(event.globalPos())

    def _open_folder(self) -> None:
        folder = Path(self._path).parent
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
        except Exception:
            pass

    def _copy_path(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._path)


class _PremiumCarousel(QWidget):
    current_image_changed = Signal(str)
    download_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cards: List[_ThumbnailCard] = []
        self._paths: List[str] = []
        self._selected_path: str = ""

        self.setMinimumHeight(280)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setFrameShape(QScrollArea.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_area.installEventFilter(self)

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._card_layout = QHBoxLayout(self._scroll_content)
        self._card_layout.setContentsMargins(S.xl, S.sm, S.xl, S.sm)
        self._card_layout.setSpacing(S.md)
        self._card_layout.addStretch(1)

        self._scroll_area.setWidget(self._scroll_content)
        outer.addWidget(self._scroll_area, 1)
        self._nav_opacity = 0.0
        self._nav_hovered = False
        self.setMouseTracking(True)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._scroll_area and event.type() == QEvent.Wheel:
            delta = event.angleDelta().y()
            sb = self._scroll_area.horizontalScrollBar()
            sb.setValue(int(sb.value() - delta * 0.5))
            return True
        return super().eventFilter(obj, event)

    def set_images(self, results: List[ImageResultData]) -> None:
        for c in self._cards:
            c.deleteLater()
        self._cards.clear()
        self._paths.clear()

        for i, ir in enumerate(results):
            path = str(ir.output_path or ir.source_path)
            self._paths.append(path)
            card = _ThumbnailCard(path, i, self)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.load_async(delay=i * 30)
            self._cards.append(card)

        for i, card in enumerate(self._cards):
            self._card_layout.insertWidget(i, card, 0, Qt.AlignLeft)

        if self._cards:
            self._cards[0].set_selected(True)
            self._selected_path = self._paths[0]
            self.current_image_changed.emit(self._paths[0])

        for card in self._cards:
            card.show()

    def _on_card_clicked(self, path: str) -> None:
        for c in self._cards:
            c.set_selected(c._path == path)
        self._selected_path = path
        self.current_image_changed.emit(path)

    def _on_card_double_clicked(self, path: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def enterEvent(self, event: QEnterEvent) -> None:
        self._nav_hovered = True
        self._nav_fade(0.6)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._nav_hovered = False
        self._nav_fade(0.0)
        super().leaveEvent(event)

    def _nav_fade(self, target: float) -> None:
        a = QPropertyAnimation(self, b"nav_opacity", self)
        a.setDuration(250)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.setStartValue(self._nav_opacity)
        a.setEndValue(target)
        a.start()

    def _get_nav_op(self) -> float:
        return self._nav_opacity

    def _set_nav_op(self, v: float) -> None:
        self._nav_opacity = v
        self.update()

    nav_opacity = Property(float, _get_nav_op, _set_nav_op)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self._nav_opacity > 0.01:
            for direction in (-1, 1):
                btn_size = 36
                bx = 8 if direction == -1 else w - 8 - btn_size
                by = (h - btn_size) / 2

                c = QColor(C.bg_surface)
                c.setAlpha(int(180 * self._nav_opacity))
                p.setBrush(c)
                p.setPen(QPen(QColor(C.border), 1))
                p.drawRoundedRect(QRectF(bx, by, btn_size, btn_size), btn_size / 2, btn_size / 2)

                p.setPen(QColor(C.text_primary))
                f = QFont(["Inter", "Segoe UI", "sans-serif"], 14)
                p.setFont(f)
                arrow = "\u25C0" if direction == -1 else "\u25B6"
                p.drawText(QRectF(bx, by, btn_size, btn_size), Qt.AlignCenter, arrow)

        p.end()


class _FailedFileCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._collapsed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.xl, S.lg, S.xl, S.lg)
        outer.setSpacing(S.sm)

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

        outer.addLayout(header_row)

        self._list_widget = QListWidget()
        self._list_widget.setFrameShape(QListWidget.NoFrame)
        self._list_widget.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; }}"
            f"QListWidget::item {{ color: {C.text_primary}; padding: {S.xs}px {S.xs}px; "
            f"border-bottom: 1px solid {C.border}; font-size: {T.size_sm}px; }}"
        )
        outer.addWidget(self._list_widget)

    def set_files(self, files: List[str]) -> None:
        self._list_widget.clear()
        for f in files:
            item = QListWidgetItem(f)
            item.setIcon(icon("close", 14, color=str(QColor(C.error).name())))
            self._list_widget.addItem(item)
        self._count_badge.setText(str(len(files)))
        self.setVisible(len(files) > 0)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._list_widget.setVisible(not self._collapsed)
        self._toggle_btn.setText("\u25B6" if self._collapsed else "\u25BC")


class _OutputFolderTile(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._folder_path = ""
        self.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.xl, S.md, S.xl, S.md)
        outer.setSpacing(S.sm)

        header = QLabel("OUTPUT FOLDER")
        header.setStyleSheet(f"color: {C.text_muted}; font-size: {T.size_xs}px; letter-spacing: 1.5px; font-weight: 600;")
        outer.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(S.sm)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet(
            f"color: {C.text_secondary}; font-size: {T.size_sm}px; "
            "font-family: 'Cascadia Mono', 'Consolas', monospace;"
        )
        self._path_label.setWordWrap(True)
        row.addWidget(self._path_label, 1)

        self._open_btn = QPushButton("  Open Folder")
        self._open_btn.setObjectName("GhostButton")
        self._open_btn.setIcon(icon("folder_open", 14))
        self._open_btn.clicked.connect(self._open)
        row.addWidget(self._open_btn)

        self._copy_btn = QPushButton("  Copy Path")
        self._copy_btn.setObjectName("GhostButton")
        self._copy_btn.setIcon(icon("link", 14))
        self._copy_btn.clicked.connect(self._copy)
        row.addWidget(self._copy_btn)

        outer.addLayout(row)

    def set_path(self, path: str) -> None:
        self._folder_path = path
        self._path_label.setText(path)

    def _open(self) -> None:
        if not self._folder_path:
            return
        try:
            if sys.platform == "win32":
                os.startfile(self._folder_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", self._folder_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", self._folder_path])
        except Exception:
            pass

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._folder_path)


class _SummaryTile(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: List[str] = []
        self._entrance_offset = 20.0
        self.setFixedHeight(120)

    def set_items(self, items: List[str]) -> None:
        self._items = items
        self.update()

    def animate_in(self, delay: int = 0) -> QSequentialAnimationGroup:
        anim = QPropertyAnimation(self, b"sum_offset", self)
        anim.setDuration(400)
        anim.setStartValue(20.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        group = QSequentialAnimationGroup(self)
        group.addPause(delay)
        group.addAnimation(anim)
        return group

    def _get_so(self) -> float:
        return self._entrance_offset

    def _set_so(self, v: float) -> None:
        self._entrance_offset = v
        self.update()

    sum_offset = Property(float, _get_so, _set_so)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.translate(0, self._entrance_offset)
        p.setOpacity(max(0.0, 1.0 - self._entrance_offset / 20.0))

        p.setBrush(QColor(C.bg_card))
        p.setPen(QPen(QColor(C.border), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, S.card_radius, S.card_radius)

        f = QFont()
        f.setPointSize(T.size_sm)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        p.setPen(QColor(C.text_secondary))

        y = S.md
        for item in self._items:
            p.drawText(S.xl, y, "\u2713  " + item)
            y += S.lg + S.xs

        p.end()


class ResultsPage(QWidget):
    process_again = Signal()

    def __init__(self, event_bus: EventBus, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")

        self._event_bus = event_bus
        self._result: Optional[PipelineResult] = None
        self._output_folder: str = ""
        self._entered = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        root = QVBoxLayout(inner)
        root.setContentsMargins(S.xxl, S.xl, S.xxl, S.xxl)
        root.setSpacing(S.xl)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(S.lg)

        self._badge = _GlowBadge(True)
        hero_row.addWidget(self._badge, alignment=Qt.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(S.xxs)
        self._title = QLabel("")
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("PageSubtitle")
        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)

        elapsed_container = QWidget()
        elapsed_layout = QVBoxLayout(elapsed_container)
        elapsed_layout.setContentsMargins(0, S.xs, 0, 0)
        elapsed_layout.setSpacing(2)

        elapsed_label = QLabel("DURATION")
        elapsed_label.setStyleSheet(
            f"color: {C.text_muted}; font-size: {T.size_xs}px; "
            "letter-spacing: 1.5px; font-weight: 600;"
        )
        elapsed_label.setAlignment(Qt.AlignRight)
        elapsed_layout.addWidget(elapsed_label)

        self._elapsed_value = QLabel("00:00")
        self._elapsed_value.setStyleSheet(
            f"color: {C.text_primary}; font-size: {T.size_xl}px; font-weight: 700; "
            "font-family: 'Cascadia Mono', 'Consolas', monospace;"
        )
        self._elapsed_value.setAlignment(Qt.AlignRight)
        elapsed_layout.addWidget(self._elapsed_value)

        hero_row.addLayout(titles)
        hero_row.addStretch(1)
        hero_row.addWidget(elapsed_container, alignment=Qt.AlignTop)

        root.addLayout(hero_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(S.md)

        self._stat_total = _StatTile("0", "Total Images", QColor(C.accent))
        self._stat_succeeded = _StatTile("0", "Succeeded", QColor(C.success))
        self._stat_failed = _StatTile("0", "Failed", QColor(C.error))
        self._stat_time = _StatTile("00:00", "Elapsed", QColor(C.text_secondary))

        for st in (self._stat_total, self._stat_succeeded, self._stat_failed, self._stat_time):
            st.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(st)

        root.addLayout(stats_row)

        root.addWidget(_SectionDivider())

        self._summary = _SummaryTile()
        root.addWidget(self._summary)

        self._carousel = _PremiumCarousel()
        self._carousel.setMinimumHeight(280)
        self._carousel.download_requested.connect(self._on_download_image)
        root.addWidget(self._carousel, 1)

        self._failed_card = _FailedFileCard()
        root.addWidget(self._failed_card)

        self._output_tile = _OutputFolderTile()
        root.addWidget(self._output_tile)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.md)
        btn_row.addStretch(1)

        self._again_btn = PrimaryButton("  Process Again")
        self._again_btn.setIcon(icon("refresh", 18, color="#FFFFFF"))
        self._again_btn.clicked.connect(self.process_again.emit)
        btn_row.addWidget(self._again_btn)

        root.addLayout(btn_row)
        root.addStretch(1)

        scroll.setWidget(inner)
        outer_root = QVBoxLayout(self)
        outer_root.setContentsMargins(0, 0, 0, 0)
        outer_root.setSpacing(0)
        outer_root.addWidget(scroll, 1)

    def _play_entrance_sequence(self) -> None:
        if _reduced():
            return

        group = QParallelAnimationGroup(self)
        tiles = [self._stat_total, self._stat_succeeded, self._stat_failed, self._stat_time]
        for i, tile in enumerate(tiles):
            group.addAnimation(tile.animate_in(delay=200 + i * 100))

        group.addAnimation(self._summary.animate_in(delay=700))

        group.start()

    def show_result(self, result: PipelineResult, output_folder: str) -> None:
        self._result = result
        self._output_folder = output_folder

        is_success = result.all_succeeded and not result.cancelled
        is_cancelled = result.cancelled
        has_errors = result.failed > 0

        self._badge._succeeded = is_success
        self._badge.animate_in()

        if is_success:
            self._title.setText("Processing Complete")
            self._title.setStyleSheet(f"color: {C.success};")
            self._subtitle.setText("Every image processed successfully.")
        elif is_cancelled:
            self._title.setText("Processing Cancelled")
            self._title.setStyleSheet(f"color: {C.warning};")
            self._subtitle.setText("The operation was cancelled before completion.")
        elif has_errors:
            self._title.setText("Completed with Errors")
            self._title.setStyleSheet(f"color: {C.error};")
            self._subtitle.setText(f"{result.failed} image(s) could not be processed.")

        self._stat_total.set_value(str(result.total))
        self._stat_succeeded.set_value(str(result.succeeded))
        self._stat_failed.set_value(str(result.failed))
        self._stat_time.set_value(_fmt_time(result.elapsed_seconds))

        self._elapsed_value.setText(_fmt_time(result.elapsed_seconds))

        self._failed_card.set_files(result.failed_files)

        summary_items = []
        if result.succeeded > 0:
            summary_items.append("Background Removed")
            summary_items.append("Upscaled")
            summary_items.append("Resized")
            summary_items.append("Saved Successfully")
        self._summary.set_items(summary_items)

        self._output_tile.set_path(output_folder)

        self._carousel.set_images(result.image_results)

        if not self._entered:
            self._entered = True
            self._play_entrance_sequence()

    def _on_download_image(self, path: str) -> None:
        from PySide6.QtWidgets import QFileDialog
        default_name = Path(path).name
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", default_name,
            "Images (*.png *.jpg *.jpeg *.webp *.tiff);;All Files (*)"
        )
        if save_path:
            import shutil
            try:
                shutil.copy2(path, save_path)
            except Exception as e:
                from core.logger import get_logger
                get_logger(__name__).error(f"Failed to save image: {e}")


class _SectionDivider(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(1)
