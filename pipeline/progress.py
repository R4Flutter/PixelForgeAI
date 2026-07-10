from __future__ import annotations

from typing import Callable, List, Optional

from core.enums import PipelineStage
from core.logger import get_logger

log = get_logger(__name__)

StageCallback = Callable[[PipelineStage], None]
ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str, str, str], None]


class ProgressTracker:
    def __init__(self) -> None:
        self._stage_cb: Optional[StageCallback] = None
        self._progress_cb: Optional[ProgressCallback] = None
        self._log_cb: Optional[LogCallback] = None
        self._current_stage: Optional[PipelineStage] = None

    def on_stage(self, callback: StageCallback) -> None:
        self._stage_cb = callback

    def on_progress(self, callback: ProgressCallback) -> None:
        self._progress_cb = callback

    def on_log(self, callback: LogCallback) -> None:
        self._log_cb = callback

    def set_stage(self, stage: PipelineStage) -> None:
        self._current_stage = stage
        if self._stage_cb:
            self._stage_cb(stage)

    def report_progress(self, done: int, total: int, file: str) -> None:
        if self._progress_cb:
            self._progress_cb(done, total, file)

    def log(self, level: str, logger_name: str, message: str) -> None:
        if self._log_cb:
            self._log_cb(level, logger_name, message)
