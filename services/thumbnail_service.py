from __future__ import annotations

from typing import Optional

from plogging.logger import get_logger
from services.cache_service import CacheService

log = get_logger(__name__)


class ThumbnailService:
    def __init__(self, cache_service: CacheService) -> None:
        self._cache = cache_service
        self._thumb_size = 160

    def get_or_create(self, image_path: str) -> Optional[str]:
        cached = self._cache.get_thumbnail(image_path)
        if cached:
            return cached
        try:
            from PIL import Image
            import io
            img = Image.open(image_path)
            img.thumbnail((self._thumb_size, self._thumb_size), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=85)
            return self._cache.save_thumbnail(image_path, buf.getvalue())
        except Exception as e:
            log.warning(f"Thumbnail failed for {image_path}: {e}")
            return None
