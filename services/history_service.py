from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from events.base import EventBus
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class HistoryEntry:
    job_id: str
    total: int
    succeeded: int
    failed: int
    timestamp: float = 0.0
    output_folder: str = ""


class HistoryService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._entries: List[HistoryEntry] = []
        self._max = 50

    def add(self, entry: HistoryEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries.pop(0)
        log.info(f"History: {entry.job_id} ({entry.succeeded}/{entry.total})")

    def recent(self, count: int = 10) -> List[HistoryEntry]:
        return self._entries[-count:]

    def clear(self) -> None:
        self._entries.clear()
