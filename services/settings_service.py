from __future__ import annotations

from typing import Any, Dict, Optional

from events.base import EventBus
from events.settings_events import SettingsChangedEvent, SettingsLoadedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


class SettingsService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._settings: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        try:
            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository()
            model = repo.load()
            self._settings = model.to_dict() if hasattr(model, "to_dict") else {}
            self._event_bus.emit(SettingsLoadedEvent(settings=self._settings))
        except Exception as e:
            log.error(f"Failed to load settings: {e}")
        return self._settings

    def save(self, settings: Dict[str, Any]) -> None:
        self._settings.update(settings)
        try:
            from models.settings_model import SettingsModel
            model = SettingsModel.from_dict(self._settings) if hasattr(SettingsModel, "from_dict") else SettingsModel()
            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository()
            repo.save(model)
            self._event_bus.emit(SettingsChangedEvent(key="all", value=self._settings))
        except Exception as e:
            log.error(f"Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._event_bus.emit(SettingsChangedEvent(key=key, value=value))
