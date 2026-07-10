from __future__ import annotations

from typing import Optional

from commands.base import CommandDispatcher
from events.base import EventBus
from events.pipeline_events import (
    PipelineCancelledEvent,
    PipelineCompletedEvent,
    PipelineFailedEvent,
    PipelinePausedEvent,
    PipelineResumedEvent,
    PipelineStartedEvent,
    ProgressUpdatedEvent,
    StageStartedEvent,
)


class ProcessingController:
    def __init__(self, dispatcher: CommandDispatcher, event_bus: EventBus) -> None:
        self._dispatcher = dispatcher
        self._event_bus = event_bus
        self._wire_events()

    def _wire_events(self) -> None:
        self._event_bus.on(PipelineStartedEvent, self._on_started)
        self._event_bus.on(ProgressUpdatedEvent, self._on_progress)
        self._event_bus.on(StageStartedEvent, self._on_stage)
        self._event_bus.on(PipelineCompletedEvent, self._on_completed)
        self._event_bus.on(PipelineFailedEvent, self._on_failed)
        self._event_bus.on(PipelineCancelledEvent, self._on_cancelled)
        self._event_bus.on(PipelinePausedEvent, self._on_paused)
        self._event_bus.on(PipelineResumedEvent, self._on_resumed)

    def _on_started(self, event: PipelineStartedEvent) -> None:
        pass

    def _on_progress(self, event: ProgressUpdatedEvent) -> None:
        pass

    def _on_stage(self, event: StageStartedEvent) -> None:
        pass

    def _on_completed(self, event: PipelineCompletedEvent) -> None:
        pass

    def _on_failed(self, event: PipelineFailedEvent) -> None:
        pass

    def _on_cancelled(self, event: PipelineCancelledEvent) -> None:
        pass

    def _on_paused(self, event: PipelinePausedEvent) -> None:
        pass

    def _on_resumed(self, event: PipelineResumedEvent) -> None:
        pass

    def pause(self) -> None:
        from commands.pipeline_commands import PausePipelineCommand
        cmd = PausePipelineCommand(job_id="", event_bus=self._event_bus)
        self._dispatcher.dispatch(cmd)

    def resume(self) -> None:
        from commands.pipeline_commands import ResumePipelineCommand
        cmd = ResumePipelineCommand(job_id="", event_bus=self._event_bus)
        self._dispatcher.dispatch(cmd)

    def cancel(self) -> None:
        from commands.pipeline_commands import CancelPipelineCommand
        cmd = CancelPipelineCommand(job_id="", event_bus=self._event_bus)
        self._dispatcher.dispatch(cmd)
