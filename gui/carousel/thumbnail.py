from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QUrl, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QAction, QDesktopServices,
    QEnterEvent, QMouseEvent, QClipboard,
)
from PySide6.QtWidgets import (
    QWidget, QApplication, QMenu,
)

from design_system.tokens.colors import Colors as C
from design_system.tokens.spacing import Spacing as S
from design_system.tokens.typography import Typography as T


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _thumb_path(output_path: str) -> str:
    p = Path(output_path)
    return str(p.parent / f"{p.stem}_thumb{p.suffix}")


def _ensure_thumbnail(output_path: str, size: int = 100) -> str:
    tp = _thumb_path(output_path)
    if Path(tp).exists():
        return tp
    pm = QPixmap(output_path)
    if pm.isNull():
        return output_path
    thumb = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    thumb.save(tp, "PNG")
    return tp


class ThumbnailWidget(QWidget):
    clicked = Signal(str)
    double_clicked = Signal(str)

    def __init__(self, output_path: str, index: int, parent=None) -> None:
        super().__init__(parent)
        self._path = output_path
        self._index = index
        self._selected = False
        self._hovered = False
        self._loaded = False
        self._glow = 0.0
        self._glow_dir = 1
        self._thumb: Optional[QPixmap] = None

        self.setFixedSize(150, 160)
        self.setCursor(Qt.PointingHandCursor)

        tp = _ensure_thumbnail(output_path)
        pm = QPixmap(tp)
        if not pm.isNull():
            self._thumb = pm
            self._loaded = True

        if not _reduced():
            self._glow_timer = QTimer(self)
            self._glow_timer.setInterval(16)
            self._glow_timer.timeout.connect(self._tick_glow)
            self._glow_timer.start()

    def _tick_glow(self) -> None:
        if self._selected:
            self._glow += 0.02 * self._glow_dir
            if self._glow > 1.0:
                self._glow = 1.0
                self._glow_dir = -1
            elif self._glow < 0.5:
                self._glow = 0.5
                self._glow_dir = 1
            self.update()
        elif self._hovered:
            self._glow = min(1.0, self._glow + 0.05)
            self.update()
        else:
            if self._glow > 0:
                self._glow = max(0.0, self._glow - 0.05)
                self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._path)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.LeftButton:
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
        QApplication.clipboard().setText(self._path)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        if self._selected:
            glow_w = 3 + 2 * self._glow
            glow_c = QColor(C.accent)
            glow_c.setAlpha(int(80 + 60 * self._glow))
            p.setPen(QPen(glow_c, glow_w))
            p.setBrush(QColor(C.bg_card))
            p.drawRoundedRect(2, 2, w - 4, h - 4, 14, 14)
            sel_glow = QRadialGradient(w / 2, h / 2, w * 0.6)
            sel_glow.setColorAt(0.0, QColor(C.accent + "15"))
            sel_glow.setColorAt(0.6, QColor(C.accent + "08"))
            sel_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(sel_glow))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(4, 4, w - 8, h - 8, 12, 12)
        elif self._hovered:
            p.setBrush(QColor(C.bg_card))
            p.setPen(QPen(QColor(C.border_hover), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 14, 14)
        else:
            p.setBrush(QColor(C.bg_card))
            p.setPen(QPen(QColor(C.border), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 14, 14)

        img_margin = S.md
        img_w = w - img_margin * 2
        img_h = 100
        img_y = S.sm

        if self._loaded and self._thumb:
            scaled = self._thumb.scaled(img_w, img_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            px = (w - scaled.width()) / 2
            py = img_y + (img_h - scaled.height()) / 2
            p.drawPixmap(int(px), int(py), scaled)
        else:
            p.setBrush(QColor(C.bg_surface))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(img_margin, img_y, img_w, img_h), 8, 8)
            f = QFont(["Inter", "Segoe UI"], 10, QFont.Medium)
            p.setFont(f)
            p.setPen(QColor(C.text_muted))
            p.drawText(QRectF(img_margin, img_y, img_w, img_h), Qt.AlignCenter, "\u274C")

        name_y = img_y + img_h + 4
        name_rect = QRectF(4, name_y, w - 8, 20)
        f_name = QFont(["Inter", "Segoe UI"], 8, QFont.Medium)
        p.setFont(f_name)
        p.setPen(QColor(C.text_secondary))
        name = Path(self._path).name
        elided = p.fontMetrics().elidedText(name, Qt.ElideMiddle, int(w - 8))
        p.drawText(name_rect, Qt.AlignLeft | Qt.AlignTop, elided)

        if self._selected:
            idx_f = QFont(["Inter", "Segoe UI"], 7, QFont.Semibold)
            p.setFont(idx_f)
            p.setPen(QColor(C.accent))
            idx_rect = QRectF(4, name_y + 14, w - 8, 14)
            p.drawText(idx_rect, Qt.AlignLeft | Qt.AlignTop, f"#{self._index + 1}")

        p.end()
