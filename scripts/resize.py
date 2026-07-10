"""
resize.py
----------
Production-grade image resizing module.

A single target function ``resize_image`` supports three fit modes:

  * ``width_only`` — scale so the width equals ``target_width``, aspect ratio
    preserved, height derived. (Original behaviour; ``target_height`` ignored.)
  * ``fit``        — scale preserving aspect ratio so the image fits *inside*
    a ``target_width`` x ``target_height`` box, then centre it on a
    transparent RGBA canvas of exactly that size. Padding is transparent, so
    the result is a true W x H image (what print-on-demand platforms expect).
  * ``exact``      — stretch to exactly ``target_width`` x ``target_height``
    (aspect ratio may change). Use when the source already matches the target
    aspect and you want a guaranteed pixel size.

All failure paths raise ``ResizeError`` (typed, so ``scripts.pipeline`` can
catch it). Inputs are validated; truncated/corrupt images are caught instead
of producing a half-written file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional

from PIL import Image, ImageFile
import logging
import time

# ---------------- LOGGING ---------------- #
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "resize.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
# ----------------------------------------- #

# Tolerate truncated downloads / scans instead of raising mid-resize.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Hard sanity bounds. The connector clamps to these too, but the script is
# also callable directly (CLI), so it defends itself here.
_MIN_DIM = 8
_MAX_DIM = 20000


class ResizeError(Exception):
    """Raised when image resizing fails."""


def _validate_dims(width: int, height: int) -> None:
    if not isinstance(width, int) or width < _MIN_DIM:
        raise ResizeError(
            f"Invalid width {width!r}: must be an integer >= {_MIN_DIM}."
        )
    if not isinstance(height, int) or height < 0:
        raise ResizeError(
            f"Invalid height {height!r}: must be an integer >= 0 (0 = keep aspect)."
        )
    if width > _MAX_DIM or (height > _MAX_DIM):
        raise ResizeError(
            f"Dimension out of bounds (max {_MAX_DIM}px): {width}x{height}."
        )


def _fit_inside(src_w: int, src_h: int, box_w: int, box_h: int) -> Tuple[int, int]:
    """Largest (w, h) preserving aspect ratio that fits inside the box."""
    scale = min(box_w / src_w, box_h / src_h)
    scale = min(scale, 1.0)  # never upscale inside fit — pad instead
    return max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))


def resize_image(
    input_image: Path,
    output_image: Path,
    target_width: int = 4000,
    target_height: int = 0,
    fit_mode: str = "width_only",
    overwrite: bool = True,
    resample: int = Image.LANCZOS,
    png_compression: int = 6,
) -> Path:
    """
    Resize an image to ``target_width`` (and optionally ``target_height``).

    Args:
        input_image:        Source image path.
        output_image:       Destination path (extension chooses the encoder).
        target_width:       Target width in pixels (>= 8).
        target_height:      Target height in pixels. 0 = ignore (width-only).
                            > 0 = used by ``fit`` and ``exact`` modes.
        fit_mode:           ``width_only`` | ``fit`` | ``exact``.
        overwrite:          If False and output exists, skip and return the path.
        resample:           Pillow resampling filter (default Lanczos).
        png_compression:    PNG ``compress_level`` (0-9) when the output is PNG.

    Returns:
        The output Path on success.

    Raises:
        ResizeError: on any failure — missing input, corrupt decode, write
                     error, or invalid parameters. Never a bare OSError.
    """
    start = time.time()

    try:
        input_image = Path(input_image)
        output_image = Path(output_image)
    except TypeError as e:
        raise ResizeError(f"Invalid path argument: {e}") from e

    if fit_mode not in ("width_only", "fit", "exact"):
        raise ResizeError(f"Unknown fit_mode {fit_mode!r}")

    _validate_dims(target_width, target_height)
    if fit_mode in ("fit", "exact") and (target_height < _MIN_DIM):
        raise ResizeError(
            f"fit/exact modes need a target_height >= {_MIN_DIM}, got {target_height}."
        )

    if not input_image.exists():
        raise ResizeError(f"Input image not found: {input_image}")

    if output_image.exists() and not overwrite:
        logger.info(f"Skipping resize (exists): {output_image.name}")
        return output_image

    output_image.parent.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(input_image) as img:
            img.load()  # force full decode so truncated images fail here, not later
            src_w, src_h = img.size
            if src_w < 1 or src_h < 1:
                raise ResizeError(f"Source has invalid dimensions: {img.size}")

            # Keep RGBA so transparency survives padding / save.
            rgba = img.convert("RGBA")

            ext = output_image.suffix.lower()
            save_kwargs = _save_kwargs(ext, png_compression)

            if fit_mode == "width_only":
                out_img = _scale_to_width(rgba, target_width, resample)
            elif fit_mode == "fit":
                out_img = _fit_pad(rgba, target_width, target_height, resample)
            else:  # exact
                out_img = rgba.resize((target_width, target_height), resample)

            # JPG/WebP cannot carry an alpha channel in RGBA mode — the connector
            # handles the final PNG->JPG/WebP packaging, but if someone calls
            # this with a .jpg destination directly, flatten onto white.
            if out_img.mode == "RGBA" and ext in (".jpg", ".jpeg"):
                out_img = _flatten_to_white(out_img)

            logger.info(
                f"Resizing: {input_image.name} ({src_w}x{src_h}) "
                f"-> {out_img.size[0]}x{out_img.size[1]} [{fit_mode}]"
            )

            out_img.save(output_image, **save_kwargs)

        elapsed = round(time.time() - start, 2)
        logger.info(
            f"Resized successfully -> {output_image.name} "
            f"({out_img.size[0]}x{out_img.size[1]}, {elapsed}s)"
        )
        return output_image

    except ResizeError:
        raise
    except Exception as e:
        logger.error(f"Resize failed: {e}", exc_info=True)
        # A half-written destination is worse than none — remove it so a later
        # retry isn't fooled into skipping.
        try:
            if output_image.exists():
                output_image.unlink()
        except OSError:
            pass
        raise ResizeError(str(e)) from e


# --------------------------------------------------------------------------- #
# Internal transforms
# --------------------------------------------------------------------------- #
def _scale_to_width(img: Image.Image, target_width: int, resample: int) -> Image.Image:
    if img.width == target_width:
        return img
    scale = target_width / img.width
    new_h = max(1, int(round(img.height * scale)))
    return img.resize((target_width, new_h), resample=resample)


def _fit_pad(img: Image.Image, box_w: int, box_h: int, resample: int) -> Image.Image:
    """Scale preserving aspect to fit inside (box_w, box_h), centre on transparent canvas."""
    if img.width > box_w or img.height > box_h:
        new_w, new_h = _fit_inside(img.width, img.height, box_w, box_h)
        img = img.resize((new_w, new_h), resample=resample)
    # else: source already smaller than the box — keep native size, centre on padding.
    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    off_x = (box_w - img.width) // 2
    off_y = (box_h - img.height) // 2
    canvas.alpha_composite(img, (off_x, off_y))
    return canvas


def _flatten_to_white(img: Image.Image) -> Image.Image:
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[-1])
    return bg


def _save_kwargs(ext: str, png_compression: int) -> dict:
    if ext == ".png":
        cl = max(0, min(9, int(png_compression)))
        return {"format": "PNG", "compress_level": cl}
    if ext in (".jpg", ".jpeg"):
        return {"format": "JPEG", "quality": 95, "optimize": True}
    if ext == ".webp":
        return {"format": "WEBP", "quality": 90, "method": 6}
    # Let Pillow infer from the extension.
    return {}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Resize images (width / fit-box / exact).")
    parser.add_argument("--input", required=True, help="Input image or folder")
    parser.add_argument("--output", required=True, help="Output folder")
    parser.add_argument("--width", type=int, default=4000, help="Target width (default 4000)")
    parser.add_argument("--height", type=int, default=0,
                        help="Target height (0 = width-only; >0 used by fit/exact)")
    parser.add_argument("--mode", default="width_only",
                        choices=["width_only", "fit", "exact"],
                        help="width_only | fit | exact")
    parser.add_argument("--png", type=int, default=6, help="PNG compress_level 0-9")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    def _run_one(src: Path, dst: Path) -> None:
        try:
            resize_image(src, dst, target_width=args.width,
                         target_height=args.height, fit_mode=args.mode,
                         png_compression=args.png)
        except ResizeError as e:
            print(f"Failed: {src.name} -> {e}")

    if input_path.is_file():
        _run_one(input_path, output_dir / input_path.name)
    elif input_path.is_dir():
        output_dir.mkdir(parents=True, exist_ok=True)
        for img in input_path.iterdir():
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                _run_one(img, output_dir / f"{img.stem}.png")
    else:
        print("Invalid input path.")
