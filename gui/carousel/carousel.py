from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import (
    Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup, QRectF, QPoint, QPointF, QEvent,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QKeyEvent, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QEnterEvent, QWheelEvent,
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QScrollArea,
    QSizePolicy, QApplication,
)

from models.pipeline_result import ImageResultData
from gui.carousel.thumbnail import ThumbnailWidget
from gui.carousel.preview import PreviewViewer

from design_system.tokens.colors import Colors as C
from design_system.tokens.spacing import Spacing as S
from design_system.tokens.typography import Typography as T


def _reduced() -> bool:
    return os.environ.get("PIXELFORGEAI_REDUCED_MOTION", "").strip() not in ("", "0", "false")


def _fmt_size(path: str) -> str:
    try:
        sz = os.path.getsize(path)
        if sz > 1048576:
            return f"{sz / 1048576:.1f} MB"
        return f"{sz / 1024:.1f} KB"
    except Exception:
        return "\u2014"


def _fmt_time(seconds: float) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m:02d}:{s:02d}"


class _BottomBar(QWidget):
    """Bottom bar with metadata on the left, prev/next counter on the right."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._index = 0
        self._total = 0
        self._filename = ""
        self._dimensions = ""
        self._file_size = ""
        self._duration = ""
        self.setFixedHeight(36)

    def set_metadata(self, index: int, total: int, filename: str,
                     dimensions: str, file_size: str, duration: str) -> None:
        self._index = index
        self._total = total
        self._filename = filename
        self._dimensions = dimensions
        self._file_size = file_size
        self._duration = duration
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.setBrush(QColor(C.bg_card))
        p.setPen(QPen(QColor(C.border), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        f_name = QFont(["Inter", "Segoe UI"], 11, QFont.Semibold)
        p.setFont(f_name)
        p.setPen(QColor(C.text_primary))
        elided = p.fontMetrics().elidedText(self._filename, Qt.ElideMiddle, 200)
        p.drawText(QRectF(S.xl, 0, 200, h), Qt.AlignLeft | Qt.AlignVCenter, elided)

        x = S.xl + 210
        p.setPen(QPen(QColor(C.border), 1))
        p.drawLine(QPointF(x, 12), QPointF(x, h - 12))

        f_meta = QFont(["Inter", "Segoe UI"], 9, QFont.Medium)
        p.setFont(f_meta)

        items = []
        if self._dimensions:
            items.append(self._dimensions)
        if self._file_size:
            items.append(self._file_size)
        if self._duration:
            items.append(f"{self._duration} s")

        ix = x + S.lg
        for item in items:
            p.setPen(QColor(C.text_secondary))
            p.drawText(QRectF(ix, 0, 140, h), Qt.AlignLeft | Qt.AlignVCenter, item)
            ix += 150

        f_count = QFont(["Cascadia Mono", "Consolas", "monospace"], 12, QFont.Bold)
        p.setFont(f_count)
        p.setPen(QColor(C.text_primary))
        count_str = f"{self._index + 1} / {self._total}"
        cw = p.fontMetrics().horizontalAdvance(count_str)
        cx = w - S.xxl - cw
        p.drawText(QRectF(cx, 0, cw, h), Qt.AlignLeft | Qt.AlignVCenter, count_str)

        p.end()


class ImageCarousel(QWidget):
    current_image_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._results: List[ImageResultData] = []
        self._cards: List[ThumbnailWidget] = []
        self._current_index = 0
        self._image_data: Dict[str, ImageResultData] = {}
        self._entered = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(S.md)

        self._preview = PreviewViewer()
        self._preview.prev_requested.connect(self._prev)
        self._preview.next_requested.connect(self._next)
        root.addWidget(self._preview, 1)

        carousel_bg = QWidget()
        carousel_bg.setStyleSheet("background: transparent;")
        carousel_lay = QVBoxLayout(carousel_bg)
        carousel_lay.setContentsMargins(0, 0, 0, 0)
        carousel_lay.setSpacing(S.xs)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setFrameShape(QScrollArea.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_area.installEventFilter(self)
        self._scroll_area.setFixedHeight(170)

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._card_layout = QHBoxLayout(self._scroll_content)
        self._card_layout.setContentsMargins(S.xl, S.sm, S.xl, S.sm)
        self._card_layout.setSpacing(S.md)
        self._card_layout.addStretch(1)

        self._scroll_area.setWidget(self._scroll_content)
        carousel_lay.addWidget(self._scroll_area)

        root.addWidget(carousel_bg)

        self._bottom_bar = _BottomBar()
        root.addWidget(self._bottom_bar)

        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._scroll_area and event.type() == QEvent.Wheel:
            delta = event.angleDelta().y()
            sb = self._scroll_area.horizontalScrollBar()
            sb.setValue(int(sb.value() - delta * 0.5))
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        k = event.key()
        if k == Qt.Key_Left:
            self._prev()
        elif k == Qt.Key_Right:
            self._next()
        elif k == Qt.Key_Home:
            self._go_to(0)
        elif k == Qt.Key_End:
            self._go_to(len(self._cards) - 1)
        elif k == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
            if event.modifiers() & Qt.ShiftModifier:
                self._export_all()
            else:
                self._save_current()
        else:
            super().keyPressEvent(event)

    def set_images(self, results: List[ImageResultData]) -> None:
        for c in self._cards:
            c.deleteLater()
        self._cards.clear()
        self._results = list(results)
        self._image_data.clear()
        self._current_index = 0

        for i, r in enumerate(results):
            path = str(r.output_path or r.source_path)
            self._image_data[path] = r
            card = ThumbnailWidget(path, i, self)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            self._cards.append(card)

        for i, card in enumerate(self._cards):
            self._card_layout.insertWidget(i, card, 0, Qt.AlignLeft)

        if self._cards:
            self._select(0)
            if not _reduced():
                self._play_entrance()

    def _play_entrance(self) -> None:
        for i, card in enumerate(self._cards):
            a = QPropertyAnimation(card, b"pos", self)
            a.setDuration(400)
            a.setStartValue(card.pos() + QPoint(0, 30))
            a.setEndValue(card.pos())
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.setStartTime(i * 40)
            a.start()

    def _instant_show(self) -> None:
        for card in self._cards:
            card.move(card.pos().x(), card.pos().y())

    def _select(self, index: int) -> None:
        if not self._cards or index < 0 or index >= len(self._cards):
            return
        for c in self._cards:
            c.set_selected(False)

        self._current_index = index
        card = self._cards[index]
        card.set_selected(True)

        path = card._path
        self._preview.set_pixmap(path, fade=True)
        self.current_image_changed.emit(path)

        self._ensure_visible(index)
        self._update_bottom_bar(path)

        card.update()

    def _update_bottom_bar(self, path: str) -> None:
        data = self._image_data.get(path)
        filename = Path(path).name
        dims = ""
        if data and data.output_size:
            dims = f"{data.output_size[0]}\u00D7{data.output_size[1]}"
        fsize = _fmt_size(path)
        dur = ""
        if data and data.duration:
            dur = f"{data.duration:.2f}"

        self._bottom_bar.set_metadata(
            self._current_index, len(self._cards),
            filename, dims, fsize, dur
        )

    def _ensure_visible(self, index: int) -> None:
        if index < 0 or index >= len(self._cards):
            return
        card = self._cards[index]
        sb = self._scroll_area.horizontalScrollBar()
        card_x = card.pos().x()
        card_w = card.width()
        view_w = self._scroll_area.viewport().width()
        scroll = sb.value()

        if card_x < scroll:
            sb.setValue(int(card_x - S.xl))
        elif card_x + card_w > scroll + view_w:
            sb.setValue(int(card_x + card_w - view_w + S.xl))

    def _on_card_clicked(self, path: str) -> None:
        for i, c in enumerate(self._cards):
            if c._path == path:
                self._select(i)
                break

    def _on_card_double_clicked(self, path: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _prev(self) -> None:
        if self._current_index > 0:
            self._select(self._current_index - 1)

    def _next(self) -> None:
        if self._current_index < len(self._cards) - 1:
            self._select(self._current_index + 1)

    def _go_to(self, index: int) -> None:
        self._select(index)

    def _save_current(self) -> None:
        if not self._cards or self._current_index < 0:
            return
        path = self._cards[self._current_index]._path
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
            except Exception:
                pass

    def _export_all(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Export All Images")
        if not folder:
            return
        import shutil
        for card in self._cards:
            src = card._path
            dst = os.path.join(folder, Path(src).name)
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    def get_data_for(self, path: str) -> Optional[ImageResultData]:
        return self._image_data.get(path)

    def count(self) -> int:
        return len(self._cards)

    def current_index(self) -> int:
        return self._current_index
