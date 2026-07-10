from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from common.result import Result, Success

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


class UseCase(ABC, Generic[TIn, TOut]):
    @abstractmethod
    def execute(self, request: TIn) -> Result[TOut, str]:
        pass
