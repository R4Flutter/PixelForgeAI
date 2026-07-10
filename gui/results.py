from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPauseAnimation,
    QPointF, QRectF, QSize, Property,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QFontMetrics,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from components.buttons import PrimaryButton, SecondaryButton
from components.carousel import CoverFlowCarousel
from components.icons import icon, pixmap
from core.event_bus import EventBus
from models.pipeline_result import ImageResultData, PipelineResult

from design_system.tokens.colors import Colors as C
from design_system.tokens.spacing import Spacing as S
from design_system.tokens.typography import Typography as T
from design_system.tokens.elevation import Elevation as E


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _fmt_time(seconds: float) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m:02d}:{s:02d}"


class _CinematicBadge(QWidget):
    def __init__(self, succeeded: bool, parent=None) -> None:
        super().__init__(parent)
        self._succeeded = succeeded
        self._arc_progress = 0.0
        self._check_progress = 0.0
        self._pulse = 0.0
        self._glow_opacity = 0.0
        self._glow_phase = 0.0
        self.setFixedSize(96, 96)
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
        r = 38
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
                path.moveTo(cx - 11, cy + 1)
                path.lineTo(cx - 3, cy + 8)
                path.lineTo(cx + 11, cy - 7)
                p.drawPath(path)
            else:
                off = 8
                p.drawLine(QPointF(cx - off, cy - off), QPointF(cx + off, cy + off))
                p.drawLine(QPointF(cx + off, cy - off), QPointF(cx - off, cy + off))
            if self._check_progress < 1.0:
                p.setOpacity(1.0)

        p.end()


class _StatTile(QWidget):
    def __init__(self, icon_name: str, value: str, label: str,
                 color: QColor, parent=None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._value = value
        self._label = label
        self._color = color
        self._hovered = False
        self._entrance_offset = 30.0
        self._entrance_opacity = 0.0
        self.setFixedHeight(104)
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
            bg = QColor(C.bg_surface)
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

        ic = pixmap(self._icon_name, S.icon_size, color=self._color.name())
        p.drawPixmap(S.xl, S.lg, ic)

        f = QFont()
        f.setPointSize(T.size_xxl)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        val_rect = QRectF(S.xl, 44, w - S.xl * 2, 34)
        p.setPen(QColor(C.text_primary))
        p.drawText(val_rect, Qt.AlignLeft | Qt.AlignVCenter, self._value)

        f2 = QFont()
        f2.setPointSize(T.size_xs)
        f2.setWeight(QFont.Medium)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        p.setFont(f2)
        lbl_rect = QRectF(S.xl, 76, w - S.xl * 2, S.lg)
        p.setPen(QColor(C.text_muted))
        p.drawText(lbl_rect, Qt.AlignLeft | Qt.AlignVCenter, self._label.upper())

        p.end()


class _CinematicCarousel(QWidget):
    current_image_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entrance_opacity = 0.0
        self._entrance_offset = 40.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S.md)

        header_row = QHBoxLayout()
        header_row.setSpacing(S.sm)

        ic = QLabel()
        ic.setPixmap(pixmap("image", 16, color=C.text_secondary))
        header_row.addWidget(ic)

        header = QLabel("OUTPUT GALLERY")
        header.setObjectName("SectionLabel")
        header_row.addWidget(header)

        self._count_label = QLabel("0 images")
        self._count_label.setStyleSheet(f"color: {C.text_muted}; font-size: {T.size_sm}px;")
        header_row.addWidget(self._count_label)

        header_row.addStretch(1)

        self._prev_btn = QPushButton()
        self._prev_btn.setObjectName("GhostButton")
        self._prev_btn.setFixedSize(28, 28)
        self._prev_btn.setText("\u25C0")
        self._prev_btn.clicked.connect(self._go_prev)
        header_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton()
        self._next_btn.setObjectName("GhostButton")
        self._next_btn.setFixedSize(28, 28)
        self._next_btn.setText("\u25B6")
        self._next_btn.clicked.connect(self._go_next)
        header_row.addWidget(self._next_btn)

        layout.addLayout(header_row)

        self._carousel = CoverFlowCarousel()
        self._carousel.setMinimumHeight(300)
        self._carousel.current_index_changed.connect(self._on_index_changed)
        layout.addWidget(self._carousel, 1)

        info_row = QHBoxLayout()
        info_row.setSpacing(S.sm)

        self._filename_label = QLabel("")
        self._filename_label.setStyleSheet(f"color: {C.text_secondary}; font-size: {T.size_md}px;")
        self._filename_label.setAlignment(Qt.AlignCenter)
        info_row.addStretch(1)
        info_row.addWidget(self._filename_label)
        info_row.addStretch(1)

        layout.addLayout(info_row)

    def _go_prev(self) -> None:
        self._carousel.select_previous()

    def _go_next(self) -> None:
        self._carousel.select_next()

    def _on_index_changed(self, idx: int) -> None:
        paths = self._carousel.get_paths()
        if 0 <= idx < len(paths):
            name = Path(paths[idx]).name
            self._filename_label.setText(name)
            self.current_image_changed.emit(paths[idx])

    def set_images(self, results: List[ImageResultData]) -> None:
        paths: List[str] = []
        for ir in results:
            p = str(ir.output_path or ir.source_path)
            paths.append(p)
        self._carousel.set_paths(paths)
        self._count_label.setText(f"{len(paths)} images")
        self._filename_label.setText(Path(paths[0]).name if paths else "")
        self.setVisible(len(paths) > 0)

    def animate_in(self, delay: int = 0) -> QSequentialAnimationGroup:
        anim = QPropertyAnimation(self, b"entrance_offset", self)
        anim.setDuration(600)
        anim.setStartValue(40.0)
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
        self._entrance_opacity = max(0.0, 1.0 - v / 40.0)
        self.update()

    entrance_offset = Property(float, _get_offset, _set_offset)

    def paintEvent(self, event) -> None:
        if self._entrance_opacity < 1.0:
            p = QPainter(self)
            p.setOpacity(1.0 - self._entrance_opacity)
            p.fillRect(self.rect(), QColor(C.bg_primary))
            p.end()
        super().paintEvent(event)


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

        warn_ic = QLabel()
        warn_ic.setPixmap(pixmap("warn", 16, color=str(QColor(C.warning).name())))
        header_row.addWidget(warn_ic)

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


