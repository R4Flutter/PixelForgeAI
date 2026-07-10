from __future__ import annotations

import math
import os
from typing import List, Optional, Sequence

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QPoint, QRect, QRectF, QSize,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from backend.job import (
    IMAGE_SUFFIXES, BackgroundMode, ConflictPolicy, FitMode,
    OutputFormat, QualityPreset, Settings, UpscaleMode,
)
from components.cards import DropZone
from components.carousel import CoverFlowCarousel
from components.icons import pixmap


_COLOR_ACTIVE = "#7C5CFF"
_COLOR_COMPLETED = "#34D399"
_COLOR_WAITING = "#6B7280"
_COLOR_BG = "#09090B"
_COLOR_SURFACE = "#12141C"
_COLOR_BORDER = "#1E2230"
_COLOR_TEXT_PRIMARY = "#F4F5FB"
_COLOR_TEXT_SECONDARY = "#8A90A6"
_COLOR_TEXT_MUTED = "#6B7186"


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


class _AmbientBg(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._angle = 0.0
        self._pulse = 0.0
        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(50)
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    def _tick(self) -> None:
        self._angle += 0.006
        self._pulse += 0.03
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        cx = w / 2 + math.cos(self._angle) * 60
        cy = h * 0.35 + math.sin(self._angle * 0.7) * 40

        g1 = QRadialGradient(cx, cy, max(w, h) * 0.65)
        g1.setColorAt(0.0, QColor(15, 15, 35, 0))
        g1.setColorAt(0.4, QColor(20, 18, 50, 25))
        g1.setColorAt(1.0, QColor(11, 12, 16, 0))
        p.fillRect(self.rect(), QBrush(g1))

        g2 = QRadialGradient(cx, cy, max(w, h) * 0.45)
        g2.setColorAt(0.0, QColor(99, 102, 241, 10))
        g2.setColorAt(0.5, QColor(139, 92, 246, 5))
        g2.setColorAt(1.0, QColor(11, 12, 16, 0))
        p.fillRect(self.rect(), QBrush(g2))

        g3 = QRadialGradient(w / 2, 0, max(w, h) * 0.35)
        g3.setColorAt(0.0, QColor(124, 92, 255, 6))
        g3.setColorAt(1.0, QColor(11, 12, 16, 0))
        p.fillRect(self.rect(), QBrush(g3))
        p.end()


class _FlowPresetBar(QWidget):
    current_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._presets = ["Print Ready", "Photo Enhancement", "Transparent Assets", "Marketplace", "Custom"]
        self._current = "Print Ready"
        self._buttons: List[QPushButton] = []
        self.setFixedHeight(40)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        for name in self._presets:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setStyleSheet(self._style_for(name, name == self._current))
            btn.clicked.connect(lambda _checked=False, n=name: self._select(n))
            self._buttons.append(btn)
            lay.addWidget(btn)
            if name != self._presets[-1]:
                sep = QLabel()
                sep.setFixedWidth(16)
                sep.setStyleSheet("color: #2B3042; font-size: 14px;")
                sep.setAlignment(Qt.AlignCenter)
                lay.addWidget(sep)

        lay.addStretch(1)

    def _style_for(self, name: str, active: bool) -> str:
        if active:
            return (
                "QPushButton { background-color: #1A1552; color: #7C5CFF; border: 1px solid #7C5CFF; "
                "border-radius: 6px; padding: 4px 14px; font-size: 11px; font-weight: 600; }"
            )
        return (
            "QPushButton { background-color: transparent; color: #6B7186; border: 1px solid #2B3042; "
            "border-radius: 6px; padding: 4px 14px; font-size: 11px; font-weight: 500; }"
            "QPushButton:hover { background-color: #161922; color: #C4C8D6; border-color: #383E54; }"
        )

    def _select(self, name: str) -> None:
        self._current = name
        for btn in self._buttons:
            active = btn.text() == name
            btn.setChecked(active)
            btn.setStyleSheet(self._style_for(btn.text(), active))
        self.current_changed.emit(name)


class _PipelineCard(QWidget):
    toggled = Signal(str, bool)

    def __init__(self, title: str, subtitle: str, icon_svg: str,
                 expanded: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        self._animating = False

        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)

        self._body_layout = QVBoxLayout(self)
        self._body_layout.setContentsMargins(14, 10, 14, 10)
        self._body_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(10)

        self._arrow = QLabel(" \u25B6" if not expanded else " \u25BC")
        self._arrow.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 9px;")
        hlay.addWidget(self._arrow)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(True)
        self._checkbox.setStyleSheet(
            "QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;"
            " border: 1px solid #262A37; }"
            "QCheckBox::indicator:checked { background-color: #7C5CFF;"
            " border-color: #7C5CFF; }"
        )
        hlay.addWidget(self._checkbox)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(pixmap(icon_svg, 18, color=_COLOR_TEXT_PRIMARY))
        hlay.addWidget(icon_lbl)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(f"color: {_COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 600;")
        self._sub_lbl = QLabel(subtitle)
        self._sub_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        texts.addWidget(t)
        texts.addWidget(self._sub_lbl)
        hlay.addLayout(texts, 1)

        self._body_layout.addWidget(header)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(28, 8, 4, 4)
        self._content_layout.setSpacing(6)

        if expanded:
            self._content.setVisible(True)
            self._content.setMaximumHeight(16777215)
        else:
            self._content.setVisible(False)
            self._content.setMaximumHeight(0)

        self._body_layout.addWidget(self._content)
        self._update_style()

    def set_content_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def set_subtitle(self, text: str) -> None:
        self._sub_lbl.setText(text)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded or self._animating:
            return
        self._expanded = expanded
        if expanded:
            self._animate_expand()
        else:
            self._animate_collapse()
        self.toggled.emit(self._title, expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _animate_expand(self) -> None:
        self._animating = True
        self._arrow.setText(" \u25BC")

        self._content.setVisible(True)
        self._content.setMaximumHeight(16777215)
        target = self._content.sizeHint().height()
        if target <= 0:
            target = 200

        self._content.setMaximumHeight(0)

        anim = QPropertyAnimation(self._content, b"maximumHeight", self)
        anim.setDuration(200 if not _reduced() else 1)
        anim.setStartValue(0)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self._on_expand_finished)
        anim.start()

    def _on_expand_finished(self) -> None:
        self._content.setMaximumHeight(16777215)
        self._animating = False
        self._update_style()

    def _animate_collapse(self) -> None:
        self._animating = True
        self._arrow.setText(" \u25B6")

        current = self._content.maximumHeight()
        if current > 10000:
            current = self._content.height()
            if current <= 0:
                current = self._content.sizeHint().height()
            if current <= 0:
                current = 200
            self._content.setMaximumHeight(current)

        anim = QPropertyAnimation(self._content, b"maximumHeight", self)
        anim.setDuration(200 if not _reduced() else 1)
        anim.setStartValue(current)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self._on_collapse_finished)
        anim.start()

    def _on_collapse_finished(self) -> None:
        self._content.setVisible(False)
        self._content.setMaximumHeight(0)
        self._animating = False
        self._update_style()

    def _update_style(self) -> None:
        if self._expanded:
            self.setStyleSheet(
                f"#Card {{ background-color: #1A1552; border: 1px solid"
                f" {_COLOR_ACTIVE}; border-radius: 10px; }}"
            )
        else:
            self.setStyleSheet(
                f"#Card {{ background-color: {_COLOR_SURFACE};"
                f" border: 1px solid {_COLOR_BORDER}; border-radius: 10px; }}"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._animating:
            chk_global = self._checkbox.mapToGlobal(QPoint(0, 0))
            chk_local = self.mapFromGlobal(chk_global)
            chk_rect = QRect(chk_local, self._checkbox.size())
            if not chk_rect.contains(event.pos()):
                self.toggle()
        super().mousePressEvent(event)


class _JobInfoPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        title = QLabel("JOB INFO")
        title.setObjectName("SectionLabel")
        outer.addWidget(title)

        grid = QWidget()
        glay = QVBoxLayout(grid)
        glay.setContentsMargins(0, 0, 0, 0)
        glay.setSpacing(6)

        self._stats: List[QLabel] = []
        for label in ("Images", "Photos", "Illustrations", "Est. RAM", "Est. Time", "Output Size"):
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
            val = QLabel("--")
            val.setStyleSheet(f"color: {_COLOR_TEXT_PRIMARY}; font-size: 10px; font-weight: 600;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row.addWidget(lbl, 1)
            row.addWidget(val)
            glay.addLayout(row)
            self._stats.append(val)

        outer.addWidget(grid)

    def update_stats(self, count: int) -> None:
        vals = [
            str(count),
            str(max(0, count - count // 3)),
            str(count // 3),
            f"{count * 18} MB",
            f"{count * 3}s",
            f"{count * 24} MB",
        ]
        for lbl, v in zip(self._stats, vals):
            lbl.setText(v)


class _PipelineCardSettings(QWidget):
    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings = Settings()

    def apply_to(self, settings: Settings) -> None:
        pass

    def load_from(self, settings: Settings) -> None:
        pass


class _RemoveBgSettings(_PipelineCardSettings):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        m_lbl = QLabel("Method")
        m_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._method = QComboBox()
        self._method.addItems(["Auto", "AI", "Poster", "Anime", "Solid Color"])
        self._method.setStyleSheet(
            "QComboBox { background: #0E0F14; border: 1px solid #262A37; border-radius: 5px; "
            "padding: 3px 8px; font-size: 10px; color: #E6E8F0; min-height: 18px; }"
        )
        row1.addWidget(m_lbl)
        row1.addWidget(self._method, 1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        s_lbl = QLabel("Sensitivity")
        s_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._sensitivity = QSlider(Qt.Horizontal)
        self._sensitivity.setRange(0, 100)
        self._sensitivity.setValue(50)
        self._sensitivity.setStyleSheet(
            "QSlider::groove:horizontal { background: #262A37; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #7C5CFF; width: 12px; height: 12px; "
            "margin: -4px 0; border-radius: 6px; }"
        )
        row2.addWidget(s_lbl)
        row2.addWidget(self._sensitivity, 1)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        f_lbl = QLabel("Feather")
        f_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._feather = QSpinBox()
        self._feather.setRange(0, 20)
        self._feather.setValue(2)
        self._feather.setStyleSheet(
            "QSpinBox { background: #0E0F14; border: 1px solid #262A37; border-radius: 5px; "
            "padding: 3px 8px; font-size: 10px; color: #E6E8F0; min-height: 18px; }"
        )
        row3.addWidget(f_lbl)
        row3.addWidget(self._feather, 1)
        lay.addLayout(row3)

        self._shadow_removal = QCheckBox("Shadow Removal")
        self._shadow_removal.setStyleSheet(
            f"QCheckBox {{ color: {_COLOR_TEXT_SECONDARY}; font-size: 10px; spacing: 6px; }}"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #262A37; }"
            "QCheckBox::indicator:checked { background-color: #7C5CFF; border-color: #7C5CFF; }"
        )
        lay.addWidget(self._shadow_removal)


class _UpscaleSettings(_PipelineCardSettings):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        scale_lbl = QLabel("Scale")
        scale_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        lay.addWidget(scale_lbl)
        scale_row = QHBoxLayout()
        scale_row.setSpacing(6)
        self._scale_btns: List[QPushButton] = []
        for s in ["1x", "2x", "4x", "8x"]:
            btn = QPushButton(s)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            active = s == "4x"
            btn.setChecked(active)
            btn.setStyleSheet(self._scale_style(active))
            btn.clicked.connect(lambda _checked=False, b=btn, sv=s: self._select_scale(sv))
            self._scale_btns.append(btn)
            scale_row.addWidget(btn)
        lay.addLayout(scale_row)

        self._sharpen = QCheckBox("Sharpen")
        self._sharpen.setChecked(True)
        self._sharpen.setStyleSheet(
            f"QCheckBox {{ color: {_COLOR_TEXT_SECONDARY}; font-size: 10px; spacing: 6px; }}"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #262A37; }"
            "QCheckBox::indicator:checked { background-color: #7C5CFF; border-color: #7C5CFF; }"
        )
        lay.addWidget(self._sharpen)

        self._denoise = QCheckBox("Denoise")
        self._denoise.setChecked(True)
        self._denoise.setStyleSheet(self._sharpen.styleSheet())
        lay.addWidget(self._denoise)

    def _scale_style(self, active: bool) -> str:
        if active:
            return (
                "QPushButton { background-color: #1A1552; color: #7C5CFF; border: 1px solid #7C5CFF; "
                "border-radius: 5px; font-size: 10px; font-weight: 600; padding: 2px 10px; }"
            )
        return (
            "QPushButton { background-color: #0E0F14; color: #6B7280; border: 1px solid #262A37; "
            "border-radius: 5px; font-size: 10px; padding: 2px 10px; }"
            "QPushButton:hover { border-color: #383E54; color: #C4C8D6; }"
        )

    def _select_scale(self, scale: str) -> None:
        for btn in self._scale_btns:
            active = btn.text() == scale
            btn.setChecked(active)
            btn.setStyleSheet(self._scale_style(active))


class _ResizeSettings(_PipelineCardSettings):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        row_w = QHBoxLayout()
        w_lbl = QLabel("Width")
        w_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._width = QSpinBox()
        self._width.setRange(64, 12000)
        self._width.setValue(4000)
        self._width.setSingleStep(100)
        self._width.setStyleSheet(
            "QSpinBox { background: #0E0F14; border: 1px solid #262A37; border-radius: 5px; "
            "padding: 3px 8px; font-size: 10px; color: #E6E8F0; min-height: 18px; }"
        )
        row_w.addWidget(w_lbl)
        row_w.addWidget(self._width, 1)
        lay.addLayout(row_w)

        row_h = QHBoxLayout()
        h_lbl = QLabel("Height")
        h_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._height = QSpinBox()
        self._height.setRange(64, 12000)
        self._height.setValue(4000)
        self._height.setSingleStep(100)
        self._height.setStyleSheet(self._width.styleSheet())
        row_h.addWidget(h_lbl)
        row_h.addWidget(self._height, 1)
        lay.addLayout(row_h)

        self._lock = QCheckBox("Lock Aspect Ratio")
        self._lock.setChecked(True)
        self._lock.setStyleSheet(
            f"QCheckBox {{ color: {_COLOR_TEXT_SECONDARY}; font-size: 10px; spacing: 6px; }}"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #262A37; }"
            "QCheckBox::indicator:checked { background-color: #7C5CFF; border-color: #7C5CFF; }"
        )
        lay.addWidget(self._lock)

        fit_lbl = QLabel("Fit Mode")
        fit_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        lay.addWidget(fit_lbl)
        self._fit = QComboBox()
        self._fit.addItems(["Contain", "Fill", "Stretch"])
        self._fit.setStyleSheet(
            "QComboBox { background: #0E0F14; border: 1px solid #262A37; border-radius: 5px; "
            "padding: 3px 8px; font-size: 10px; color: #E6E8F0; min-height: 18px; }"
        )
        lay.addWidget(self._fit)


class _OutputSettings(_PipelineCardSettings):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        row_f = QHBoxLayout()
        f_lbl = QLabel("Format")
        f_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._format = QComboBox()
        self._format.addItems(["PNG", "JPG", "WEBP", "TIFF"])
        self._format.setStyleSheet(
            "QComboBox { background: #0E0F14; border: 1px solid #262A37; border-radius: 5px; "
            "padding: 3px 8px; font-size: 10px; color: #E6E8F0; min-height: 18px; }"
        )
        row_f.addWidget(f_lbl)
        row_f.addWidget(self._format, 1)
        lay.addLayout(row_f)

        row_c = QHBoxLayout()
        c_lbl = QLabel("Compression")
        c_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 10px;")
        self._compression = QSlider(Qt.Horizontal)
        self._compression.setRange(0, 9)
        self._compression.setValue(6)
        self._compression.setStyleSheet(
            "QSlider::groove:horizontal { background: #262A37; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #7C5CFF; width: 12px; height: 12px; "
            "margin: -4px 0; border-radius: 6px; }"
        )
        row_c.addWidget(c_lbl)
        row_c.addWidget(self._compression, 1)
        lay.addLayout(row_c)

        self._transparent = QCheckBox("Transparent Background")
        self._transparent.setChecked(True)
        self._transparent.setStyleSheet(
            f"QCheckBox {{ color: {_COLOR_TEXT_SECONDARY}; font-size: 10px; spacing: 6px; }}"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #262A37; }"
            "QCheckBox::indicator:checked { background-color: #7C5CFF; border-color: #7C5CFF; }"
        )
        lay.addWidget(self._transparent)


class _PropertiesPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._current = "Remove Background"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        self._panel_title = QLabel("PROPERTIES")
        self._panel_title.setObjectName("SectionLabel")
        outer.addWidget(self._panel_title)

        self._card_title = QLabel("Remove Background Settings")
        self._card_title.setStyleSheet(f"color: {_COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        outer.addWidget(self._card_title)

        self._settings_stack = QWidget()
        self._stack_lay = QVBoxLayout(self._settings_stack)
        self._stack_lay.setContentsMargins(0, 0, 0, 0)
        self._stack_lay.setSpacing(0)

        self._settings_widgets: dict[str, _PipelineCardSettings] = {
            "Remove Background": _RemoveBgSettings(),
            "AI Upscale": _UpscaleSettings(),
            "Resize": _ResizeSettings(),
            "Output": _OutputSettings(),
        }
        for w in self._settings_widgets.values():
            w.setVisible(False)
            self._stack_lay.addWidget(w)

        self._settings_widgets["Remove Background"].setVisible(True)
        outer.addWidget(self._settings_stack, 1)

        outer.addStretch(1)

    def show_panel(self, name: str) -> None:
        self._current = name
        self._card_title.setText(f"{name} Settings")
        for n, w in self._settings_widgets.items():
            w.setVisible(n == name)


class _OutputSettingsBar(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(24)

        def _make_field(label: str, widget: QWidget) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 11px; font-weight: 500;")
            row.addWidget(lbl)
            row.addWidget(widget, 1)
            return row

        dest_lbl = QLabel("Destination")
        dest_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        self._dest = QLabel("output/final")
        self._dest.setStyleSheet(
            f"color: {_COLOR_TEXT_PRIMARY}; font-size: 11px; background: #0E0F14; "
            "border: 1px solid #262A37; border-radius: 5px; padding: 4px 10px;"
        )
        self._browse_dest = QPushButton("Browse")
        self._browse_dest.setStyleSheet(
            "QPushButton { background: #1C1F2B; color: #C4C8D6; border: 1px solid #2B3042; "
            "border-radius: 5px; font-size: 10px; padding: 4px 12px; }"
            "QPushButton:hover { background: #232737; }"
        )
        dest_row = QHBoxLayout()
        dest_row.setSpacing(6)
        dest_row.addWidget(dest_lbl)
        dest_row.addWidget(self._dest, 1)
        dest_row.addWidget(self._browse_dest)
        lay.addLayout(dest_row)

        conflict_lbl = QLabel("Conflict")
        conflict_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        self._conflict = QComboBox()
        self._conflict.addItems(["Replace", "Skip", "Rename"])
        self._conflict.setStyleSheet(
            "QComboBox { background: #0E0F14; border: 1px solid #262A37; border-radius: 5px; "
            "padding: 3px 8px; font-size: 10px; color: #E6E8F0; min-height: 18px; }"
        )
        conflict_row = QHBoxLayout()
        conflict_row.setSpacing(8)
        conflict_row.addWidget(conflict_lbl)
        conflict_row.addWidget(self._conflict)
        lay.addLayout(conflict_row)

        naming_lbl = QLabel("Naming")
        naming_lbl.setStyleSheet(f"color: {_COLOR_TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        self._naming = QComboBox()
        self._naming.addItems(["Original", "Suffix", "Prefix"])
        self._naming.setStyleSheet(self._conflict.styleSheet())
        naming_row = QHBoxLayout()
        naming_row.setSpacing(8)
        naming_row.addWidget(naming_lbl)
        naming_row.addWidget(self._naming)
        lay.addLayout(naming_row)

        self._naming_suffix = QLabel("_processed")
        self._naming_suffix.setStyleSheet(
            f"color: {_COLOR_TEXT_PRIMARY}; font-size: 11px; background: #0E0F14; "
            "border: 1px solid #262A37; border-radius: 5px; padding: 4px 10px;"
        )
        lay.addWidget(self._naming_suffix)

        self._open_after = QCheckBox("Open After")
        self._open_after.setChecked(True)
        self._open_after.setStyleSheet(
            f"QCheckBox {{ color: {_COLOR_TEXT_SECONDARY}; font-size: 10px; spacing: 6px; }}"
            "QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #262A37; }"
            "QCheckBox::indicator:checked { background-color: #7C5CFF; border-color: #7C5CFF; }"
        )
        lay.addWidget(self._open_after)


class _StartProcessingButton(QWidget):
    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._count = 0
        self._enabled = False
        self._pulse = 0.0
        self._hovered = False
        self.setFixedHeight(58)
        self.setCursor(Qt.PointingHandCursor)

        if not _reduced():
            self._timer = QTimer(self)
            self._timer.setInterval(30)
            self._timer.timeout.connect(lambda: (setattr(self, "_pulse", self._pulse + 0.02) or self.update()))
            self._timer.start()

    def set_count(self, count: int) -> None:
        self._count = count
        self._enabled = count > 0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = 12

        if self._enabled:
            pulse = 0.5 + 0.15 * math.sin(self._pulse * 2 * math.pi / 60) if not _reduced() else 0.65
            c = QColor(124, 92, 255)
            c.setAlpha(int(min(255, 40 * pulse)))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(0, 0, w, h, r, r)

            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0.0, QColor("#7C5CFF"))
            g.setColorAt(0.5, QColor("#8B5CF6"))
            g.setColorAt(1.0, QColor("#6366F1"))
            p.setBrush(QBrush(g))
            p.setPen(QPen(QColor("#9A7CFF"), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, r, r)
        else:
            p.setBrush(QColor("#1A1D2B"))
            p.setPen(QPen(QColor("#2B3042"), 1))
            p.drawRoundedRect(0, 0, w - 1, h - 1, r, r)

        f = QFont()
        f.setPointSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF") if self._enabled else QColor("#54586A"))
        p.drawText(QRectF(0, 6, w, 24), Qt.AlignCenter, "START PROCESSING")

        f2 = QFont()
        f2.setPointSize(9)
        f2.setWeight(QFont.Normal)
        p.setFont(f2)
        p.setPen(QColor(255, 255, 255, 160) if self._enabled else QColor("#4F5364"))
        info = f"{self._count} Images" if self._count > 0 else "Add images to begin"
        p.drawText(QRectF(0, 30, w, 18), Qt.AlignCenter, info)

        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._enabled:
            self.clicked.emit()
        super().mousePressEvent(event)


class _PreviewBadgeGrid(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._paths: List[str] = []
        self.setMinimumHeight(64)

    def set_paths(self, paths: Sequence[str]) -> None:
        self._paths = list(paths)
        self.update()

    def add_paths(self, paths: Sequence[str]) -> None:
        existing = set(self._paths)
        for p in paths:
            if p not in existing:
                self._paths.append(p)
                existing.add(p)
        self.update()

    def get_paths(self) -> List[str]:
        return list(self._paths)

    def clear(self) -> None:
        self._paths.clear()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w = self.width()
        h = self.height()

        if not self._paths:
            p.setPen(QColor(_COLOR_TEXT_MUTED))
            f = QFont()
            f.setPointSize(10)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No images selected")
            p.end()
            return

        thumb_size = 42
        gap = 8
        radius = 6
        max_visible = min(len(self._paths), (w + gap) // (thumb_size + gap))
        remaining = len(self._paths) - max_visible

        for i in range(max_visible):
            x = 0 + i * (thumb_size + gap)
            pm = QPixmap(self._paths[i])
            if pm.isNull():
                p.setBrush(QColor("#1A1D2B"))
                p.setPen(QPen(QColor("#2B3042"), 1))
                p.drawRoundedRect(x, (h - thumb_size) // 2, thumb_size, thumb_size, radius, radius)
            else:
                scaled = pm.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                path = QPainterPath()
                path.addRoundedRect(x, (h - thumb_size) // 2, thumb_size, thumb_size, radius, radius)
                p.setClipPath(path)
                ox = x + (thumb_size - scaled.width()) // 2
                oy = (h - thumb_size) // 2 + (thumb_size - scaled.height()) // 2
                p.drawPixmap(ox, oy, scaled)
                p.setClipping(False)

            badge_type = "Photo" if i % 3 != 0 else "Vector"
            badge_color = _COLOR_ACTIVE if badge_type == "Photo" else "#FBBF24"
            bx = x + thumb_size - 14
            by = (h - thumb_size) // 2 - 2
            p.setBrush(QColor(badge_color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(bx, by, 14, 12, 4, 4)
            f2 = QFont()
            f2.setPointSize(6)
            f2.setWeight(QFont.Bold)
            p.setFont(f2)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(QRectF(bx, by, 14, 12), Qt.AlignCenter, "P" if badge_type == "Photo" else "V")

        if remaining > 0:
            x = max_visible * (thumb_size + gap)
            p.setBrush(QColor("#1A1D2B"))
            p.setPen(QPen(QColor("#2B3042"), 1))
            p.drawRoundedRect(x, (h - thumb_size) // 2, thumb_size, thumb_size, radius, radius)
            f3 = QFont()
            f3.setPointSize(10)
            f3.setWeight(QFont.DemiBold)
            p.setFont(f3)
            p.setPen(QColor(_COLOR_TEXT_SECONDARY))
            p.drawText(QRectF(x, (h - thumb_size) // 2, thumb_size, thumb_size), Qt.AlignCenter, f"+{remaining}")

        p.end()


class HomePage(QWidget):
    start_requested = Signal(list)
    selection_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageContainer")

        self._bg = _AmbientBg(self)
        self._glow = QWidget(self)
        self._glow.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._glow.setStyleSheet("background: transparent;")

        self._settings = Settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollBar:vertical { background: transparent; width: 8px; }"
                             "QScrollBar::handle:vertical { background: #262A37; border-radius: 4px; min-height: 20px; }"
                             "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(28, 20, 28, 20)
        inner_lay.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        title = QLabel("Pipeline Builder")
        title.setObjectName("PageTitle")
        top_row.addWidget(title)
        top_row.addStretch(1)
        self._flow_bar = _FlowPresetBar()
        top_row.addWidget(self._flow_bar, 1)
        inner_lay.addLayout(top_row)

        main_content = QHBoxLayout()
        main_content.setSpacing(14)

        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        self._drop = DropZone()
        self._drop.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_col.addWidget(self._drop)

        self._job_info = _JobInfoPanel()
        left_col.addWidget(self._job_info, 1)

        self._badge_grid = CoverFlowCarousel()
        self._badge_grid.setMinimumHeight(260)
        self._badge_grid.setStyleSheet("background: transparent; border: none;")
        self._badge_grid.images_changed.connect(self._on_count_changed)
        left_col.addWidget(self._badge_grid, 2)

        main_content.addLayout(left_col, 2)

        pipe_col = QVBoxLayout()
        pipe_col.setSpacing(12)
        pipe_label = QLabel("PIPELINE")
        pipe_label.setObjectName("SectionLabel")
        pipe_col.addWidget(pipe_label)

        self._pipeline_cards: List[_PipelineCard] = []
        self._active_card = "Remove Background"
        pipeline_defs = [
            ("Remove Background", "Method: Auto", "cpu"),
            ("AI Upscale", "Scale: 4x", "gpu"),
            ("Resize", "4000 x 4000", "resize"),
            ("Output", "PNG  •  Compression: 6", "format"),
        ]
        for title, subtitle, icon_name in pipeline_defs:
            card = _PipelineCard(title, subtitle, icon_name,
                                 expanded=title == "Remove Background")
            card.toggled.connect(self._on_card_toggled)
            if title == "Remove Background":
                card.set_content_widget(_RemoveBgSettings())
            elif title == "AI Upscale":
                card.set_content_widget(_UpscaleSettings())
            elif title == "Resize":
                card.set_content_widget(_ResizeSettings())
            elif title == "Output":
                card.set_content_widget(_OutputSettings())
            self._pipeline_cards.append(card)
            pipe_col.addWidget(card)

        pipe_col.addStretch(1)
        main_content.addLayout(pipe_col, 2)

        self._props_panel = _PropertiesPanel()
        main_content.addWidget(self._props_panel, 2)

        inner_lay.addLayout(main_content, 1)

        self._output_bar = _OutputSettingsBar()
        inner_lay.addWidget(self._output_bar)

        start_row = QHBoxLayout()
        start_row.setSpacing(14)
        start_row.addStretch(1)
        self._process = _StartProcessingButton()
        self._process.setFixedWidth(400)
        self._process.clicked.connect(self._emit_start)
        start_row.addWidget(self._process)
        start_row.addStretch(1)
        inner_lay.addLayout(start_row)

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self._drop.urls_dropped.connect(self._on_drop)
        self._drop.clicked.connect(self._browse_files)
        self._flow_bar.current_changed.connect(self._on_flow_changed)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())
        self._glow.setGeometry(self.rect())

    def _on_card_toggled(self, title: str, expanded: bool) -> None:
        if expanded:
            self._active_card = title
            for card in self._pipeline_cards:
                if card._title != title and card.is_expanded():
                    card.set_expanded(False)
            self._props_panel.show_panel(title)

    def _on_flow_changed(self, preset: str) -> None:
        pass

    def _on_drop(self, paths: list) -> None:
        self._badge_grid.add_paths(paths)
        self._on_count_changed()

    def _on_count_changed(self, *_args) -> None:
        count = len(self._badge_grid.get_paths())
        self._job_info.update_stats(count)
        self._process.set_count(count)
        self._process.update()
        self.selection_changed.emit(count)

    def set_images(self, paths: Sequence[str]) -> None:
        self._badge_grid.set_paths(paths)
        self._on_count_changed()

    def add_images(self, paths: Sequence[str]) -> None:
        self._badge_grid.add_paths(paths)
        self._on_count_changed()

    def clear(self) -> None:
        self._badge_grid.clear()
        self._on_count_changed()

    def selected_paths(self) -> List[str]:
        return self._badge_grid.get_paths()

    def _browse_files(self) -> None:
        filt = "Images (" + " ".join("*" + s for s in IMAGE_SUFFIXES) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, "Select images", "", filt)
        if paths:
            self._badge_grid.add_paths(paths)
            self._on_count_changed()

    def _emit_start(self) -> None:
        paths = self._badge_grid.get_paths()
        if not paths:
            return
        self.start_requested.emit(paths)
