"""
icons.py
--------
Programmatic line-art icon factory.

Rather than ship dozens of PNG/SVG asset files (which break silently when a
path is wrong), icons are drawn from compact inline SVG strings rendered to
QPixmap via QtSvg. Every icon inherits the theme colour, so a single call site
can restyle the whole app. No backend dependency; pure Qt.

    icon("home", color="#E6E8F0")   -> QIcon
    pixmap("check", size=18)        -> QPixmap
"""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG_WRAP = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'width="{w}" height="{h}" fill="none" stroke="__C__" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)

# Each value is the inner SVG (paths only). The wrapper supplies stroke rules.
_BODIES: Dict[str, str] = {
    "home": (
        '<path d="M3 10.4 12 4l9 6.4"/><path d="M5 9.4V19h14V9.4"/>'
        '<path d="M9.5 19v-4.5h5V19"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3.2"/>'
        '<path d="M12 2.6v2.8M12 18.6v2.8M21.4 12h-2.8M5.4 12H2.6"/>'
        '<path d="M18.4 5.6 16.3 7.7M7.7 16.3 5.6 18.4M18.4 18.4l-2.1-2.1M7.7 7.7 5.6 5.6"/>'
    ),
    "info": (
        '<circle cx="12" cy="12" r="9.4"/>'
        '<path d="M12 11v5.6"/>'
        '<circle cx="12" cy="7.7" r="0.6" fill="__C__" stroke="none"/>'
    ),
    "logo": (
        '<path d="M12 3c.62 3.4 2.2 5 5.6 5.6C14.2 9.2 12.6 10.8 12 14c-.62-3.2-2.2-4.8-5.6-5.4C9.8 8 11.4 6.4 12 3Z" fill="__A__" stroke="none"/>'
        '<path d="M18.4 13c.3 1.6 1 2.3 2.6 2.6-1.6.3-2.3 1-2.6 2.6-.3-1.6-1-2.3-2.6-2.6 1.6-.3 2.3-1 2.6-2.6Z" fill="__A__" stroke="none"/>'
    ),
    "folder": '<path d="M3 6.4h6l2 2.5h10V18H3z"/>',
    "folder_open": (
        '<path d="M3 6.4h6l2 2.5h10V18H3z"/>'
        '<path d="M3.6 8.4 5 18h13.6"/>'
    ),
    "image": (
        '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/>'
        '<circle cx="9" cy="10" r="1.7"/>'
        '<path d="m4.5 17 4-4 3.8 2.9 3.2-2 4 4"/>'
    ),
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "pause": (
        '<rect x="7" y="5.2" width="3.3" height="13.6" rx="1.2" fill="__C__" stroke="none"/>'
        '<rect x="13.7" y="5.2" width="3.3" height="13.6" rx="1.2" fill="__C__" stroke="none"/>'
    ),
    "play": '<path d="M7 5l12 7-12 7z" fill="__C__" stroke="none"/>',
    "upload": (
        '<path d="M12 4v11"/><path d="M8 8l4-4 4 4"/><path d="M4.5 16v3.5h15V16"/>'
    ),
    "refresh": (
        '<path d="M4.5 12a7.5 7.5 0 0 1 12.8-5.3"/>'
        '<path d="M19.5 5.6v3.8h-3.8"/>'
        '<path d="M19.5 12a7.5 7.5 0 0 1-12.8 5.3"/>'
        '<path d="M4.5 18.4v-3.8h3.8"/>'
    ),
    "check": '<path d="M5 12.4l4.4 4.6L19 6.6"/>',
    "clock": (
        '<circle cx="12" cy="12" r="8.4"/>'
        '<path d="M12 7.6V12l3 2"/>'
    ),
    "link": (
        '<path d="M9 15l6-6"/>'
        '<path d="M11 6.5 13 4.5a3.2 3.2 0 0 1 4.5 4.5l-2 2"/>'
        '<path d="M13 17.5 11 19.5a3.2 3.2 0 0 1-4.5-4.5l2-2"/>'
    ),
    "mail": (
        '<rect x="3.5" y="5.5" width="17" height="13" rx="2.4"/>'
        '<path d="M4.6 7.2 12 12l7.4-4.8"/>'
    ),
    "trash": (
        '<path d="M5 6.4h14M9 6.4V5h6v1.4M7.2 6.4l1 12h7.6l1-12"/>'
        '<path d="M10 10v6M14 10v6"/>'
    ),
    "cpu": (
        '<rect x="7" y="7" width="10" height="10" rx="2.2"/>'
        '<rect x="10" y="10" width="4" height="4" rx="1" fill="__C__" stroke="none"/>'
        '<path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>'
    ),
    "gpu": (
        '<rect x="3" y="7" width="18" height="10" rx="2.2"/>'
        '<circle cx="9" cy="12" r="2"/>'
        '<circle cx="15.4" cy="12" r="2"/>'
        '<path d="M6.5 17v2"/>'
    ),
    "resize": (
        '<rect x="3.5" y="3.5" width="17" height="17" rx="2.5"/>'
        '<path d="M9 3.5v17M15 3.5v17M3.5 9h17M3.5 15h17"/>'
    ),
    "format": (
        '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/>'
        '<path d="M8 9h8M8 13h8M8 17h5"/>'
    ),
    "key": (
        '<circle cx="8" cy="14" r="4"/>'
        '<path d="M11 11l8-8M16 4l3 3M16.5 6.5l2-2"/>'
    ),
    "success": (
        '<circle cx="12" cy="12" r="9.4"/>'
        '<path d="M7.5 12.4l3 3 6-6.4"/>'
    ),
    "warn": (
        '<path d="M12 3.5 21 19H3z"/>'
        '<path d="M12 10v4.2"/>'
        '<circle cx="12" cy="17" r="0.7" fill="__C__" stroke="none"/>'
    ),
    "stop": (
        '<rect x="7" y="7" width="10" height="10" rx="2.5" fill="__C__" stroke="none"/>'
    ),
    "copy": (
        '<rect x="9" y="9" width="11" height="11" rx="2.5"/>'
        '<path d="M5 15V5a2 2 0 0 1 2-2h8"/>'
    ),
    "external": (
        '<path d="M14 4h6v6"/><path d="M20 4 10 14"/>'
        '<path d="M19 13v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5"/>'
    ),
    "chevron_down": '<path d="M6 9.5l6 6 6-6"/>',
    "chevron_right": '<path d="M9.5 6l6 6-6 6"/>',
}

DEFAULT_COLOR = "#C4C8D6"
DEFAULT_ACCENT = "#6366F1"


def _render(svg: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pm


def _build_svg(name: str, size: int, color: str, accent: str) -> str:
    body = _BODIES.get(name, _BODIES["image"])
    svg = _SVG_WRAP.format(w=size, h=size, body=body)
    return svg.replace("__C__", color).replace("__A__", accent)


def pixmap(name: str, size: int = 22, color: str = DEFAULT_COLOR,
           accent: str = DEFAULT_ACCENT) -> QPixmap:
    """Return a single-resolution QPixmap for ``name``."""
    return _render(_build_svg(name, size, color, accent), size)


def icon(name: str, size: int = 22, color: str = DEFAULT_COLOR,
         accent: str = DEFAULT_ACCENT) -> QIcon:
    """Return an QIcon. Adds a 2x icon for crisp rendering on HiDPI."""
    qi = QIcon()
    base = pixmap(name, size, color, accent)
    qi.addPixmap(base, QIcon.Normal, QIcon.Off)
    return qi


def names() -> list[str]:
    return list(_BODIES)
