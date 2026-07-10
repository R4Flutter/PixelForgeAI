from __future__ import annotations

import time
from typing import Any, Optional

from core.enums import PipelineStage
from plogging.logger import get_logger
from pipeline.models.stage_result import StageResult
from pipeline.stages.remove_bg import RemoveBgStage
from pipeline.stages.upscale import UpscaleStage
from pipeline.stages.resize import ResizeStage
from pipeline.progress import ProgressTracker

log = get_logger(__name__)


class StageExecutor:
    def __init__(self, tracker: Optional[ProgressTracker] = None) -> None:
        self._tracker = tracker or ProgressTracker()
        self._stages = {
            PipelineStage.REMOVE_BG: RemoveBgStage(),
            PipelineStage.UPSCALE: UpscaleStage(),
            PipelineStage.RESIZE: ResizeStage(),
        }

    def execute(self, image_path: str, output_dir: str, settings: Any) -> StageResult:
        for stage in [PipelineStage.REMOVE_BG, PipelineStage.UPSCALE, PipelineStage.RESIZE]:
            if self._tracker:
                self._tracker.set_stage(stage)
            result = self._run_stage(stage, image_path, output_dir, settings)
            if not result.success:
                return result
        return StageResult(stage=PipelineStage.RESIZE, success=True, output_path=output_dir)

    def _run_stage(self, stage: PipelineStage, image_path: str, output_dir: str, settings: Any) -> StageResult:
        handler = self._stages.get(stage)
        if handler is None:
            return StageResult(stage=stage, success=True)

        start = time.time()
        try:
            result_path = handler.execute(image_path, output_dir, settings)
            return StageResult(
                stage=stage,
                success=True,
                output_path=result_path,
                duration=time.time() - start,
            )
        except Exception as e:
            return StageResult(
                stage=stage,
                success=False,
                error=str(e),
                duration=time.time() - start,
            )
