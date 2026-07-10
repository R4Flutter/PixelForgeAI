from features.home.controller import HomeController
from features.home.state import HomeState


class HomeFeature:
    def __init__(self, controller: HomeController, state: HomeState) -> None:
        self._controller = controller
        self._state = state

    @property
    def controller(self) -> HomeController:
        return self._controller

    @property
    def state(self) -> HomeState:
        return self._state
