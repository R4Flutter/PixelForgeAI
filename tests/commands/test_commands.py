from __future__ import annotations

from commands.base import Command, CommandResult, CommandDispatcher


class TestCommandResult:
    def test_success_result(self) -> None:
        result = CommandResult(success=True, value="done")
        assert result.success
        assert result.value == "done"

    def test_failure_result(self) -> None:
        result = CommandResult(success=False, error="failed")
        assert not result.success
        assert result.error == "failed"


class TestCommandDispatcher:
    def test_dispatch_success(self, event_bus) -> None:
        from dataclasses import dataclass

        @dataclass
        class SimpleCommand(Command[str]):
            def execute(self) -> CommandResult[str]:
                return CommandResult(success=True, value="ok")

        dispatcher = CommandDispatcher(event_bus)
        result = dispatcher.dispatch(SimpleCommand())
        assert result.success
        assert result.value == "ok"

    def test_dispatch_failure(self, event_bus) -> None:
        from dataclasses import dataclass

        @dataclass
        class FailingCommand(Command[None]):
            def execute(self) -> CommandResult[None]:
                raise RuntimeError("unexpected error")

        dispatcher = CommandDispatcher(event_bus)
        result = dispatcher.dispatch(FailingCommand())
        assert not result.success
        assert "unexpected" in (result.error or "")

    def test_command_history(self, event_bus) -> None:
        from dataclasses import dataclass

        @dataclass
        class Cmd(Command[None]):
            def execute(self) -> CommandResult[None]:
                return CommandResult(success=True)

        dispatcher = CommandDispatcher(event_bus)
        dispatcher.dispatch(Cmd())
        dispatcher.dispatch(Cmd())
        assert len(dispatcher._history) == 2
