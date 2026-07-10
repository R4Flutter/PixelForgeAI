from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

log = get_logger(__name__)


class RemoveBgStage:
    def execute(self, image_path: str, output_dir: str, config: Any) -> Optional[str]:
        try:
            from scripts.remove_bg import remove_background

            dest = os.path.join(output_dir, f"no_bg_{Path(image_path).name}")
            remove_background(image_path, dest, overwrite=True)
            if os.path.isfile(dest):
                return dest
            return None
        except Exception as e:
            log.error(f"Remove BG failed: {e}")
            return None
