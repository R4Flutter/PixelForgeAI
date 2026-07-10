from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from store.base import Action, Reducer, Store


@dataclass
class SessionState:
    recent_projects: List[str] = field(default_factory=list)
    last_output_folder: str = ""
    window_width: int = 1180
    window_height: int = 760
    license_status: str = "trial"
    metadata: Dict[str, Any] = field(default_factory=dict)


def session_reducer(state: SessionState, action: Action) -> SessionState:
    p = action.payload
    if action.type == "SESSION_UPDATE":
        return SessionState(
            recent_projects=p.get("recent", state.recent_projects),
            last_output_folder=p.get("output_folder", state.last_output_folder),
            window_width=p.get("width", state.window_width),
            window_height=p.get("height", state.window_height),
            license_status=p.get("license", state.license_status),
        )
    if action.type == "SESSION_ADD_RECENT":
        projects = [p.get("path", "")] + [r for r in state.recent_projects if r != p.get("path", "")]
        return SessionState(recent_projects=projects[:10], last_output_folder=state.last_output_folder,
            window_width=state.window_width, window_height=state.window_height,
            license_status=state.license_status)
    return state


class SessionStore(Store[SessionState]):
    def __init__(self) -> None:
        super().__init__(SessionState(), session_reducer)
