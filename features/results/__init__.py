from features.results.controller import ResultsController
from features.results.state import ResultsState


class ResultsFeature:
    def __init__(self, controller: ResultsController, state: ResultsState) -> None:
        self._controller = controller
        self._state = state

    @property
    def controller(self) -> ResultsController:
        return self._controller

    @property
    def state(self) -> ResultsState:
        return self._state
