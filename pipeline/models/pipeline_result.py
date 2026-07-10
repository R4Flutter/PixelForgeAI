from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PipelineResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    failed_files: List[str] = field(default_factory=list)
    cancelled: bool = False
    output_folder: Optional[str] = None

    @property
    def all_succeeded(self) -> bool:
        return self.failed == 0 and self.total > 0
