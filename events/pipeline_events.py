from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from domain.models import PipelineStatistics as JobStatistics, StageType
from events.base import Event


@dataclass
class PipelineStartedEvent(Event):
    job_id: str
    total_images: int
    image_paths: List[str]


@dataclass
class PipelineCompletedEvent(Event):
    job_id: str
    statistics: JobStatistics
    output_folder: str


@dataclass
class PipelineFailedEvent(Event):
    job_id: str
    error: str


@dataclass
class PipelineCancelledEvent(Event):
    job_id: str


@dataclass
class PipelinePausedEvent(Event):
    job_id: str


@dataclass
class PipelineResumedEvent(Event):
    job_id: str


@dataclass
class StageStartedEvent(Event):
    job_id: str
    stage: Any
    image_path: str


@dataclass
class StageCompletedEvent(Event):
    job_id: str
    stage: Any
    success: bool
    duration: float
    error: Optional[str] = None


@dataclass
class ProgressUpdatedEvent(Event):
    job_id: str
    completed: int
    total: int
    current_file: str
    percentage: float
