from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Action:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


Reducer = Callable[[T, Action], T]


class Store(Generic[T]):
    def __init__(self, initial: T, reducer: Reducer[T]) -> None:
        self._state: T = deepcopy(initial)
        self._reducer = reducer
        self._listeners: List[Callable[[T], None]] = []

    @property
    def state(self) -> T:
        return deepcopy(self._state)

    def dispatch(self, action: Action) -> None:
        self._state = self._reducer(self._state, action)
        for listener in self._listeners:
            listener(self._state)

    def subscribe(self, listener: Callable[[T], None]) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[T], None]) -> None:
        self._listeners.remove(listener)
