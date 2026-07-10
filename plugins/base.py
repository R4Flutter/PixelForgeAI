from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PluginMeta:
    name: str
    version: str
    author: str = ""
    description: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)


class Plugin(ABC):
    meta: PluginMeta

    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass

    def on_activate(self) -> None:
        pass

    def on_deactivate(self) -> None:
        pass
