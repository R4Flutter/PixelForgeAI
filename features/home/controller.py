from __future__ import annotations

from typing import Any, List, Optional

from commands.base import CommandDispatcher
from commands.pipeline_commands import StartPipelineCommand
from events.base import EventBus
from gui.home import HomePage


class HomeController:
    def __init__(self, page: HomePage, dispatcher: CommandDispatcher, event_bus: EventBus) -> None:
        self._page = page
        self._dispatcher = dispatcher
        self._event_bus = event_bus

    def start_pipeline(self, paths: List[str], settings: Any) -> None:
        cmd = StartPipelineCommand(
            paths=paths,
            settings=settings,
            event_bus=self._event_bus,
        )
        self._dispatcher.dispatch(cmd)

    @property
    def page(self) -> HomePage:
        return self._page
