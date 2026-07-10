from __future__ import annotations

from dataclasses import dataclass
from typing import List

from application.use_cases.base import UseCase
from common.result import Result, Success
from events.base import EventBus
from events.history_events import HistoryClearedEvent, HistoryEntryAddedEvent, HistoryLoadedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class HistoryEntryData:
    job_id: str
    total: int
    succeeded: int
    failed: int
    timestamp: float = 0.0
    output_folder: str = ""


@dataclass
class AddHistoryEntryRequest:
    job_id: str
    total: int
    succeeded: int
    failed: int
    output_folder: str = ""


@dataclass
class LoadHistoryResponse:
    entries: List[dict]


class AddHistoryEntryUseCase(UseCase[AddHistoryEntryRequest, None]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request: AddHistoryEntryRequest) -> Result[None, str]:
        self._event_bus.emit(HistoryEntryAddedEvent(
            job_id=request.job_id,
            total=request.total,
            succeeded=request.succeeded,
            failed=request.failed,
            output_folder=request.output_folder,
        ))
        return Success(None)


class LoadHistoryUseCase(UseCase[None, LoadHistoryResponse]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request=None) -> Result[LoadHistoryResponse, str]:
        from services.history_service import HistoryService
        service = HistoryService(self._event_bus)
        entries = [{
            "job_id": e.job_id,
            "total": e.total,
            "succeeded": e.succeeded,
            "failed": e.failed,
            "timestamp": e.timestamp,
            "output_folder": e.output_folder,
        } for e in service.recent(50)]
        self._event_bus.emit(HistoryLoadedEvent(entries=entries))
        return Success(LoadHistoryResponse(entries=entries))


class ClearHistoryUseCase(UseCase[None, None]):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def execute(self, request=None) -> Result[None, str]:
        from services.history_service import HistoryService
        service = HistoryService(self._event_bus)
        service.clear()
        self._event_bus.emit(HistoryClearedEvent())
        return Success(None)
