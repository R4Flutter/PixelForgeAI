"""
PixelForgeAI - Presentation layer.

Pure UI. Uses EventBus for communication with services layer. Never
imports or calls AI backend directly. Only contract with backend is
via ``models`` dataclasses and the ``event_bus``.

Pages
-----
main_window  - ``QMainWindow`` with sidebar + ``QStackedWidget``.
sidebar      - Navigation sidebar.
home         - drag & drop, browse, image carousel, pipeline builder.
processing   - progress bar, stage indicators, live log console.
results      - completion summary, open folder, process again.
settings     - output folder, format, pipeline config, licence.
about        - version, developer, support.
"""

from __future__ import annotations

__all__ = [
    "main_window",
    "sidebar",
    "home",
    "processing",
    "results",
    "settings_page",
    "about",
]
