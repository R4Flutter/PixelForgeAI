from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from application.use_cases.base import UseCase
from common.result import Result, Success
from events.base import EventBus
from events.settings_events import SettingsChangedEvent, SettingsLoadedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class LoadSettingsResponse:
    settings: Dict[str, Any]


class LoadSettingsUseCase(UseCase[None, LoadSettingsResponse]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request=None) -> Result[LoadSettingsResponse, str]:
        try:
            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository()
            model = repo.load()
            data = model.to_dict() if hasattr(model, "to_dict") else {}
            self._event_bus.emit(SettingsLoadedEvent(settings=data))
            return Success(LoadSettingsResponse(settings=data))
        except Exception as e:
            log.error(f"Failed to load settings: {e}")
            return Success(LoadSettingsResponse(settings={}))


@dataclass
class SaveSettingsRequest:
    settings: Dict[str, Any]


class SaveSettingsUseCase(UseCase[SaveSettingsRequest, None]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: SaveSettingsRequest) -> Result[None, str]:
        try:
            from models.settings_model import SettingsModel
            model = SettingsModel.from_dict(request.settings)
            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository()
            repo.save(model)
            self._event_bus.emit(SettingsChangedEvent(key="all", value=request.settings))
            return Success(None)
        except Exception as e:
            log.error(f"Failed to save settings: {e}")
            return Success(None)
