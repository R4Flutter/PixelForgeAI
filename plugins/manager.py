from __future__ import annotations

from typing import Any, Dict, List, Optional

from plogging.logger import get_logger
from plugins.base import Plugin, PluginMeta
from plugins.registry import PluginRegistry

log = get_logger(__name__)


class PluginManager:
    def __init__(self) -> None:
        self._registry = PluginRegistry()
        self._loaded: Dict[str, Plugin] = {}

    def load(self, plugin_class: type, meta: PluginMeta) -> Optional[Plugin]:
        try:
            instance = plugin_class()
            instance.meta = meta
            instance.initialize()
            self._loaded[meta.name] = instance
            self._registry.register(meta.name, instance)
            log.info(f"Plugin loaded: {meta.name} v{meta.version}")
            return instance
        except Exception as e:
            log.error(f"Failed to load plugin {meta.name}: {e}")
            return None

    def unload(self, name: str) -> bool:
        plugin = self._loaded.pop(name, None)
        if plugin:
            try:
                plugin.shutdown()
                self._registry.unregister(name)
                log.info(f"Plugin unloaded: {name}")
                return True
            except Exception as e:
                log.error(f"Failed to unload plugin {name}: {e}")
                return False
        return False

    def get(self, name: str) -> Optional[Plugin]:
        return self._loaded.get(name)

    def all(self) -> List[Plugin]:
        return list(self._loaded.values())

    def shutdown_all(self) -> None:
        for name in list(self._loaded.keys()):
            self.unload(name)
