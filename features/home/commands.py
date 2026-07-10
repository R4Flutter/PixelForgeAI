from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from commands.base import Command, CommandResult
from events.base import EventBus
from events.image_events import ImagesAddedEvent, ImagesRemovedEvent, ImageSelectedEvent


@dataclass
class AddImagesCommand(Command[List[str]]):
    paths: List[str]
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[List[str]]:
        if self.event_bus:
            self.event_bus.emit(ImagesAddedEvent(paths=self.paths, count=len(self.paths)))
        return CommandResult(success=True, value=self.paths)


@dataclass
class RemoveImagesCommand(Command[None]):
    paths: List[str]
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(ImagesRemovedEvent(paths=self.paths))
        return CommandResult(success=True)


@dataclass
class SelectImageCommand(Command[None]):
    path: str
    index: int
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(ImageSelectedEvent(path=self.path, index=self.index))
        return CommandResult(success=True)


@dataclass
class ClearImagesCommand(Command[None]):
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(ImagesRemovedEvent(paths=[]))
        return CommandResult(success=True)
