from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    accent: str = "#7C5CFF"
    accent_hover: str = "#6B4FE0"
    accent_active: str = "#5A3FC0"

    bg_primary: str = "#0B0C10"
    bg_secondary: str = "#0E0F14"
    bg_card: str = "#13151D"
    bg_surface: str = "#1A1D2B"
    bg_hover: str = "#232737"
    bg_active: str = "#2B3042"

    text_primary: str = "#E6E8F0"
    text_secondary: str = "#8A90A6"
    text_muted: str = "#5A6080"
    text_accent: str = "#7C5CFF"

    border: str = "#262A37"
    border_hover: str = "#2B3042"
    border_focus: str = "#7C5CFF"

    success: str = "#22C55E"
    warning: str = "#FBBF24"
    error: str = "#EF4444"
    info: str = "#3B82F6"

    gradient_start: str = "#7C5CFF"
    gradient_end: str = "#A78BFA"
