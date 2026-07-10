from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Repository(Protocol):
    def load(self) -> Any: ...
    def save(self, data: Any) -> None: ...


@runtime_checkable
class Service(Protocol):
    pass


@runtime_checkable
class UseCase(Protocol):
    def execute(self, **kwargs) -> Any: ...
