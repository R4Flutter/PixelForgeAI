from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from store.base import Action, Reducer, Store


@dataclass
class AppState:
    current_page: int = 0
    theme: str = "dark"
    version: str = "1.0.0"
    is_processing: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def app_reducer(state: AppState, action: Action) -> AppState:
    if action.type == "SET_PAGE":
        return AppState(current_page=action.payload.get("page", 0), theme=state.theme, version=state.version, is_processing=state.is_processing)
    if action.type == "SET_THEME":
        return AppState(current_page=state.current_page, theme=action.payload.get("theme", "dark"), version=state.version, is_processing=state.is_processing)
    if action.type == "SET_PROCESSING":
        return AppState(current_page=state.current_page, theme=state.theme, version=state.version, is_processing=action.payload.get("running", False))
    return state


class AppStore(Store[AppState]):
    def __init__(self) -> None:
        super().__init__(AppState(), app_reducer)
