from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ModelType(Enum):
    REALESR_ANIMEVIDEOV3 = "realesr-animevideov3"
    REAL_ESRGAN_X4PLUS = "realesrgan-x4plus"
    REAL_ESRGAN_X4PLUS_ANIME = "realesrgan-x4plus-anime"


class UpscaleEngine(str, Enum):
    REAL_ESRGAN = "realesrgan"
    OPENCV_LANCZOS = "opencv_lanczos"


@dataclass(frozen=True)
class UpscaleConfig:
    upscale_engine: str = UpscaleEngine.REAL_ESRGAN.value
    model: ModelType = ModelType.REAL_ESRGAN_X4PLUS
    scale: int = 4
    timeout: int = 600
    fallback: bool = True
    executable_path: Path = Path("resources") / "realesrgan" / "realesrgan-ncnn-vulkan.exe"
