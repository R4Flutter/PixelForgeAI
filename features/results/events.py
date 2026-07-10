from __future__ import annotations

from dataclasses import dataclass

from events.base import Event


@dataclass
class ResultsPageShownEvent(Event):
    pass


@dataclass
class ExportRequestedEvent(Event):
    source_paths: list
    output_dir: str
