from __future__ import annotations

from dataclasses import dataclass

from application.use_cases.base import UseCase
from common.result import Result, Success
from events.base import EventBus
from store.app_store import AppStore
from store.base import Action


@dataclass
class NavigatePageRequest:
    page_index: int


class NavigatePageUseCase(UseCase[NavigatePageRequest, None]):
    def __init__(self, app_store: AppStore, event_bus: EventBus) -> None:
        self._app_store = app_store
        self._event_bus = event_bus

    def execute(self, request: NavigatePageRequest) -> Result[None, str]:
        self._app_store.dispatch(Action(type="SET_PAGE", payload={"page": request.page_index}))
        return Success(None)


class SetProcessingStateUseCase(UseCase):
    def __init__(self, app_store: AppStore) -> None:
        self._app_store = app_store

    def execute(self, request=None) -> Result[None, str]:
        is_running = getattr(request, "running", False) if request else False
        self._app_store.dispatch(Action(type="SET_PROCESSING", payload={"running": is_running}))
        return Success(None)
