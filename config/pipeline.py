from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class PipelineConfig:
    remove_bg_enabled: bool = True
    upscale_enabled: bool = True
    resize_enabled: bool = True
    upscale_timeout: int = 180
    default_upscale_factor: int = 4
    min_output_dim: int = 64
    max_output_dim: int = 12000
    stages: Tuple[str, ...] = ("remove_bg", "upscale", "resize", "save")
    overwrite_by_default: bool = True
    cleanup_work_dir: bool = True
