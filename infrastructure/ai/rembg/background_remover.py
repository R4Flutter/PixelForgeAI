from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.result import Result, Success, Failure
from plogging.logger import get_logger

log = get_logger(__name__)

try:
    from rembg import remove as _rembg_remove
    from PIL import Image as _PILImage

    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False


class BackgroundRemover:
    def remove(self, input_path: str, output_path: str, post_process: bool = False) -> Result[str, str]:
        if not _REMBG_AVAILABLE:
            return Failure("rembg is not installed")

        try:
            with open(input_path, "rb") as f:
                input_data = f.read()

            result_data = _rembg_remove(input_data, post_process=post_process)

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(result_data)

            log.info(f"Background removed: {input_path} -> {output_path}")
            return Success(output_path)
        except Exception as e:
            log.error(f"Background removal failed for {input_path}: {e}")
            return Failure(str(e))

    def is_available(self) -> bool:
        return _REMBG_AVAILABLE
