from __future__ import annotations

from typing import Optional

from commands.base import CommandDispatcher
from events.base import EventBus
from events.pipeline_events import PipelineCompletedEvent


class ResultsController:
    def __init__(self, dispatcher: CommandDispatcher, event_bus: EventBus) -> None:
        self._dispatcher = dispatcher
        self._event_bus = event_bus

    def export_images(self, source_paths: list, output_dir: str) -> None:
        from commands.export_commands import ExportImagesCommand
        cmd = ExportImagesCommand(
            source_paths=source_paths,
            output_dir=output_dir,
            event_bus=self._event_bus,
        )
        self._dispatcher.dispatch(cmd)

    def open_output_folder(self, folder: str) -> None:
        from commands.export_commands import OpenOutputFolderCommand
        cmd = OpenOutputFolderCommand(folder=folder)
        self._dispatcher.dispatch(cmd)

    def process_again(self) -> None:
        pass
