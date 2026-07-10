from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from domain.models import (
    ExportProfile,
    Image,
    ImageKind,
    JobStatistics,
    OutputFormat,
    OutputImage,
    PipelineJob,
)


@dataclass(frozen=True)
class ExportSpec:
    profile: ExportProfile
    output_dir: str


class ImageValidator:
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}

    @staticmethod
    def validate(path: str) -> Optional[str]:
        import os
        if not os.path.isfile(path):
            return f"Not a file: {path}"
        ext = os.path.splitext(path)[1].lower()
        if ext not in ImageValidator.SUPPORTED_EXTENSIONS:
            return f"Unsupported format: {ext}"
        return None

    @staticmethod
    def classify(path: str) -> ImageKind:
        ext = path.lower()
        if any(x in ext for x in [".jpg", ".jpeg"]):
            return ImageKind.PHOTO
        if ".png" in ext:
            p = path.lower()
            if "icon" in p or "logo" in p:
                return ImageKind.VECTOR
            return ImageKind.DESIGN
        return ImageKind.UNKNOWN


class JobCalculator:
    @staticmethod
    def estimate_time(total: int, completed: int, elapsed: float) -> float:
        if completed == 0:
            return 0.0
        remaining = total - completed
        per_item = elapsed / completed
        return per_item * remaining

    @staticmethod
    def compute_statistics(job: PipelineJob, outputs: List[OutputImage]) -> JobStatistics:
        return JobStatistics(
            total_images=job.total,
            succeeded=sum(1 for o in outputs if o.succeeded),
            failed=sum(1 for o in outputs if not o.succeeded),
            elapsed_seconds=job.elapsed,
            total_file_size=sum(i.file_size for i in job.images),
            output_file_size=sum(o.file_size for o in outputs),
        )
