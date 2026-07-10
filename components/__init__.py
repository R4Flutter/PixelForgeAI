"""
PixelForgeAI - Reusable UI widgets.

Framework-agnostic building blocks styled from ``themes/dark.qss``. None of
these widgets know anything about the backend.

buttons  - PrimaryButton / SecondaryButton / IconButton / DangerButton.
cards    - DropZone / PreviewGrid / SectionCard / StatCard / NavCard / ImageCard.
progress - ProgressBar (determinate), StepIndicator, LogConsole, Throbber.
icons    - programmatic SVG line-art icon factory (no asset files shipped).
"""

from __future__ import annotations

__all__ = ["buttons", "cards", "progress", "icons"]
