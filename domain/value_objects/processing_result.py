from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ProcessingResult:
    success: bool
    image_path: str
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0
    stages_completed: int = 0
    stages_total: int = 0
