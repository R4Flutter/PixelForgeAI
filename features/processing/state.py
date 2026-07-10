from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ProcessingState:
    job_id: str = ""
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_file: str = ""
    current_stage: str = ""
    percentage: float = 0.0
    is_running: bool = False
    is_paused: bool = False
    log_lines: List[str] = field(default_factory=list)
    failed_files: List[str] = field(default_factory=list)
