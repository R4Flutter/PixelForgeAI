from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportProfile:
    output_format: str = "png"
    quality: int = 95
    png_compression: int = 6
    jpg_background: str = "#FFFFFF"
    overwrite: bool = True
    suffix: str = ""
    strip_metadata: bool = True


@dataclass(frozen=True)
class ExportOptions:
    output_dir: str = "output/final"
    profile: ExportProfile = ExportProfile()
