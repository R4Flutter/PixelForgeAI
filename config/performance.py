from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    thumbnail_size: int = 160
    thumbnail_quality: int = 85
    max_thumbnails_cached: int = 1000
    max_log_blocks: int = 4000
    progress_history_size: int = 100
    batch_size: int = 1
    parallel_thumbnails: bool = True
    upscale_timeout_seconds: int = 180
    max_pixel_count: int = 60000000
