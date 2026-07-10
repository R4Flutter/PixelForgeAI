from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Result(Generic[T, E]):
    success: bool
    value: Optional[T] = None
    error: Optional[E] = None

    def unwrap(self) -> T:
        if not self.success or self.value is None:
            raise ValueError(f"Called unwrap on failed result: {self.error}")
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value if self.success and self.value is not None else default

    def map(self, fn):
        if self.success and self.value is not None:
            return Success(fn(self.value))
        return self


def Success(value: T = None) -> Result[T, Any]:
    return Result(success=True, value=value)


def Failure(error: str = "") -> Result[Any, str]:
    return Result(success=False, error=error)
