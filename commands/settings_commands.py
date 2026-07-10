from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from commands.base import Command, CommandResult
from events.base import EventBus
from events.settings_events import SettingsChangedEvent, SettingsLoadedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class ChangeSettingCommand(Command[None]):
    key: str
    value: Any
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        if self.event_bus:
            self.event_bus.emit(SettingsChangedEvent(key=self.key, value=self.value))
        log.info(f"Setting changed: {self.key} = {self.value}")
        return CommandResult(success=True)


@dataclass
class LoadSettingsCommand(Command[dict]):
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[dict]:
        from repositories.settings_repository import SettingsRepository
        repo = SettingsRepository()
        settings = repo.load()
        if self.event_bus:
            self.event_bus.emit(SettingsLoadedEvent(settings={"loaded": True}))
        return CommandResult(success=True, value=settings)


@dataclass
class SaveSettingsCommand(Command[None]):
    settings: Any
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[None]:
        from repositories.settings_repository import SettingsRepository
        repo = SettingsRepository()
        repo.save(self.settings)
        if self.event_bus:
            self.event_bus.emit(SettingsChangedEvent(key="all", value=self.settings))
        return CommandResult(success=True)
