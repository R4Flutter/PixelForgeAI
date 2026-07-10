from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ImageResultData:
    source_path: Path
    output_path: Optional[Path] = None
    succeeded: bool = False
    error: Optional[str] = None
    duration: float = 0.0
    output_size: Optional[tuple[int, int]] = None
    output_format: Optional[str] = None


@dataclass
class PipelineResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    failed_files: List[str] = field(default_factory=list)
    cancelled: bool = False
    output_folder: Optional[str] = None
    image_results: List[ImageResultData] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return self.failed == 0 and self.total > 0
