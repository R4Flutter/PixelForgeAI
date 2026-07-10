from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from application.use_cases.base import UseCase
from common.result import Result, Success, Failure
from events.base import EventBus
from events.image_events import ThumbnailGeneratedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class GenerateThumbnailRequest:
    image_path: str
    size: int = 160


@dataclass
class GenerateThumbnailResponse:
    thumbnail_path: Optional[str]


class GenerateThumbnailUseCase(UseCase[GenerateThumbnailRequest, GenerateThumbnailResponse]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: GenerateThumbnailRequest) -> Result[GenerateThumbnailResponse, str]:
        try:
            from PIL import Image
            import io
            from infrastructure.cache.disk_cache import DiskCache

            cache = DiskCache()
            cached = cache.get(str(hash(request.image_path)))
            if cached:
                return Success(GenerateThumbnailResponse(thumbnail_path=cached))

            img = Image.open(request.image_path)
            img.thumbnail((request.size, request.size), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=85)

            import hashlib
            key = hashlib.md5(request.image_path.encode()).hexdigest()
            thumb_path = cache.set(key, buf.getvalue())

            self._event_bus.emit(ThumbnailGeneratedEvent(
                source_path=request.image_path, thumbnail_path=thumb_path or "",
            ))
            return Success(GenerateThumbnailResponse(thumbnail_path=thumb_path))
        except Exception as e:
            log.warning(f"Thumbnail generation failed: {e}")
            return Success(GenerateThumbnailResponse(thumbnail_path=None))
