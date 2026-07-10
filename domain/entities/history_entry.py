from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from domain.entities.image import OutputImage
from domain.entities.pipeline_job import PipelineJob


@dataclass
class HistoryEntry:
    job: PipelineJob
    outputs: List[OutputImage] = field(default_factory=list)
    timestamp: float = 0.0
