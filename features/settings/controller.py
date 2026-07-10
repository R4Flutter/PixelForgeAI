from __future__ import annotations

from typing import Any, Dict, Optional

from commands.base import CommandDispatcher
from events.base import EventBus


class SettingsController:
    def __init__(self, dispatcher: CommandDispatcher, event_bus: EventBus) -> None:
        self._dispatcher = dispatcher
        self._event_bus = event_bus

    def load_settings(self) -> None:
        from commands.settings_commands import LoadSettingsCommand
        cmd = LoadSettingsCommand(event_bus=self._event_bus)
        self._dispatcher.dispatch(cmd)

    def save_settings(self, settings: Dict[str, Any]) -> None:
        from commands.settings_commands import SaveSettingsCommand
        cmd = SaveSettingsCommand(settings=settings, event_bus=self._event_bus)
        self._dispatcher.dispatch(cmd)

    def change_setting(self, key: str, value: Any) -> None:
        from commands.settings_commands import ChangeSettingCommand
        cmd = ChangeSettingCommand(key=key, value=value, event_bus=self._event_bus)
        self._dispatcher.dispatch(cmd)
