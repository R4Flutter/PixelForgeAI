from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ResultsState:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    output_folder: str = ""
    cancelled: bool = False
    failed_files: List[str] = field(default_factory=list)
    has_results: bool = False
