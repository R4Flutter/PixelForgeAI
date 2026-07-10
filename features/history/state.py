from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class HistoryEntryData:
    job_id: str
    total: int
    succeeded: int
    failed: int
    timestamp: float = 0.0
    output_folder: str = ""


@dataclass
class HistoryState:
    entries: List[HistoryEntryData] = field(default_factory=list)
    has_entries: bool = False
