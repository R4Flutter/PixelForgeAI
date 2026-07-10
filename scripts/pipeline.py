"""
pipeline.py
-----------
ENTERPRISE IMAGE PROCESSING PIPELINE
Production-ready • Deterministic • Windows-safe
"""

from __future__ import annotations

from pathlib import Path
import logging
import sys

import cv2
import numpy as np

from scripts.resize import resize_image, ResizeError
from scripts.upscale import upscale_image, UpscaleError
from scripts.remove_bg import remove_background, BackgroundRemovalError


# ==============================================================================
# LOGGING
# ==============================================================================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("PIPELINE")

# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class PipelineError(RuntimeError):
    """Raised when the pipeline fails"""

# ==============================================================================
# STATIC CONFIG (LOCKED)
# ==============================================================================

CFG = {
    "input_dir": Path("input/original"),

    "output_resized": Path("output/resized"),
    "output_no_bg": Path("output/no_bg"),
    "output_upscaled": Path("output/upscaled"),
    "output_final": Path("output/final"),

    "resize_size": 1200,     # normalize width (step 1)
    "final_size": 4000,      # final print width
    "final_height": 0,       # 0 = width-only (keep aspect); >0 = box/exact height
    "fit_mode": "width_only",  # width_only | fit | exact (final step only)
    "png_compression": 6,    # PNG compress_level 0-9 (final output)

    "upscale_factor": 4,
    "upscale_enabled": True,
    "upscale_engine": "realesrgan",
    "upscale_model": "realesrgan-x4plus",
    "upscale_fallback": True,
    "upscale_timeout": 600,

    "overwrite": True
}

# ==============================================================================
# UTILS
# ==============================================================================

def quick_read_gray(path: Path) -> np.ndarray:
    """Fast safe grayscale read with error handling"""
    try:
        if not path.exists():
            raise PipelineError(f"File not found: {path}")
        
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            raise PipelineError(f"File is empty: {path}")
        
        img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
        if img is None or img.size == 0:
            raise PipelineError(f"Failed to decode image: {path}")
        return img
    except Exception as e:
        raise PipelineError(f"Failed to read image: {path}") from e


def is_probably_photo(path: Path) -> bool:
    """
    FAST heuristic:
    - photos -> smooth gradients
    - line art / merch -> high contrast edges
    """
    gray = quick_read_gray(path)

    edges = cv2.Canny(gray, 80, 160)
    edge_ratio = np.count_nonzero(edges) / edges.size

    # photos usually < 6–7% edge density
    return edge_ratio < 0.07


# ==============================================================================
# CORE PIPELINE
# ==============================================================================

def process_single_image(image_path: Path) -> None:
    try:
        logger.info(f"START -> {image_path.name}")

        resized = CFG["output_resized"] / f"{image_path.stem}_r.png"
        no_bg = CFG["output_no_bg"] / f"{image_path.stem}_no_bg.png"
        upscaled = CFG["output_upscaled"] / f"{image_path.stem}_u.png"
        final = CFG["output_final"] / f"{image_path.stem}.png"

        # ----------------------------------------------------------
        # 1) Normalize input size
        # ----------------------------------------------------------
        resize_image(
            image_path,
            resized,
            target_width=CFG["resize_size"],
            overwrite=CFG["overwrite"]
        )

        # ----------------------------------------------------------
        # 2) Remove background (CRITICAL FIRST)
        # ----------------------------------------------------------
        logger.info("Removing background...")
        remove_background(
            resized,
            no_bg,
            overwrite=CFG["overwrite"]
        )

        # ----------------------------------------------------------
        # 3) Detect image type from resized (before upscale)
        # ----------------------------------------------------------
        is_photo = False
        try:
            is_photo = is_probably_photo(resized)
        except Exception as e:
            logger.warning(f"Photo detection failed -> treating as design: {e}")
            is_photo = False

        # ----------------------------------------------------------
        # 4) Upscale (ONLY for photos)
        # ----------------------------------------------------------
        if is_photo and CFG.get("upscale_enabled", True):
            logger.info("Detected PHOTO -> applying upscale")
            upscale_image(
                no_bg,
                upscaled,
                scale=CFG["upscale_factor"],
                overwrite=CFG["overwrite"]
            )
            source = upscaled
        elif is_photo:
            logger.info("Detected PHOTO - upscale disabled by settings")
            source = no_bg
        else:
            logger.info("Detected DESIGN / LINE-ART -> skipping upscale")
            source = no_bg

        # ----------------------------------------------------------
        # 5) Resize to final print size
        #    fit_mode + final_height only apply here; step 1 stays width-only.
        # ----------------------------------------------------------
        resize_image(
            source,
            final,
            target_width=CFG["final_size"],
            target_height=CFG.get("final_height", 0),
            fit_mode=CFG.get("fit_mode", "width_only"),
            overwrite=True,
            png_compression=CFG.get("png_compression", 6),
        )

        logger.info(f"SUCCESS -> {image_path.name}")

    except (ResizeError, UpscaleError, BackgroundRemovalError) as e:
        logger.error(f"FAILED -> {image_path.name} | {e}")
        raise PipelineError from e
    except Exception as e:  # last line of defense
        # Catch stray cv2.error / OOM / anything the typed catch above missed,
        # so process_single_image never leaks a non-PipelineError exception.
        logger.error(f"FAILED -> {image_path.name} | {type(e).__name__}: {e}")
        raise PipelineError(str(e)) from e


# ==============================================================================
# RUNNER
# ==============================================================================

def run_pipeline() -> None:
    input_dir = CFG["input_dir"]

    if not input_dir.exists():
        raise PipelineError(f"Input directory missing: {input_dir}")

    for key in ("output_resized", "output_no_bg", "output_upscaled", "output_final"):
        CFG[key].mkdir(parents=True, exist_ok=True)

    images = [
        img for img in input_dir.iterdir()
        if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    ]

    if not images:
        logger.info("No images found -> exiting")
        return

    logger.info(f"Found {len(images)} image(s)")

    for img in images:
        process_single_image(img)

    logger.info("PIPELINE FINISHED SUCCESSFULLY")


# ==============================================================================
# ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        logger.critical(f"PIPELINE TERMINATED: {e}")
        sys.exit(1)
