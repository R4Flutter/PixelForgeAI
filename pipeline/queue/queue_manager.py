from __future__ import annotations

import threading
from typing import Any, List, Optional

from plogging.logger import get_logger

log = get_logger(__name__)


class QueueManager:
    def __init__(self, max_size: int = 100) -> None:
        self._queue: List[Any] = []
        self._lock = threading.Lock()
        self._max_size = max_size

    def enqueue(self, item: Any) -> None:
        with self._lock:
            if len(self._queue) >= self._max_size:
                self._queue.pop(0)
            self._queue.append(item)

    def dequeue(self) -> Any:
        with self._lock:
            return self._queue.pop(0) if self._queue else None

    def peek(self) -> Any:
        with self._lock:
            return self._queue[0] if self._queue else None

    def remove(self, item_id: str) -> bool:
        with self._lock:
            before = len(self._queue)
            self._queue = [j for j in self._queue if getattr(j, "job_id", "") != item_id]
            return len(self._queue) < before

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return self.pending == 0
