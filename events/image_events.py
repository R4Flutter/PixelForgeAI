from __future__ import annotations

from dataclasses import dataclass
from typing import List

from events.base import Event


@dataclass
class ImagesAddedEvent(Event):
    paths: List[str]
    count: int


@dataclass
class ImagesRemovedEvent(Event):
    paths: List[str]


@dataclass
class ImageSelectedEvent(Event):
    path: str
    index: int


@dataclass
class ThumbnailGeneratedEvent(Event):
    source_path: str
    thumbnail_path: str
