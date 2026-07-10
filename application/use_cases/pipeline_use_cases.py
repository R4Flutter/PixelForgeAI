from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from application.use_cases.base import UseCase
from common.result import Result, Success
from events.base import EventBus
from events.pipeline_events import (
    PipelineCompletedEvent,
    PipelineStartedEvent,
    ProgressUpdatedEvent,
)
from plogging.logger import get_logger
from pipeline.core.orchestrator import PipelineOrchestrator

log = get_logger(__name__)


@dataclass
class StartPipelineRequest:
    paths: List[str]
    settings: Any
    output_folder: str = "output/final"


@dataclass
class StartPipelineResponse:
    job_id: str
    total: int


class StartPipelineUseCase(UseCase[StartPipelineRequest, StartPipelineResponse]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: StartPipelineRequest) -> Result[StartPipelineResponse, str]:
        import time as _time
        job_id = str(_time.time_ns())

        self._event_bus.emit(PipelineStartedEvent(
            job_id=job_id,
            total_images=len(request.paths),
            image_paths=list(request.paths),
        ))

        import threading
        thread = threading.Thread(
            target=self._run,
            args=(request, job_id),
            daemon=True,
        )
        thread.start()

        return Success(StartPipelineResponse(job_id=job_id, total=len(request.paths)))

    def _run(self, request: StartPipelineRequest, job_id: str) -> None:
        orchestrator = PipelineOrchestrator(request.settings)
        for i, path in enumerate(request.paths):
            try:
                orchestrator.execute(path, request.settings)
            except Exception as e:
                log.error(f"Pipeline error: {e}")

            self._event_bus.emit(ProgressUpdatedEvent(
                job_id=job_id,
                completed=i + 1,
                total=len(request.paths),
                current_file=path,
                percentage=(i + 1) / len(request.paths) * 100,
            ))

        from domain.value_objects.pipeline_statistics import PipelineStatistics
        stats = PipelineStatistics(
            total_images=len(request.paths),
            succeeded=len(request.paths),
        )
        self._event_bus.emit(PipelineCompletedEvent(
            job_id=job_id, statistics=stats, output_folder=request.output_folder,
        ))


@dataclass
class CancelPipelineRequest:
    job_id: str


class CancelPipelineUseCase(UseCase[CancelPipelineRequest, None]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: CancelPipelineRequest) -> Result[None, str]:
        from events.pipeline_events import PipelineCancelledEvent
        self._event_bus.emit(PipelineCancelledEvent(job_id=request.job_id))
        return Success(None)


class PausePipelineUseCase(UseCase):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request=None) -> Result[None, str]:
        from events.pipeline_events import PipelinePausedEvent
        job_id = getattr(request, "job_id", "") if request else ""
        self._event_bus.emit(PipelinePausedEvent(job_id=job_id))
        return Success(None)


class ResumePipelineUseCase(UseCase):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request=None) -> Result[None, str]:
        from events.pipeline_events import PipelineResumedEvent
        job_id = getattr(request, "job_id", "") if request else ""
        self._event_bus.emit(PipelineResumedEvent(job_id=job_id))
        return Success(None)
