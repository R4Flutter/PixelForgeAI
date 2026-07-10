from __future__ import annotations

from enum import Enum


class StringEnum(Enum):
    def __str__(self) -> str:
        return self.value

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)
