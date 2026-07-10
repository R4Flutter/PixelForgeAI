from __future__ import annotations

from dataclasses import dataclass

from events.base import Event


@dataclass
class ProcessingPageShownEvent(Event):
    pass


@dataclass
class LogLineAppendedEvent(Event):
    line: str
