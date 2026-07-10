from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SettingsState:
    output_folder: str = "output/final"
    output_format: str = "png"
    quality: int = 95
    upscale_mode: str = "auto"
    device: str = "gpu"
    theme: str = "dark"
    raw: Dict[str, Any] = field(default_factory=dict)
