from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass(kw_only=True)
class Event:
    timestamp: float = field(default_factory=time.time)


Handler = Callable[..., None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[Type[Event], List[Handler]] = {}

    def on(self, event_type: Type[Event], handler: Handler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: Type[Event], handler: Handler) -> None:
        handlers = self._handlers.get(event_type, [])
        self._handlers[event_type] = [h for h in handlers if h is not handler]

    def emit(self, event: Event) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)

    def clear(self) -> None:
        self._handlers.clear()
