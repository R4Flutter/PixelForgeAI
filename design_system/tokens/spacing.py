from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spacing:
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    xxl: int = 28
    xxxl: int = 40

    sidebar_width: int = 72
    card_radius: int = 10
    button_height: int = 42
    icon_size: int = 22
