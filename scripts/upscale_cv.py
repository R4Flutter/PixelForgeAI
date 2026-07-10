from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from scripts.exceptions import UpscaleError


logger = logging.getLogger("UPSCALE_CV")

_MAX_OUTPUT_PIXELS = 60_000_000


def _validate_scale(scale: int) -> None:
    if not isinstance(scale, int) or scale < 1:
        raise UpscaleError(f"Invalid scale {scale!r}: must be an integer >= 1.")


def _imread_unicode(path: Path) -> np.ndarray:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError as e:
        raise UpscaleError(f"Could not read file bytes: {path.name} ({e})") from e
    if data.size == 0:
        raise UpscaleError(f"Input image is empty: {path.name}")
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise UpscaleError(f"OpenCV failed to decode image: {path.name}")
    return img


def _imwrite_unicode(path: Path, img: np.ndarray) -> None:
    ext = path.suffix.lower()
    try:
        ok, buf = cv2.imencode(ext, img)
    except cv2.error as e:
        raise UpscaleError(f"Encode failed ({ext}): {e}") from e
    if not ok or buf is None:
        raise UpscaleError(f"Encode returned no data for {path.name}")
    try:
        buf.tofile(str(path))
    except OSError as e:
        raise UpscaleError(f"Write failed ({path.name}): {e}") from e
    if not path.exists() or path.stat().st_size == 0:
        raise UpscaleError(f"Output file missing or empty after write: {path.name}")


def upscale_image_cv(
    input_image: Path,
    output_image: Path,
    scale: int = 4,
    overwrite: bool = True,
) -> Path:
    start = time.time()

    try:
        input_image = Path(input_image)
        output_image = Path(output_image)
    except TypeError as e:
        raise UpscaleError(f"Invalid path argument: {e}") from e

    _validate_scale(scale)

    if not input_image.exists():
        raise UpscaleError(f"Input image not found: {input_image}")

    if output_image.exists() and not overwrite:
        return output_image

    try:
        img = _imread_unicode(input_image)
        h, w = img.shape[:2]
        if w < 1 or h < 1:
            raise UpscaleError(f"Invalid source dimensions: {img.shape}")

        new_w = w * scale
        new_h = h * scale
        if new_w * new_h > _MAX_OUTPUT_PIXELS:
            raise UpscaleError(
                f"Upscaled size {new_w}x{new_h} exceeds the "
                f"{_MAX_OUTPUT_PIXELS:,}-pixel safety limit. "
                "Use a smaller scale or a smaller source."
            )

        upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        output_image.parent.mkdir(parents=True, exist_ok=True)
        _imwrite_unicode(output_image, upscaled)

    except UpscaleError:
        try:
            if output_image.exists():
                output_image.unlink()
        except OSError:
            pass
        raise
    except (MemoryError, cv2.error) as e:
        raise UpscaleError(
            f"Out of memory / OpenCV error upscaling {input_image.name}: {e}"
        ) from e
    except Exception as e:
        raise UpscaleError(f"Unexpected error upscaling {input_image.name}: {e}") from e

    logger.info(
        f"Upscaled: {input_image.name} "
        f"({w}x{h} -> {new_w}x{new_h}, "
        f"{round(time.time() - start, 2)}s, "
        f"{img.dtype}/{img.shape[2] if img.ndim == 3 else 1}ch)"
    )
    return output_image
