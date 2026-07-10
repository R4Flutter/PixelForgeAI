from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from store.base import Action, Reducer, Store


@dataclass
class SettingsState:
    output_folder: str = "output/final"
    output_format: str = "png"
    output_width: int = 4000
    output_height: int = 4000
    quality: int = 95
    upscale_mode: str = "auto"
    device: str = "gpu"
    raw: Dict[str, Any] = field(default_factory=dict)


def settings_reducer(state: SettingsState, action: Action) -> SettingsState:
    p = action.payload
    if action.type == "SETTINGS_LOAD":
        raw = p.get("settings", {})
        return SettingsState(
            output_folder=raw.get("output_folder", state.output_folder),
            output_format=raw.get("output_format", state.output_format),
            output_width=raw.get("output_width", state.output_width),
            output_height=raw.get("output_height", state.output_height),
            quality=raw.get("jpg_quality", state.quality),
            upscale_mode=raw.get("upscale_mode", state.upscale_mode),
            device=raw.get("device", state.device),
            raw=raw,
        )
    if action.type == "SETTINGS_UPDATE":
        updated = {**state.raw, **p.get("settings", {})}
        return SettingsState(raw=updated, **{k: v for k, v in updated.items()
                            if k in SettingsState.__dataclass_fields__})
    return state


class SettingsStore(Store[SettingsState]):
    def __init__(self) -> None:
        super().__init__(SettingsState(), settings_reducer)
