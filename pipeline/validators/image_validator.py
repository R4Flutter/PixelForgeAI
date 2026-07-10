from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from core.constants import IMAGE_SUFFIXES
from plogging.logger import get_logger

log = get_logger(__name__)


class ImageValidator:
    SUPPORTED = IMAGE_SUFFIXES

    def validate(self, path: str) -> Optional[str]:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.suffix.lower() not in self.SUPPORTED:
            return f"Unsupported format: {path}"
        if not p.is_file():
            return f"Not a file: {path}"
        return None

    def filter_valid(self, paths: List[str]) -> List[str]:
        valid = []
        for p in paths:
            if self.validate(p) is None:
                valid.append(p)
            else:
                log.warning(f"Skipping invalid file: {p}")
        return valid
