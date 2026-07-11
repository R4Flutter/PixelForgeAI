from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, Property,
    QPointF, QRectF,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QWidget,
)


class _NeumorphicSwitch(QWidget):
    def __init__(self, checked: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._thumb = 1.0 if checked else 0.0
        self._anim: QPropertyAnimation | None = None
        self.setFixedSize(39, 19)
        self.setCursor(Qt.PointingHandCursor)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool, animated: bool = True) -> None:
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animated:
            self._anim = QPropertyAnimation(self, b"thumb", self)
            self._anim.setDuration(350)
            self._anim.setStartValue(self._thumb)
            self._anim.setEndValue(target)
            self._anim.setEasingCurve(QEasingCurve.OutBack)
            self._anim.start()
        else:
            self._thumb = target
            self.update()

    def _get_thumb(self) -> float:
        return self._thumb

    def _set_thumb(self, v: float) -> None:
        self._thumb = v
        self.update()

    thumb = Property(float, _get_thumb, _set_thumb)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            target = 1.0 if self._checked else 0.0
            self._anim = QPropertyAnimation(self, b"thumb", self)
            self._anim.setDuration(350)
            self._anim.setStartValue(self._thumb)
            self._anim.setEndValue(target)
            self._anim.setEasingCurve(QEasingCurve.OutBack)
            self._anim.start()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        bg = QColor("#262A37") if not self._checked else QColor("#6366F1")
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        thumb_size = h - 8
        track_w = w - thumb_size - 8
        thumb_x = 4 + track_w * self._thumb
        thumb_y = 4

        thumb_bg = QColor("#FFFFFF")
        p.setBrush(thumb_bg)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(thumb_x + thumb_size / 2, thumb_y + thumb_size / 2),
                      thumb_size / 2, thumb_size / 2)

        if self._checked:
            glow = QColor("#6366F1")
            glow.setAlpha(35)
            p.setBrush(glow)
            p.drawEllipse(QPointF(thumb_x + thumb_size / 2, thumb_y + thumb_size / 2),
                          thumb_size / 2 + 5, thumb_size / 2 + 5)

        p.end()


class NeumorphicToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, text: str = "", checked: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._switch = _NeumorphicSwitch(checked)

        self._label = QLabel(text)
        self._label.setStyleSheet(
            "color: #C4C8D6; font-size: 12px; background: transparent; border: none;"
        )
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._switch)
        layout.addWidget(self._label, 1)

        self._switch.mousePressEvent = self._on_switch_click

    def _on_switch_click(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._switch.set_checked(not self._switch.is_checked())
            self.toggled.emit(self._switch.is_checked())

    def is_checked(self) -> bool:
        return self._switch.is_checked()

    def set_checked(self, checked: bool, animated: bool = True) -> None:
        self._switch.set_checked(checked, animated)

    def setChecked(self, checked: bool) -> None:
        self._switch.set_checked(checked, True)

    def isChecked(self) -> bool:
        return self._switch.is_checked()

    def setToolTip(self, tip: str) -> None:
        super().setToolTip(tip)
        self._switch.setToolTip(tip)
        self._label.setToolTip(tip)

    def setText(self, text: str) -> None:
        self._label.setText(text)
