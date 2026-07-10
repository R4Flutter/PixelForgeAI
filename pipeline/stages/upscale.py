from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

log = get_logger(__name__)


class UpscaleStage:
    def execute(self, image_path: str, output_dir: str, config: Any) -> Optional[str]:
        try:
            from scripts.upscale import upscale_image

            factor = getattr(config, "upscale_factor", 4)
            dest = os.path.join(output_dir, f"up_{Path(image_path).name}")
            result = upscale_image(image_path, dest, factor)
            return result if result and os.path.isfile(str(result)) else None
        except Exception as e:
            log.error(f"Upscale failed: {e}")
            return None
