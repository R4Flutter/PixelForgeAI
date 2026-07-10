from features.processing.controller import ProcessingController
from features.processing.state import ProcessingState as ProcessingFeatureState


class ProcessingFeature:
    def __init__(self, controller: ProcessingController, state: ProcessingFeatureState) -> None:
        self._controller = controller
        self._state = state

    @property
    def controller(self) -> ProcessingController:
        return self._controller

    @property
    def state(self) -> ProcessingFeatureState:
        return self._state
