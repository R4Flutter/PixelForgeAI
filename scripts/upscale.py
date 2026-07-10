from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from scripts import upscale_ai, upscale_cv
from scripts.config import ModelType
from scripts.exceptions import UpscaleError


logger = logging.getLogger("UPSCALE")

_DEFAULT_ENGINE = "realesrgan"
_DEFAULT_FALLBACK = True
_DEFAULT_MODEL = "realesrgan-x4plus"
_DEFAULT_TIMEOUT = 600


def _read_config() -> dict:
    try:
        from scripts.pipeline import CFG as pipeline_cfg
        return pipeline_cfg
    except (ImportError, AttributeError):
        return {}


def upscale_image(
    input_image: Path,
    output_image: Path,
    scale: int = 4,
    overwrite: bool = True,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Path:
    cfg = _read_config()
    engine = cfg.get("upscale_engine", _DEFAULT_ENGINE)
    fallback = cfg.get("upscale_fallback", _DEFAULT_FALLBACK)
    model_name = cfg.get("upscale_model", _DEFAULT_MODEL)
    timeout = cfg.get("upscale_timeout", _DEFAULT_TIMEOUT)

    if engine == "realesrgan":
        try:
            model = ModelType(model_name)
        except ValueError:
            logger.warning(f"Unknown model '{model_name}', using default")
            model = ModelType.REAL_ESRGAN_X4PLUS

        try:
            return upscale_ai.upscale_image(
                input_image=input_image,
                output_image=output_image,
                scale=scale,
                overwrite=overwrite,
                model=model,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        except UpscaleError as ai_err:
            if fallback:
                logger.warning(
                    "Real-ESRGAN failed, falling back to OpenCV Lanczos: "
                    f"{ai_err}"
                )
                return upscale_cv.upscale_image_cv(
                    input_image=input_image,
                    output_image=output_image,
                    scale=scale,
                    overwrite=overwrite,
                )
            raise

    return upscale_cv.upscale_image_cv(
        input_image=input_image,
        output_image=output_image,
        scale=scale,
        overwrite=overwrite,
    )
