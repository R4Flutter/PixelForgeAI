"""
PixelForgeAI - Presentation layer.

Pure UI. These modules NEVER import or call the AI backend directly. The only
contract they hold is with ``backend.job`` (the immutable JobRequest/Settings
dataclasses) and with Qt. All backend interaction is delegated to
``backend.worker`` by the main window.

Pages
-----
main_window - ``QMainWindow`` with a sidebar + ``QStackedWidget``.
home       - drag & drop, browse, preview grid, selected-image count.
processing - progress bar, current file, elapsed / ETA, pause / resume / cancel,
             live log console.
success    - completion summary, open output folder, process again.
settings   - output folder, format, output size, GPU/CPU, batch, theme,
             licence info.
about      - version, developer, website, support.
"""

from __future__ import annotations

__all__ = [
    "main_window",
    "home",
    "processing",
    "success",
    "settings_page",
    "about",
]
