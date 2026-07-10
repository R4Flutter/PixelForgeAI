from __future__ import annotations

from dataclasses import dataclass
from typing import List

from events.base import Event


@dataclass
class ExportStartedEvent(Event):
    count: int
    output_dir: str


@dataclass
class ExportCompletedEvent(Event):
    count: int
    output_dir: str


@dataclass
class ExportFailedEvent(Event):
    error: str
    path: str
