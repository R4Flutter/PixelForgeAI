from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppearanceConfig:
    theme: str = "dark"
    accent_color: str = "#7C5CFF"
    font_family: str = "Segoe UI"
    font_size: int = 10
    sidebar_width: int = 72
    animation_enabled: bool = True
    animation_duration_ms: int = 260
