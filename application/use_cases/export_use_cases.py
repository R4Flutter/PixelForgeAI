from __future__ import annotations

from dataclasses import dataclass
from typing import List

from application.use_cases.base import UseCase
from common.result import Result, Success
from events.base import EventBus
from events.export_events import ExportCompletedEvent, ExportFailedEvent, ExportStartedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class ExportRequest:
    source_paths: List[str]
    output_dir: str


class ExportImagesUseCase(UseCase[ExportRequest, int]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: ExportRequest) -> Result[int, str]:
        self._event_bus.emit(ExportStartedEvent(
            count=len(request.source_paths), output_dir=request.output_dir,
        ))

        exported = 0
        for src in request.source_paths:
            try:
                import shutil
                from pathlib import Path
                dest = Path(request.output_dir) / Path(src).name
                shutil.copy2(src, str(dest))
                exported += 1
            except Exception as e:
                log.error(f"Export failed: {src} â†’ {e}")
                self._event_bus.emit(ExportFailedEvent(error=str(e), path=src))

        self._event_bus.emit(ExportCompletedEvent(
            count=exported, output_dir=request.output_dir,
        ))
        return Success(exported)
