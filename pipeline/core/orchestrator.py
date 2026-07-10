from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from core.enums import PipelineStage
from plogging.logger import get_logger
from pipeline.models.stage_result import StageResult
from pipeline.stages.remove_bg import RemoveBgStage
from pipeline.stages.upscale import UpscaleStage
from pipeline.stages.resize import ResizeStage
from pipeline.validators.image_validator import ImageValidator

log = get_logger(__name__)


class PipelineOrchestrator:
    def __init__(self, settings: Any = None) -> None:
        self._settings = settings
        self._validator = ImageValidator()
        self._remove_bg = RemoveBgStage()
        self._upscale = UpscaleStage()
        self._resize = ResizeStage()
        self._on_stage: Optional[callable] = None
        self._on_progress: Optional[callable] = None

    def on_stage(self, callback: callable) -> None:
        self._on_stage = callback

    def on_progress(self, callback: callable) -> None:
        self._on_progress = callback

    def execute(
        self,
        image_path: str,
        settings: Any = None,
        cancel_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
    ) -> StageResult:
        cfg = settings or self._settings
        output_dir = getattr(cfg, "output_folder", "output/final") if hasattr(cfg, "output_folder") else "output/final"
        if isinstance(cfg, dict):
            output_dir = cfg.get("output_folder", "output/final")

        os.makedirs(output_dir, exist_ok=True)

        stages = [
            (PipelineStage.REMOVE_BG, self._remove_bg),
            (PipelineStage.UPSCALE, self._upscale),
            (PipelineStage.RESIZE, self._resize),
        ]

        current_path = image_path

        for stage_name, stage in stages:
            if cancel_event and cancel_event.is_set():
                return StageResult(stage=stage_name, success=False, error="Cancelled")

            while pause_event and pause_event.is_set():
                if cancel_event and cancel_event.is_set():
                    return StageResult(stage=stage_name, success=False, error="Cancelled")
                time.sleep(0.1)

            if self._on_stage:
                self._on_stage(stage_name)

            try:
                result = stage.execute(current_path, output_dir, cfg)
                if not result or not os.path.isfile(str(result)):
                    return StageResult(stage=stage_name, success=False, error=f"{stage_name.value} returned no output")
                current_path = str(result)
            except Exception as e:
                log.error(f"Stage {stage_name.value} failed: {e}")
                return StageResult(stage=stage_name, success=False, error=str(e))

        return StageResult(stage=PipelineStage.SAVE, success=True, output_path=current_path)
