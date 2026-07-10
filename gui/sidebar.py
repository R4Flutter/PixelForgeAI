from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget, QLabel

from components.buttons import NavButton
from components.icons import icon


_NAV_ITEMS = (
    ("Home", "home", 0),
    ("Processing", "image", 1),
    ("Results", "success", 2),
    ("Settings", "settings", 3),
    ("About", "info", 4),
)


class Sidebar(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(72)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        logo_lbl = QLabel()
        logo_lbl.setPixmap(icon("logo", 32, "#C4C8D6").pixmap(QSize(32, 32)))
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedHeight(64)
        lay.addWidget(logo_lbl)

        self._buttons: List[NavButton] = []
        for label, ico, idx in _NAV_ITEMS:
            btn = NavButton()
            btn.setIcon(icon(ico, 22, "#C4C8D6"))
            btn.setToolTip(label)
            btn.clicked.connect(lambda _, i=idx: self._on_clicked(i))
            self._buttons.append(btn)
            lay.addWidget(btn)

        lay.addStretch(1)

        self._callback: Optional[Callable[[int], None]] = None
        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_clicked(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
        if self._callback:
            self._callback(idx)

    def on_navigate(self, callback: Callable[[int], None]) -> None:
        self._callback = callback

    def set_active(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
