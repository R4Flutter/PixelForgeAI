from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineStatistics:
    total_images: int = 0
    succeeded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    total_file_size: int = 0
    output_file_size: int = 0

    @property
    def all_succeeded(self) -> bool:
        return self.failed == 0 and self.total_images > 0

    @property
    def success_rate(self) -> float:
        if self.total_images == 0:
            return 1.0
        return self.succeeded / self.total_images
