from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto
from typing import List, Optional

from common.enums import StringEnum
from domain.entities.image import Image


class JobStatus(StringEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageType(StringEnum):
    LOAD = "load"
    REMOVE_BG = "remove_bg"
    UPSCALE = "upscale"
    RESIZE = "resize"
    SAVE = "save"

    @property
    def label(self) -> str:
        return _STAGE_LABELS[self]


_STAGE_LABELS = {
    StageType.LOAD: "Loading",
    StageType.REMOVE_BG: "Remove Background",
    StageType.UPSCALE: "Upscaling",
    StageType.RESIZE: "Resizing",
    StageType.SAVE: "Saving",
}


@dataclass
class Stage:
    type: StageType
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: float = 0.0
    error: Optional[str] = None
    success: bool = False


@dataclass
class PipelineJob:
    job_id: str
    images: List[Image]
    status: JobStatus = JobStatus.QUEUED
    current_stage: Optional[StageType] = None
    stages: List[Stage] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    elapsed: float = 0.0

    @property
    def total(self) -> int:
        return len(self.images)

    @property
    def progress(self) -> float:
        completed = sum(1 for s in self.stages if s.success)
        return completed / max(self.total * len(self.stages), 1)
