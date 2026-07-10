from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from common.result import Failure, Result, Success
from domain.entities.image import Image, ImageKind


class ValidationService:
    @staticmethod
    def validate_image(path: str) -> Result[Image, str]:
        p = Path(path)
        if not p.exists():
            return Failure(f"File not found: {path}")
        if not p.is_file():
            return Failure(f"Not a file: {path}")
        ext = p.suffix.lower()
        if ext not in Image.SUPPORTED_EXTENSIONS:
            return Failure(f"Unsupported format: {ext}")

        kind = ValidationService._classify(path)
        img = Image(
            path=str(p),
            file_name=p.name,
            file_size=p.stat().st_size,
            kind=kind,
        )
        return Success(img)

    @staticmethod
    def filter_valid(paths: List[str]) -> List[Image]:
        valid = []
        for p in paths:
            result = ValidationService.validate_image(p)
            if result.success and result.value:
                valid.append(result.value)
        return valid

    @staticmethod
    def _classify(path: str) -> ImageKind:
        lower = path.lower()
        if any(x in lower for x in [".jpg", ".jpeg"]):
            return ImageKind.PHOTO
        if ".png" in lower:
            if "icon" in lower or "logo" in lower:
                return ImageKind.VECTOR
            return ImageKind.DESIGN
        return ImageKind.UNKNOWN
