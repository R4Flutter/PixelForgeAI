from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

log = get_logger(__name__)


class ResizeStage:
    def execute(self, image_path: str, output_dir: str, config: Any) -> Optional[str]:
        try:
            from scripts.resize import resize_image

            width = getattr(config, "output_width", 4000)
            height = getattr(config, "output_height", 4000)
            dest = os.path.join(output_dir, f"final_{Path(image_path).name}")
            resize_image(image_path, dest, width, height)
            if os.path.isfile(dest):
                return dest
            return None
        except Exception as e:
            log.error(f"Resize failed: {e}")
            return None
