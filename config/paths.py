from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PathConfig:
    root: str = ""
    assets_dir: str = "assets"
    themes_dir: str = "themes"
    config_dir: str = ""
    output_dir: str = "output"
    work_dir: str = "work"
    cache_dir: str = ""
    models_dir: str = "models"

    def resolve(self, *parts: str) -> str:
        base = Path(self.root) if self.root else Path.cwd()
        return str(base.joinpath(*parts).resolve())

    def theme_file(self, name: str) -> str:
        return self.resolve(self.themes_dir, f"{name}.qss")
