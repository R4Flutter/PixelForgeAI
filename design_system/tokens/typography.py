from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Typography:
    font_family: str = "Segoe UI"
    font_size_base: int = 10

    size_xs: int = 9
    size_sm: int = 10
    size_md: int = 12
    size_lg: int = 14
    size_xl: int = 18
    size_xxl: int = 24
    size_xxxl: int = 32

    weight_normal: str = "400"
    weight_medium: str = "500"
    weight_semibold: str = "600"
    weight_bold: str = "700"
