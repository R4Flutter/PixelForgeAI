from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional


class PipelineHandler(logging.Handler):
    def __init__(self, callback: Optional[Callable[[str, str, str], None]] = None) -> None:
        super().__init__()
        self._callback = callback
        self._buffer: List[logging.LogRecord] = []
        self._max_buffer = 4000

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._buffer.append(record)
        if len(self._buffer) > self._max_buffer:
            self._buffer.pop(0)
        if self._callback:
            self._callback(record.levelname, record.name, msg)

    def get_recent(self, count: int = 100) -> List[str]:
        return [self.format(r) for r in self._buffer[-count:]]

    def clear(self) -> None:
        self._buffer.clear()
