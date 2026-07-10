from __future__ import annotations

import io
from typing import Optional

from infrastructure.cache.disk_cache import DiskCache
from plogging.logger import get_logger

log = get_logger(__name__)


class ThumbnailGenerator:
    def __init__(self, cache: DiskCache, size: int = 160) -> None:
        self._cache = cache
        self._size = size

    def get_or_create(self, image_path: str) -> Optional[str]:
        cached = self._cache.get(image_path, ".jpg")
        if cached:
            return cached

        try:
            from PIL import Image
            img = Image.open(image_path)
            img.thumbnail((self._size, self._size), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=85)
            return self._cache.put(image_path, buf.getvalue(), ".jpg")
        except Exception as e:
            log.warning(f"Thumbnail failed for {image_path}: {e}")
            return None
