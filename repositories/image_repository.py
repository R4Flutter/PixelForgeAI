from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from core.constants import IMAGE_SUFFIXES
from core.exceptions import ImageLoadError
from core.logger import get_logger

log = get_logger(__name__)


class ImageRepository:
    def list_images(self, directory: str) -> List[str]:
        path = Path(directory)
        if not path.is_dir():
            log.warning(f"Not a directory: {directory}")
            return []
        return [str(f) for f in path.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES and f.is_file()]

    def validate_path(self, path: str) -> Optional[str]:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.suffix.lower() not in IMAGE_SUFFIXES:
            return f"Unsupported format: {path}"
        if not p.is_file():
            return f"Not a file: {path}"
        return None

    def get_file_size(self, path: str) -> int:
        return Path(path).stat().st_size

    def file_exists(self, path: str) -> bool:
        return Path(path).is_file()
