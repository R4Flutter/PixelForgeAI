from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.result import Result, Success, Failure
from plogging.logger import get_logger

log = get_logger(__name__)

try:
    import cv2
    import numpy as np

    _CV_AVAILABLE = True
except ImportError:
    _CV_AVAILABLE = False


class RealESRGANUpscaler:
    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path
        self._model = None

    def upscale(self, input_path: str, output_path: str, scale: float = 2.0) -> Result[str, str]:
        if not _CV_AVAILABLE:
            return Failure("OpenCV is not available")

        try:
            img = cv2.imread(input_path)
            if img is None:
                return Failure(f"Could not read image: {input_path}")

            w = int(img.shape[1] * scale)
            h = int(img.shape[0] * scale)
            upscaled = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(output_path, upscaled)

            log.info(f"Upscaled {input_path} -> {output_path} ({scale}x)")
            return Success(output_path)
        except Exception as e:
            log.error(f"Upscaling failed for {input_path}: {e}")
            return Failure(str(e))

    def is_available(self) -> bool:
        return _CV_AVAILABLE
