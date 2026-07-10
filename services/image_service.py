from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from events.base import EventBus
from events.image_events import ImagesAddedEvent, ImagesRemovedEvent, ImageSelectedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


class ImageService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def add(self, paths: List[str]) -> List[str]:
        valid = []
        for p in paths:
            path = Path(p)
            if path.is_file():
                valid.append(p)
        if valid:
            self._event_bus.emit(ImagesAddedEvent(paths=valid, count=len(valid)))
        return valid

    def remove(self, paths: List[str]) -> None:
        self._event_bus.emit(ImagesRemovedEvent(paths=paths))

    def select(self, path: str, index: int) -> None:
        self._event_bus.emit(ImageSelectedEvent(path=path, index=index))
