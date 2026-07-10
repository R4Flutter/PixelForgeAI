from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from core.enums import SourceKind

from models.settings_model import SettingsModel


@dataclass(frozen=True)
class ProcessingJob:
    job_id: str
    sources: Tuple[str, ...]
    kind: SourceKind
    settings: SettingsModel
    created_at: float = 0.0

    @classmethod
    def from_images(cls, images: List[str], settings: SettingsModel) -> ProcessingJob:
        return cls(
            job_id=str(time.time_ns()),
            sources=tuple(images),
            kind=SourceKind.FILES,
            settings=settings,
            created_at=time.time(),
        )

    def resolve_image_paths(self) -> List[Path]:
        return [Path(p) for p in self.sources if Path(p).is_file()]
