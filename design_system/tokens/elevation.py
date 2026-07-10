from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Elevation:
    level_0: str = "none"
    level_1: str = "0 1px 2px rgba(0,0,0,0.3)"
    level_2: str = "0 2px 8px rgba(0,0,0,0.4)"
    level_3: str = "0 4px 16px rgba(0,0,0,0.5)"
    level_4: str = "0 8px 32px rgba(0,0,0,0.6)"
    level_5: str = "0 16px 48px rgba(0,0,0,0.7)"

    glow_accent: str = "0 0 20px rgba(124,92,255,0.3)"
    glow_success: str = "0 0 20px rgba(34,197,94,0.3)"
    glow_error: str = "0 0 20px rgba(239,68,68,0.3)"
