from __future__ import annotations

from typing import Optional

from commands.base import CommandDispatcher
from events.base import EventBus
from events.history_events import HistoryClearedEvent, HistoryEntryAddedEvent, HistoryLoadedEvent


class HistoryController:
    def __init__(self, dispatcher: CommandDispatcher, event_bus: EventBus) -> None:
        self._dispatcher = dispatcher
        self._event_bus = event_bus
        self._wire_events()

    def _wire_events(self) -> None:
        self._event_bus.on(HistoryEntryAddedEvent, self._on_entry_added)
        self._event_bus.on(HistoryClearedEvent, self._on_cleared)
        self._event_bus.on(HistoryLoadedEvent, self._on_loaded)

    def _on_entry_added(self, event: HistoryEntryAddedEvent) -> None:
        pass

    def _on_cleared(self, event: HistoryClearedEvent) -> None:
        pass

    def _on_loaded(self, event: HistoryLoadedEvent) -> None:
        pass

    def add_entry(self, job_id: str, total: int, succeeded: int, failed: int, output_folder: str = "") -> None:
        self._event_bus.emit(HistoryEntryAddedEvent(
            job_id=job_id, total=total, succeeded=succeeded, failed=failed, output_folder=output_folder,
        ))

    def clear_history(self) -> None:
        self._event_bus.emit(HistoryClearedEvent())

    def load_history(self) -> None:
        self._event_bus.emit(HistoryLoadedEvent(entries=[]))
