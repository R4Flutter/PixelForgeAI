from __future__ import annotations

import threading
import time
from typing import List, Optional

from domain.models import PipelineStatistics, PipelineJob
from events.base import EventBus
from events.pipeline_events import (
    PipelineCancelledEvent,
    PipelineCompletedEvent,
    PipelineFailedEvent,
    PipelinePausedEvent,
    PipelineResumedEvent,
    PipelineStartedEvent,
    ProgressUpdatedEvent,
    StageStartedEvent,
)
from plogging.logger import get_logger
from pipeline.core.orchestrator import PipelineOrchestrator
from pipeline.models.stage_result import StageResult

log = get_logger(__name__)


class PipelineService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        self._current_job_id: str = ""
        self._total = 0
        self._completed = 0
        self._failed = 0
        self._failed_files: List[str] = []

    @property
    def is_running(self) -> bool:
        return hasattr(self, "_thread") and self._thread is not None and self._thread.is_alive()

    def start(self, paths: List[str], settings, output_folder: str = "") -> None:
        with self._lock:
            if self.is_running:
                log.warning("Pipeline already running")
                return
            self._cancel_event.clear()
            self._pause_event.clear()
            self._total = len(paths)
            self._completed = 0
            self._failed = 0
            self._failed_files.clear()

        import time as _time
        job_id = str(_time.time_ns())
        self._current_job_id = job_id

        self._event_bus.emit(PipelineStartedEvent(
            job_id=job_id,
            total_images=self._total,
            image_paths=list(paths),
        ))

        self._thread = threading.Thread(
            target=self._process_job,
            args=(paths, settings, output_folder, job_id),
            daemon=True,
        )
        self._thread.start()

    def _process_job(self, paths: List[str], settings, output_folder: str, job_id: str) -> None:
        orchestrator = PipelineOrchestrator(settings)
        errors = []

        for i, path in enumerate(paths):
            if self._cancel_event.is_set():
                self._event_bus.emit(PipelineCancelledEvent(job_id=job_id))
                return

            while self._pause_event.is_set():
                if self._cancel_event.is_set():
                    self._event_bus.emit(PipelineCancelledEvent(job_id=job_id))
                    return
                time.sleep(0.1)

            stage_name = getattr(settings, "current_stage", "remove_bg")
            self._event_bus.emit(StageStartedEvent(
                job_id=job_id,
                stage=stage_name,
                image_path=path,
            ))

            try:
                result = orchestrator.execute(
                    path, settings,
                    cancel_event=self._cancel_event,
                    pause_event=self._pause_event,
                )
                if result.success:
                    self._completed += 1
                else:
                    self._failed += 1
                    errors.append((path, result.error or "Unknown error"))
            except Exception as e:
                self._failed += 1
                errors.append((path, str(e)))

            self._event_bus.emit(ProgressUpdatedEvent(
                job_id=job_id,
                completed=self._completed + self._failed,
                total=self._total,
                current_file=path,
                percentage=(self._completed + self._failed) / max(self._total, 1) * 100,
            ))

        import time as _time
        stats = JobStatistics(
            total_images=self._total,
            succeeded=self._completed,
            failed=self._failed,
            elapsed_seconds=0.0,
        )

        self._event_bus.emit(PipelineCompletedEvent(
            job_id=job_id,
            statistics=stats,
            output_folder=output_folder,
        ))

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._current_job_id:
            self._event_bus.emit(PipelineCancelledEvent(job_id=self._current_job_id))

    def pause(self) -> None:
        self._pause_event.set()
        if self._current_job_id:
            self._event_bus.emit(PipelinePausedEvent(job_id=self._current_job_id))

    def resume(self) -> None:
        self._pause_event.clear()
        if self._current_job_id:
            self._event_bus.emit(PipelineResumedEvent(job_id=self._current_job_id))
