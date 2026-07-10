from __future__ import annotations

from dataclasses import dataclass
from typing import List

from events.base import Event


@dataclass
class HistoryEntryAddedEvent(Event):
    job_id: str
    total: int
    succeeded: int
    failed: int
    output_folder: str = ""


@dataclass
class HistoryClearedEvent(Event):
    pass


@dataclass
class HistoryLoadedEvent(Event):
    entries: List[dict]
