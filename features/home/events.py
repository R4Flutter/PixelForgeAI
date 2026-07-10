from __future__ import annotations

from dataclasses import dataclass
from typing import List

from events.base import Event


@dataclass
class HomePageShownEvent(Event):
    pass


@dataclass
class DropZoneActivatedEvent(Event):
    pass


@dataclass
class ImagesValidatedEvent(Event):
    valid: List[str]
    invalid: List[str]
