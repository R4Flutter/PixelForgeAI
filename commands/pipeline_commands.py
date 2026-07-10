from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from commands.base import Command, CommandResult
from domain.models import PipelineJob
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

log = get_logger(__name__)


@dataclass
class StartPipelineCommand(Command[PipelineJob]):
    paths: List[str]
    settings: any
    job_id: str = ""
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[PipelineJob]:
        import time
        from domain.models import Image, JobStatus, PipelineJob

        images = []
        for p in self.paths:
            import os
            img = Image(path=p, file_name=os.path.basename(p), file_size=os.path.getsize(p))
            images.append(img)

        job = PipelineJob(
            job_id=self.job_id or str(time.time_ns()),
            images=images,
            status=JobStatus.QUEUED,
        )

        if self.event_bus:
            self.event_bus.emit(PipelineStartedEvent(
                job_id=job.job_id,
                total_images=job.total,
                image_paths=list(self.paths),
            ))

        log.info(f"Pipeline started: {job.job_id} ({job.total} images)")
        return CommandResult(success=True, value=job)


@dataclass
class CancelPipelineCommand(Command[None]):
    job_id: str
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(PipelineCancelledEvent(job_id=self.job_id))
        log.info(f"Pipeline cancelled: {self.job_id}")
        return CommandResult(success=True)


@dataclass
class PausePipelineCommand(Command[None]):
    job_id: str
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(PipelinePausedEvent(job_id=self.job_id))
        log.info(f"Pipeline paused: {self.job_id}")
        return CommandResult(success=True)


@dataclass
class ResumePipelineCommand(Command[None]):
    job_id: str
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(PipelineResumedEvent(job_id=self.job_id))
        log.info(f"Pipeline resumed: {self.job_id}")
        return CommandResult(success=True)
