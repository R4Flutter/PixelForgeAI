from features.history.controller import HistoryController
from features.history.state import HistoryState


class HistoryFeature:
    def __init__(self, controller: HistoryController, state: HistoryState) -> None:
        self._controller = controller
        self._state = state

    @property
    def controller(self) -> HistoryController:
        return self._controller

    @property
    def state(self) -> HistoryState:
        return self._state
