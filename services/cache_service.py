from __future__ import annotations

from typing import Optional

from events.base import EventBus
from events.image_events import ThumbnailGeneratedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


class CacheService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def get_thumbnail(self, image_path: str) -> Optional[str]:
        try:
            from repositories.cache_repository import CacheRepository
            repo = CacheRepository()
            return repo.get_thumbnail_path(image_path)
        except Exception:
            return None

    def save_thumbnail(self, image_path: str, data: bytes) -> Optional[str]:
        try:
            from repositories.cache_repository import CacheRepository
            repo = CacheRepository()
            path = repo.save_thumbnail(image_path, data)
            self._event_bus.emit(ThumbnailGeneratedEvent(
                source_path=image_path, thumbnail_path=path,
            ))
            return path
        except Exception as e:
            log.error(f"Thumbnail save failed: {e}")
            return None

    def clear(self) -> None:
        try:
            from repositories.cache_repository import CacheRepository
            repo = CacheRepository()
            repo.clear()
        except Exception as e:
            log.error(f"Cache clear failed: {e}")
