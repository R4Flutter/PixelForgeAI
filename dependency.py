from __future__ import annotations

from typing import Any, Optional


class Dependency:
    _instance: Optional[Dependency] = None

    def __new__(cls) -> Dependency:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._registry: dict = {}

    def register(self, name: str, instance: Any) -> None:
        self._registry[name] = instance

    def resolve(self, name: str) -> Any:
        return self._registry.get(name)

    @property
    def event_bus(self):
        return self._registry.get("event_bus")

    @property
    def dispatcher(self):
        return self._registry.get("dispatcher")

    @property
    def settings_service(self):
        return self._registry.get("settings_service")

    @property
    def pipeline_service(self):
        return self._registry.get("pipeline_service")

    @property
    def image_service(self):
        return self._registry.get("image_service")

    @property
    def export_service(self):
        return self._registry.get("export_service")

    @property
    def cache_service(self):
        return self._registry.get("cache_service")

    @property
    def thumbnail_service(self):
        return self._registry.get("thumbnail_service")

    @property
    def history_service(self):
        return self._registry.get("history_service")

    @property
    def settings_repository(self):
        return self._registry.get("settings_repository")

    @property
    def app_store(self):
        return self._registry.get("app_store")

    @property
    def processing_store(self):
        return self._registry.get("processing_store")

    @property
    def settings_store(self):
        return self._registry.get("settings_store")

    @property
    def session_store(self):
        return self._registry.get("session_store")

    @property
    def plugin_manager(self):
        return self._registry.get("plugin_manager")
