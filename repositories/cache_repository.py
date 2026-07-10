from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.constants import THUMBNAIL_SIZE
from core.logger import get_logger

log = get_logger(__name__)


class CacheRepository:
    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self._cache_dir = Path(cache_dir or self._default_cache_dir())
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _default_cache_dir(self) -> str:
        return str(Path.home() / ".cache" / "PixelForgeAI")

    def _thumbnail_key(self, image_path: str) -> str:
        return hashlib.md5(image_path.encode()).hexdigest()

    def get_thumbnail_path(self, image_path: str) -> Optional[str]:
        key = self._thumbnail_key(image_path)
        path = self._cache_dir / f"thumb_{key}.jpg"
        return str(path) if path.exists() else None

    def save_thumbnail(self, image_path: str, data: bytes) -> str:
        key = self._thumbnail_key(image_path)
        path = self._cache_dir / f"thumb_{key}.jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", dir=str(self._cache_dir))
        tmp.write(data)
        tmp.close()
        os.replace(tmp.name, str(path))
        return str(path)

    def clear(self) -> None:
        count = 0
        for f in self._cache_dir.glob("thumb_*"):
            f.unlink(missing_ok=True)
            count += 1
        log.info(f"Cleared {count} cached thumbnails")
