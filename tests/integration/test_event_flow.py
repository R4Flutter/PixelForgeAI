from __future__ import annotations

from dataclasses import dataclass

from events.base import Event, EventBus
from commands.base import Command, CommandResult, CommandDispatcher


class TestEventCommandFlow:
    def test_command_emits_events(self, event_bus) -> None:
        from dataclasses import dataclass

        @dataclass
        class TestEvent(Event):
            data: str = ""

        @dataclass
        class EmitCommand(Command[None]):
            event_bus: EventBus

            def execute(self) -> CommandResult[None]:
                self.event_bus.emit(TestEvent(data="from_command"))
                return CommandResult(success=True)

        results = []
        event_bus.on(TestEvent, lambda e: results.append(e.data))

        dispatcher = CommandDispatcher(event_bus)
        dispatcher.dispatch(EmitCommand(event_bus=event_bus))

        assert results == ["from_command"]
