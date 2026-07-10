from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar

from events.base import Event, EventBus
from plogging.logger import get_logger

log = get_logger(__name__)

T = TypeVar("T")


@dataclass
class CommandResult(Generic[T]):
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Command(ABC, Generic[T]):
    @abstractmethod
    def execute(self) -> CommandResult[T]:
        pass


class CommandDispatcher:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._history: List[Command] = []
        self._max_history = 50

    def dispatch(self, command: Command) -> CommandResult:
        try:
            result = command.execute()
            self._history.append(command)
            if len(self._history) > self._max_history:
                self._history.pop(0)
            return result
        except Exception as e:
            log.error(f"Command {type(command).__name__} failed: {e}")
            return CommandResult(success=False, error=str(e))
