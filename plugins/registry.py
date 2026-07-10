from __future__ import annotations

from typing import Any, Dict, List, Optional


class PluginRegistry:
    _instance: Optional[PluginRegistry] = None

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_plugins"):
            self._plugins: Dict[str, Any] = {}

    def register(self, name: str, plugin: Any) -> None:
        self._plugins[name] = plugin

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def resolve(self, name: str) -> Any:
        return self._plugins.get(name)

    def has(self, name: str) -> bool:
        return name in self._plugins

    def all(self) -> List[Any]:
        return list(self._plugins.values())
