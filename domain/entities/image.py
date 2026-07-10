from __future__ import annotations

from dataclasses import dataclass
from enum import auto
from typing import Optional, Tuple

from common.enums import StringEnum


class ImageKind(StringEnum):
    PHOTO = "photo"
    VECTOR = "vector"
    DESIGN = "design"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Image:
    path: str
    file_name: str
    file_size: int
    width: int = 0
    height: int = 0
    kind: ImageKind = ImageKind.UNKNOWN

    @property
    def extension(self) -> str:
        import os
        return os.path.splitext(self.file_name)[1].lower()

    @property
    def is_supported(self) -> bool:
        return self.extension in Image.SUPPORTED_EXTENSIONS

    SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"})


@dataclass(frozen=True)
class OutputImage:
    source: Image
    output_path: str
    succeeded: bool
    error: Optional[str] = None
    duration: float = 0.0
    output_format: Optional[str] = None
    output_size: Optional[Tuple[int, int]] = None
    file_size: int = 0
