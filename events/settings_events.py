from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from events.base import Event


@dataclass
class SettingsChangedEvent(Event):
    key: str
    value: Any


@dataclass
class SettingsLoadedEvent(Event):
    settings: Dict[str, Any]
