"""
buttons.py
----------
Reusable QPushButton subclasses styled through themes/dark.qss by objectName.
No backend knowledge; pure presentation.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    """Main call-to-action (indigo fill)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("PrimaryButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)


class SecondaryButton(QPushButton):
    """Secondary action (subtle surface)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("SecondaryButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)


class DangerButton(QPushButton):
    """Destructive action (cancel / remove)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("DangerButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)


class GhostButton(QPushButton):
    """Text-only link/button (footers, tertiary actions)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("GhostButton")
        self.setCursor(Qt.PointingHandCursor)


class IconButton(QPushButton):
    """Square icon button (browse, settings cogs, etc.)."""

    def __init__(self, icon: Optional[QIcon] = None, tooltip: str = "",
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 44)
        self.setIconSize(QSize(20, 20)) if icon is not None else None
        if icon is not None:
            self.setIcon(icon)
        if tooltip:
            self.setToolTip(tooltip)


class NavButton(QPushButton):
    """Sidebar entry; uses the checkable state to show the active page."""

    def __init__(self, icon: Optional[QIcon] = None, text: str = "",
                 parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setContentsMargins(14, 0, 14, 0)
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(18, 18))
