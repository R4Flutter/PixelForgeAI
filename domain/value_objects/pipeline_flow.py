from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from domain.entities.pipeline_job import StageType


@dataclass(frozen=True)
class PipelineFlow:
    stages: Tuple[StageType, ...] = (
        StageType.REMOVE_BG,
        StageType.UPSCALE,
        StageType.RESIZE,
        StageType.SAVE,
    )

    @property
    def count(self) -> int:
        return len(self.stages)

    def index_of(self, stage: StageType) -> int:
        try:
            return self.stages.index(stage)
        except ValueError:
            return -1
