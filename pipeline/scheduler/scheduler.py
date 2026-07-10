from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from plogging.logger import get_logger

log = get_logger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callback: Optional[Callable] = None

    def on_tick(self, callback: Callable) -> None:
        self._callback = callback

    def start(self, interval_ms: int = 100) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(interval_ms / 1000.0,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self, interval: float) -> None:
        while not self._stop_event.is_set():
            if self._callback:
                try:
                    self._callback()
                except Exception as e:
                    log.error(f"Scheduler callback error: {e}")
            time.sleep(interval)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
