from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DefaultConfig:
    output_folder: str = "output/final"
    output_format: str = "png"
    output_width: int = 4000
    output_height: int = 4000
    png_compression: int = 6
    jpg_quality: int = 95
    webp_quality: int = 90
    jpg_background: str = "#FFFFFF"
    upscale_mode: str = "auto"
    background_mode: str = "transparent"
    conflict_policy: str = "overwrite"
    device: str = "gpu"
    max_image_size_mb: int = 50
