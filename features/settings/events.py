from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from events.base import Event


@dataclass
class SettingsPageShownEvent(Event):
    pass


@dataclass
class SettingsAppliedEvent(Event):
    settings: Dict[str, Any]
