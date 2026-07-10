from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class HomeState:
    image_paths: List[str] = field(default_factory=list)
    selected_index: int = -1
    total_images: int = 0
    has_images: bool = False
