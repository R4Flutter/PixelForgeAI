from __future__ import annotations

from dataclasses import dataclass

from events.base import Event


@dataclass
class HistoryPageShownEvent(Event):
    pass


@dataclass
class HistoryEntrySelectedEvent(Event):
    job_id: str