class _SectionDivider(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(1)


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

        self._badge = _CinematicBadge(True)
        hero_row.addWidget(self._badge, alignment=Qt.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(S.xxs)
        self._title = QLabel("All done!")
        self._title.setObjectName("PageTitle")
        self._title.setStyleSheet(f"color: {C.success};")
        self._subtitle = QLabel("Every image processed successfully.")
        self._subtitle.setObjectName("PageSubtitle")
        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)

        elapsed_container = QWidget()
        elapsed_container.setFixedWidth(120)
        elapsed_layout = QVBoxLayout(elapsed_container)
        elapsed_layout.setContentsMargins(0, S.xs, 0, 0)
        elapsed_layout.setSpacing(2)

        elapsed_label = QLabel("ELAPSED")
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

        self._stat_total = _StatTile("image", "0", "Total Images", QColor(C.accent))
        self._stat_succeeded = _StatTile("check", "0", "Succeeded", QColor(C.success))
        self._stat_failed = _StatTile("close", "0", "Failed", QColor(C.error))
        self._stat_time = _StatTile("clock", "00:00", "Elapsed", QColor(C.text_secondary))

        for st in (self._stat_total, self._stat_succeeded, self._stat_failed, self._stat_time):
            st.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            stats_row.addWidget(st)

        root.addLayout(stats_row)

        root.addWidget(_SectionDivider())

        self._carousel = _CinematicCarousel()
        self._carousel.setMinimumHeight(340)
        root.addWidget(self._carousel, 1)

        self._failed_card = _FailedFileCard()
        root.addWidget(self._failed_card)

        root.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.md)
        btn_row.addStretch(1)

        self._open_btn = SecondaryButton("  Open Output Folder")
        self._open_btn.setIcon(icon("folder_open", 18))
        self._open_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(self._open_btn)

        self._again_btn = PrimaryButton("  Process Again")
        self._again_btn.setIcon(icon("refresh", 18, color="#FFFFFF"))
        self._again_btn.clicked.connect(self.process_again.emit)
        btn_row.addWidget(self._again_btn)

        root.addLayout(btn_row)

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

        group.addAnimation(self._carousel.animate_in(delay=700))

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
            self._title.setText("All done!")
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

        self._carousel.set_images(result.image_results)

        if not self._entered:
            self._entered = True
            self._play_entrance_sequence()

    def _open_folder(self) -> None:
        folder = self._output_folder
        if not folder:
            return
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            from core.logger import get_logger
            get_logger(__name__).error(f"Failed to open folder: {e}")
