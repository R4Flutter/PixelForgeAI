from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from application.use_cases.base import UseCase
from common.result import Result, Success
from events.base import EventBus
from events.pipeline_events import PipelineStartedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class RetryPipelineRequest:
    paths: List[str]
    settings: Any
    failed_files: List[str]
    output_folder: str = "output/final"


class RetryPipelineUseCase(UseCase[RetryPipelineRequest, None]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: RetryPipelineRequest) -> Result[None, str]:
        import time
        import threading
        from pipeline.core.orchestrator import PipelineOrchestrator

        paths = request.failed_files if request.failed_files else request.paths
        job_id = str(time.time_ns())

        self._event_bus.emit(PipelineStartedEvent(
            job_id=job_id,
            total_images=len(paths),
            image_paths=list(paths),
        ))

        thread = threading.Thread(
            target=self._run,
            args=(paths, request.settings, job_id, request.output_folder),
            daemon=True,
        )
        thread.start()
        return Success(None)

    def _run(self, paths: List[str], settings: Any, job_id: str, output_folder: str) -> None:
        from events.pipeline_events import PipelineCompletedEvent, ProgressUpdatedEvent

        orchestrator = PipelineOrchestrator(settings)
        for i, path in enumerate(paths):
            try:
                orchestrator.execute(path, settings)
            except Exception as e:
                log.error(f"Retry failed for {path}: {e}")

            self._event_bus.emit(ProgressUpdatedEvent(
                job_id=job_id,
                completed=i + 1,
                total=len(paths),
                current_file=path,
                percentage=(i + 1) / len(paths) * 100,
            ))

        from domain.value_objects.pipeline_statistics import PipelineStatistics
        stats = PipelineStatistics(total_images=len(paths), succeeded=len(paths))
        self._event_bus.emit(PipelineCompletedEvent(
            job_id=job_id, statistics=stats, output_folder=output_folder,
        ))
