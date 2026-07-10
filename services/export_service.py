from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from events.base import EventBus
from events.export_events import ExportCompletedEvent, ExportFailedEvent, ExportStartedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


class ExportService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def export(self, source_paths: List[str], output_dir: str) -> int:
        self._event_bus.emit(ExportStartedEvent(count=len(source_paths), output_dir=output_dir))
        exported = 0
        for src in source_paths:
            try:
                dest = Path(output_dir) / Path(src).name
                shutil.copy2(src, str(dest))
                exported += 1
            except Exception as e:
                log.error(f"Export failed: {src} â†’ {e}")
                self._event_bus.emit(ExportFailedEvent(error=str(e), path=src))
        self._event_bus.emit(ExportCompletedEvent(count=exported, output_dir=output_dir))
        return exported
