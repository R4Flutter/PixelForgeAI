from __future__ import annotations

import threading
from typing import Any, Optional

from plogging.logger import get_logger
from pipeline.core.orchestrator import PipelineOrchestrator
from pipeline.models.stage_result import StageResult

log = get_logger(__name__)


class PipelineWorker:
    def __init__(self, orchestrator: PipelineOrchestrator) -> None:
        self._orchestrator = orchestrator
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._current_paths: list = []

    def start(self, paths: list, settings: Any) -> None:
        self._current_paths = list(paths)
        self._cancel_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(paths, settings), daemon=True
        )
        self._thread.start()

    def _run(self, paths: list, settings: Any) -> None:
        for path in paths:
            if self._cancel_event.is_set():
                break
            try:
                self._orchestrator.execute(
                    path, settings,
                    cancel_event=self._cancel_event,
                    pause_event=self._pause_event,
                )
            except Exception as e:
                log.error(f"Error processing {path}: {e}")

    def cancel(self) -> None:
        self._cancel_event.set()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
