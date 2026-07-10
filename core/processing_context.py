from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.enums import PipelineStage, ProcessingStatus


@dataclass
class ImageResult:
    path: Path
    status: ProcessingStatus = ProcessingStatus.QUEUED
    current_stage: Optional[PipelineStage] = None
    error: Optional[str] = None
    output_path: Optional[Path] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[float] = None


@dataclass
class ProcessingContext:
    job_id: str = ""
    status: ProcessingStatus = ProcessingStatus.QUEUED
    total_images: int = 0
    completed_count: int = 0
    failed_count: int = 0
    current_file: str = ""
    current_stage: Optional[PipelineStage] = None

    image_results: Dict[str, ImageResult] = field(default_factory=dict)
    failed_files: List[str] = field(default_factory=list)
    output_folder: Optional[str] = None

    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    elapsed_seconds: float = 0.0

    cancel_requested: bool = False
    pause_requested: bool = False

    _ordered_paths: List[str] = field(default_factory=list, repr=False)

    def begin(self, paths: List[str], job_id: str = "") -> None:
        self.job_id = job_id or str(time.time_ns())
        self.status = ProcessingStatus.RUNNING
        self.total_images = len(paths)
        self.completed_count = 0
        self.failed_count = 0
        self.failed_files.clear()
        self.image_results.clear()
        self.cancel_requested = False
        self.pause_requested = False
        self.started_at = time.time()
        self.finished_at = None
        self._ordered_paths = list(paths)

        for p in paths:
            self.image_results[p] = ImageResult(path=Path(p))

    def mark_completed(self, path: str, output_path: Optional[Path] = None) -> None:
        result = self.image_results.get(path)
        if result:
            result.status = ProcessingStatus.COMPLETED
            result.completed_at = time.time()
            result.duration = (result.completed_at - (result.started_at or result.completed_at))
            result.output_path = output_path
        self.completed_count += 1
        self._check_done()

    def mark_failed(self, path: str, error: str) -> None:
        result = self.image_results.get(path)
        if result:
            result.status = ProcessingStatus.FAILED
            result.error = error
            result.completed_at = time.time()
        self.failed_count += 1
        self.failed_files.append(path)
        self._check_done()

    def set_stage(self, path: str, stage: PipelineStage) -> None:
        result = self.image_results.get(path)
        if result:
            result.current_stage = stage
        self.current_stage = stage

    def set_current_file(self, path: str) -> None:
        self.current_file = path
        result = self.image_results.get(path)
        if result:
            result.started_at = result.started_at or time.time()

    def cancel(self) -> None:
        self.cancel_requested = True

    def pause(self) -> None:
        self.pause_requested = True
        if self.status == ProcessingStatus.RUNNING:
            self.status = ProcessingStatus.PAUSED

    def resume(self) -> None:
        self.pause_requested = False
        if self.status == ProcessingStatus.PAUSED:
            self.status = ProcessingStatus.RUNNING

    def finish(self) -> None:
        self.finished_at = time.time()
        if self.started_at:
            self.elapsed_seconds = self.finished_at - self.started_at

        if self.status != ProcessingStatus.CANCELLED:
            self.status = ProcessingStatus.COMPLETED if self.failed_count == 0 else ProcessingStatus.COMPLETED

    def progress(self) -> float:
        if self.total_images == 0:
            return 0.0
        return (self.completed_count + self.failed_count) / self.total_images

    def _check_done(self) -> None:
        if self.completed_count + self.failed_count >= self.total_images:
            self.finish()
