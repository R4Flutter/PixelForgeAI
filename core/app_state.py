from __future__ import annotations

from typing import Any, Dict, Optional


class AppState:
    _instance: Optional[AppState] = None

    def __new__(cls) -> AppState:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._store: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def has(self, key: str) -> bool:
        return key in self._store

    def remove(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
