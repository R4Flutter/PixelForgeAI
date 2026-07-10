from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportConfig:
    default_quality: int = 95
    png_compression_range: tuple = (0, 9)
    jpg_quality_range: tuple = (1, 100)
    webp_quality_range: tuple = (1, 100)
    max_filename_length: int = 255
    atomic_writes: bool = True
