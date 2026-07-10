"""
cards.py
--------
Composite widgets styled through themes/dark.qss by objectName.

  SectionCard  - titled grouping container (QFrame#Card).
  StatCard     - a single metric tile (QFrame#StatCard).
  NavCard      - clickable title + subtitle card (QFrame#CardRaised).
  ImageCard    - one thumbnail + filename + remove button (QFrame#ImageCard).
  DropZone     - drag & drop surface; emits urls_dropped(paths).
  PreviewGrid  - icon-mode thumbnail grid that wraps/reflows on resize and
                 lets the user remove items (Del / context menu).

No backend dependency. ``DropZone`` accepts any suffixes the caller passes in.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDragMoveEvent, QDropEvent, QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from components.icons import pixmap

# Suffixes DropZone accepts when none are supplied by the caller.
_DEFAULT_IMAGE_SUFFIXES: tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
)


class SectionCard(QFrame):
    """Titled content container."""

    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 20)
        outer.setSpacing(14)

        if title:
            header = QLabel(title.upper())
            header.setObjectName("SectionLabel")
            outer.addWidget(header)

        self._body = QWidget(self)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        outer.addWidget(self._body)

    def addWidget(self, widget: QWidget) -> None:  # noqa: D401
        self._body.layout().addWidget(widget)

    def addLayout(self, layout) -> None:
        self._body.layout().addLayout(layout)


class StatCard(QFrame):
    """A single metric tile."""

    def __init__(self, value: str = "0", label: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)

        self._value = QLabel(str(value))
        self._value.setObjectName("StatValue")
        layout.addWidget(self._value)

        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        layout.addWidget(self._label)

    def set_value(self, value) -> None:
        self._value.setText(str(value))

    def set_label(self, text: str) -> None:
        self._label.setText(text)


class NavCard(QFrame):
    """Clickable title + subtitle + (optional) icon card."""

    clicked = Signal()

    def __init__(self, title: str, subtitle: str = "", icon: Optional[QIcon] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardRaised")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        if icon is not None:
            ic = QLabel()
            ic.setPixmap(pixmap("image", 26))
            if not icon.isNull():
                ic.setPixmap(icon.pixmap(QSize(26, 26)))
            lay.addWidget(ic)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setStyleSheet("color:#F4F5FB; font-size:14px; font-weight:600;")
        s = QLabel(subtitle)
        s.setObjectName("Hint")
        text_box.addWidget(t)
        text_box.addWidget(s)
        lay.addLayout(text_box, 1)

        hint = QLabel("›")
        hint.setStyleSheet("color:#6B7186; font-size:18px;")
        lay.addWidget(hint)

        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageCard(QFrame):
    """A single thumbnail + name + remove button."""

    removed = Signal(str)  # file path

    def __init__(self, path: str, label: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self.setObjectName("ImageCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self._thumb = QLabel()
        self._thumb.setFixedSize(150, 150)
        self._thumb.setAlignment(Qt.AlignCenter)
        self._thumb.setStyleSheet("background:transparent; border:none;")
        pm = QPixmap(path)
        if pm.isNull():
            pm = pixmap("image", 90)
        else:
            pm = pm.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._thumb.setPixmap(pm)
        lay.addWidget(self._thumb, alignment=Qt.AlignCenter)

        name = label or path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        name_lbl = QLabel(name)
        name_lbl.setObjectName("Hint")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumWidth(150)
        lay.addWidget(name_lbl)

    def path(self) -> str:
        return self._path


class DropZone(QFrame):
    """Drag & drop surface. Emits ``urls_dropped`` with accepted local paths."""

    urls_dropped = Signal(list)
    clicked = Signal()

    def __init__(self, accepted_suffixes: Optional[Sequence[str]] = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self._suffixes = tuple(s.lower() for s in (accepted_suffixes or _DEFAULT_IMAGE_SUFFIXES))
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)
        lay.setContentsMargins(30, 30, 30, 30)

        ic = QLabel()
        ic.setPixmap(pixmap("upload", 44, color="#8A90A6", accent="#6366F1"))
        ic.setAlignment(Qt.AlignCenter)
        ic.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(ic)

        title = QLabel("Drag & drop images here")
        title.setStyleSheet("color:#F4F5FB; font-size:16px; font-weight:600;")
        title.setAlignment(Qt.AlignCenter)
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(title)

        sub = QLabel("PNG / JPG / WEBP / BMP")
        sub.setObjectName("Hint")
        sub.setAlignment(Qt.AlignCenter)
        sub.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(sub)

    # ------------------------------------------------------------------ #
    # DnD
    # ------------------------------------------------------------------ #
    def _is_acceptable(self, event: QDragEnterEvent) -> bool:
        urls = event.mimeData().urls()
        if not urls:
            return False
        for url in urls:
            if not url.isLocalFile():
                continue
            local = url.toLocalFile()
            if self._matches(local):
                return True
        return bool(urls)

    def _matches(self, local_path: str) -> bool:
        path = local_path.lower()
        if path.endswith(self._suffixes):
            return True
        return False

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: D401
        if self._is_acceptable(event):
            event.acceptProposedAction()
            self.setObjectName("DropZoneHover")
            self._polish()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: D401
        if self._is_acceptable(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: D401
        self.setObjectName("DropZone")
        self._polish()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: D401
        paths: List[str] = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            local = url.toLocalFile()
            if self._matches(local):
                paths.append(local)
        self.setObjectName("DropZone")
        self._polish()
        if paths:
            event.acceptProposedAction()
            self.urls_dropped.emit(paths)
        else:
            event.ignore()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _polish(self) -> None:
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)


class PreviewGrid(QListView):
    """Icon-mode thumbnail grid with reflow + item removal."""

    removed = Signal(str)  # removed path

    THUMB = 150
    CELL_W = 174
    CELL_H = 196

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ImageCard")
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.ExtendedSelection)
        self.setEditTriggers(QListView.NoEditTriggers)
        self.setWordWrap(True)
        self.setIconSize(QSize(self.THUMB, self.THUMB))
        self.setGridSize(QSize(self.CELL_W, self.CELL_H))
        self.setSpacing(10)
        self.setFrameShape(QListView.NoFrame)
        self.setUniformItemSizes(True)

        self._model = QStandardItemModel(self)
        self.setModel(self._model)

        act = QAction("Remove", self)
        act.setShortcut("Delete")
        act.triggered.connect(self.remove_selected)
        self.addAction(act)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def set_paths(self, paths: Sequence[str]) -> None:
        self._model.clear()
        for p in paths:
            self._add_item(p)

    def add_paths(self, paths: Sequence[str]) -> None:
        existing = {self._model.item(i).data(Qt.UserRole)
                    for i in range(self._model.rowCount())}
        for p in paths:
            if p in existing:
                continue
            self._add_item(p)

    def get_paths(self) -> List[str]:
        return [self._model.item(i).data(Qt.UserRole)
                for i in range(self._model.rowCount())]

    def clear(self) -> None:  # type: ignore[override]
        self._model.clear()

    def remove_selected(self) -> None:
        indexes = self.selectedIndexes()
        if not indexes:
            return
        removed: List[str] = []
        for idx in sorted(indexes, key=lambda i: i.row(), reverse=True):
            path = self._model.itemFromIndex(idx).data(Qt.UserRole)
            self._model.removeRow(idx.row())
            removed.append(path)
        for p in removed:
            self.removed.emit(p)

    def _add_item(self, path: str) -> None:
        item = QStandardItem()
        name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        item.setText(name)
        item.setToolTip(path)
        item.setData(path, Qt.UserRole)
        item.setEditable(False)
        pm = QPixmap(path)
        if pm.isNull():
            pm = pixmap("image", 120, color="#3A4054")
        else:
            pm = pm.scaled(self.THUMB, self.THUMB, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
        item.setIcon(QIcon(pm))
        self._model.appendRow(item)

    def _show_menu(self, pos) -> None:
        index = self.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self)
        menu.addAction("Remove", lambda: self._remove_index(index))
        menu.exec(self.viewport().mapToGlobal(pos))

    def _remove_index(self, index) -> None:
        path = self._model.itemFromIndex(index).data(Qt.UserRole)
        self._model.removeRow(index.row())
        self.removed.emit(path)
