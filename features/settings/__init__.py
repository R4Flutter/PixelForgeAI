from features.settings.controller import SettingsController
from features.settings.state import SettingsState as FeatureSettingsState


class SettingsFeature:
    def __init__(self, controller: SettingsController, state: FeatureSettingsState) -> None:
        self._controller = controller
        self._state = state

    @property
    def controller(self) -> SettingsController:
        return self._controller

    @property
    def state(self) -> FeatureSettingsState:
        return self._state
