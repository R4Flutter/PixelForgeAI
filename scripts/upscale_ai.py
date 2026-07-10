from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from scripts.config import ModelType, UpscaleConfig
from scripts.exceptions import UpscaleError


logger = logging.getLogger("UPSCALE_AI")

_SUPPORTED_SCALES = {2, 4, 8}


def _find_executable(cfg: UpscaleConfig) -> Path:
    exe = cfg.executable_path
    if exe.is_file():
        return exe.resolve()
    raise UpscaleError(
        "Real-ESRGAN executable not found. "
        f"Expected at: {exe}"
    )


def _validate_scale(scale: int) -> None:
    if scale not in _SUPPORTED_SCALES:
        raise UpscaleError(
            f"Unsupported scale {scale}. "
            f"Real-ESRGAN NCNN supports: {sorted(_SUPPORTED_SCALES)}"
        )


def _validate_inputs(
    input_image: Path,
    output_image: Path,
    scale: int,
    overwrite: bool,
) -> None:
    if not isinstance(scale, int) or scale < 1:
        raise UpscaleError(f"Invalid scale {scale!r}: must be a positive integer.")
    if not input_image.is_file():
        raise UpscaleError(f"Input image does not exist: {input_image}")
    if output_image.exists() and not overwrite:
        raise UpscaleError(
            f"Output file already exists and overwrite=False: {output_image}"
        )


def _validate_output(output_image: Path) -> None:
    if not output_image.is_file():
        raise UpscaleError(
            "Real-ESRGAN did not produce an output file: "
            f"{output_image}"
        )
    if output_image.stat().st_size == 0:
        raise UpscaleError(
            "Real-ESRGAN produced an empty output file: "
            f"{output_image}"
        )


def _build_command(
    executable: Path,
    input_image: Path,
    output_image: Path,
    model: ModelType,
    scale: int,
) -> list[str]:
    return [
        str(executable),
        "-i", str(input_image),
        "-o", str(output_image),
        "-s", str(scale),
        "-n", model.value,
    ]


def upscale_image(
    input_image: Path,
    output_image: Path,
    scale: int = 4,
    overwrite: bool = True,
    model: ModelType = ModelType.REAL_ESRGAN_X4PLUS,
    timeout: int = 600,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Path:
    start = time.time()
    image_name = Path(input_image).name

    try:
        input_image = Path(input_image)
        output_image = Path(output_image)
    except TypeError as e:
        raise UpscaleError(f"Invalid path argument: {e}") from e

    cfg = UpscaleConfig(
        scale=scale,
        timeout=timeout,
    )
    if model.value not in (m.value for m in ModelType):
        raise UpscaleError(f"Unknown model: {model}")

    _validate_scale(scale)
    _validate_inputs(input_image, output_image, scale, overwrite)

    if progress_callback:
        progress_callback(0, "Loading")

    executable = _find_executable(cfg)

    if progress_callback:
        progress_callback(20, "Launching Real-ESRGAN")

    output_image.parent.mkdir(parents=True, exist_ok=True)

    cmd = _build_command(executable, input_image, output_image, model, scale)

    logger.info(
        f"Starting Real-ESRGAN: {image_name} "
        f"(model={model.value}, scale={scale})"
    )

    if progress_callback:
        progress_callback(70, "AI Upscaling")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except FileNotFoundError as e:
        raise UpscaleError(
            f"Real-ESRGAN executable not found at expected path: {executable}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise UpscaleError(
            f"Real-ESRGAN timed out after {timeout}s for: {image_name}"
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        detail = f" ({stderr})" if stderr else ""
        raise UpscaleError(
            f"Real-ESRGAN failed (exit code {e.returncode}) "
            f"for {image_name}:{detail}"
        ) from e
    except OSError as e:
        raise UpscaleError(
            f"System error launching Real-ESRGAN for {image_name}: {e}"
        ) from e

    if progress_callback:
        progress_callback(90, "Verifying Output")

    _validate_output(output_image)

    elapsed = round(time.time() - start, 2)
    logger.info(
        f"Real-ESRGAN success: {image_name} "
        f"(model={model.value}, scale={scale}, "
        f"duration={elapsed}s)"
    )

    if progress_callback:
        progress_callback(100, "Done")

    return output_image


def _parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upscale images using Real-ESRGAN NCNN (offline, no PyTorch)."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Input image path",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        type=Path,
        help="Output image path",
    )
    parser.add_argument(
        "--model", "-n",
        default=ModelType.REAL_ESRGAN_X4PLUS.value,
        choices=[m.value for m in ModelType],
        help="Real-ESRGAN model name",
    )
    parser.add_argument(
        "--scale", "-s",
        type=int,
        default=4,
        choices=sorted(_SUPPORTED_SCALES),
        help="Upscale factor",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Subprocess timeout in seconds",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=True,
        help="Overwrite existing output file",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_false",
        dest="overwrite",
        help="Skip if output file exists",
    )
    return parser.parse_args()


def _main_cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        stream=sys.stdout,
    )

    args = _parse_cli()

    try:
        model = ModelType(args.model)
    except ValueError:
        print(f"Invalid model: {args.model}")
        sys.exit(1)

    try:
        upscale_image(
            input_image=args.input,
            output_image=args.output,
            scale=args.scale,
            overwrite=args.overwrite,
            model=model,
            timeout=args.timeout,
            progress_callback=lambda pct, msg: print(
                f"[{pct}%] {msg}", flush=True
            ),
        )
    except UpscaleError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main_cli()
