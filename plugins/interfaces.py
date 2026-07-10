from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class PipelinePlugin(ABC):
    @abstractmethod
    def pre_process(self, image_path: str, settings: Any) -> str:
        return image_path

    @abstractmethod
    def post_process(self, image_path: str, output_path: str, settings: Any) -> str:
        return output_path


class ExportPlugin(ABC):
    @abstractmethod
    def on_export(self, source: str, dest: str, options: Any) -> Optional[str]:
        return None


class ImagePlugin(ABC):
    @abstractmethod
    def on_image_added(self, path: str) -> None:
        pass

    @abstractmethod
    def on_image_removed(self, path: str) -> None:
        pass


class SettingsPlugin(ABC):
    @abstractmethod
    def on_settings_changed(self, key: str, value: Any) -> None:
        pass
