from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from commands.base import Command, CommandResult
from events.base import EventBus
from events.export_events import ExportCompletedEvent, ExportFailedEvent, ExportStartedEvent
from plogging.logger import get_logger

log = get_logger(__name__)


@dataclass
class ExportImagesCommand(Command[int]):
    source_paths: List[str]
    output_dir: str
    event_bus: Optional[EventBus] = None

    def execute(self) -> CommandResult[int]:
        if self.event_bus:
            self.event_bus.emit(ExportStartedEvent(
                count=len(self.source_paths), output_dir=self.output_dir,
            ))

        exported = 0
        for src in self.source_paths:
            try:
                import shutil
                from pathlib import Path
                dest = Path(self.output_dir) / Path(src).name
                shutil.copy2(src, str(dest))
                exported += 1
            except Exception as e:
                log.error(f"Export failed for {src}: {e}")

        if self.event_bus:
            self.event_bus.emit(ExportCompletedEvent(
                count=exported, output_dir=self.output_dir,
            ))

        return CommandResult(success=True, value=exported)


@dataclass
class OpenOutputFolderCommand(Command[None]):
    folder: str

    def execute(self) -> CommandResult[None]:
        import os
        import sys
        if not self.folder:
            return CommandResult(success=False, error="No output folder")
        try:
            if sys.platform == "win32":
                os.startfile(self.folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", self.folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", self.folder])
            return CommandResult(success=True)
        except Exception as e:
            return CommandResult(success=False, error=str(e))
