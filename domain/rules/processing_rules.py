from __future__ import annotations

from domain.entities.image import Image
from domain.entities.pipeline_job import PipelineJob


class ProcessingRules:
    MIN_DIM = 64
    MAX_DIM = 12000
    MAX_FILE_SIZE_MB = 50

    @staticmethod
    def can_process(image: Image) -> bool:
        return image.is_supported

    @staticmethod
    def can_start(job: PipelineJob) -> bool:
        return job.total > 0

    @staticmethod
    def is_dimension_valid(width: int, height: int) -> bool:
        return ProcessingRules.MIN_DIM <= width <= ProcessingRules.MAX_DIM and \
               ProcessingRules.MIN_DIM <= height <= ProcessingRules.MAX_DIM
