"""
job.py
------
Immutable job request + configurable settings for a processing run.

These dataclasses are the ONLY contract between the presentation layer (gui/)
and the integration layer (backend/). Neither side reaches past it, which keeps
the AI scripts (scripts/) a true black box.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Image extensions the existing backend accepts (mirrors pipeline.run_pipeline).
IMAGE_SUFFIXES: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


class OutputFormat(str, Enum):
    PNG = "png"
    JPG = "jpg"
    WEBP = "webp"
    TIFF = "tiff"

    @property
    def suffix(self) -> str:
        return ".jpg" if self is OutputFormat.JPG else f".{self.value}"


class QualityPreset(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"
    LOSSLESS = "lossless"


class UpscaleMode(str, Enum):
    OFF = "off"
    X2 = "2x"
    X4 = "4x"
    X8 = "8x"
    AUTO = "auto"


class BackgroundMode(str, Enum):
    TRANSPARENT = "transparent"
    WHITE = "white"
    CUSTOM = "custom"


class MetadataPolicy(str, Enum):
    STRIP = "strip"
    PRESERVE = "preserve"


class ConflictPolicy(str, Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    AUTO_RENAME = "auto_rename"


class FitMode(str, Enum):
    """How the final image is fitted to the target dimensions.

    * ``WIDTH_ONLY`` — scale to ``output_width`` keeping aspect ratio
      (``output_height`` ignored). Backwards-compatible default.
    * ``FIT``       — scale preserving aspect ratio to fit *inside*
      ``output_width`` x ``output_height``, centred on a transparent canvas
      of exactly that size. Produces a true W x H image.
    * ``EXACT``      — stretch to exactly ``output_width`` x ``output_height``
      (aspect ratio may change).
    """

    WIDTH_ONLY = "width_only"
    FIT = "fit"
    EXACT = "exact"


# Product-level bounds for output dimensions (sane user range). The resize
# script defends itself with a wider absolute floor/ceiling, but the GUI and
# connector clamp to these so users can't pick absurd sizes that blow up RAM.
MIN_OUTPUT_DIM = 64
MAX_OUTPUT_DIM = 12000


class DeviceMode(str, Enum):
    """Requested compute device. Applied as best-effort environment hints only -
    the backend scripts are not modified, so this is honoured where the
    underlying libraries (rembg / onnxruntime / opencv) already read env vars."""
    GPU = "gpu"
    CPU = "cpu"


class SourceKind(str, Enum):
    FILES = "files"
    FOLDER = "folder"


@dataclass
class Settings:
    """User-tunable settings persisted across sessions.

    Only fields the backend genuinely supports take effect through the connector;
    fields the AI cannot honour are handled by a lightweight post-pass inside the
    connector (format / final resize) so the product still behaves correctly.
    """

    output_folder: str = "output"
    output_format: OutputFormat = OutputFormat.PNG
    output_width: int = 4000
    output_height: int = 0
    fit_mode: FitMode = FitMode.WIDTH_ONLY
    quality_preset: QualityPreset = QualityPreset.HIGH
    png_compression: int = 6
    upscale_mode: UpscaleMode = UpscaleMode.X4
    background_mode: BackgroundMode = BackgroundMode.TRANSPARENT
    background_color: str = "#FFFFFF"
    metadata_policy: MetadataPolicy = MetadataPolicy.STRIP
    conflict_policy: ConflictPolicy = ConflictPolicy.OVERWRITE
    device: DeviceMode = DeviceMode.GPU
    batch: bool = True
    overwrite: bool = True
    jpg_quality: int = 95
    webp_quality: int = 90
    jpg_background: str = "#FFFFFF"
    theme: str = "dark"
    accent: str = "indigo"
    remember_window: bool = True
    window_width: int = 1180
    window_height: int = 760
    naming_keep_original: bool = True
    naming_suffix: str = ""
    open_output_folder: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["output_format"] = self.output_format.value
        d["fit_mode"] = self.fit_mode.value
        d["quality_preset"] = self.quality_preset.value
        d["upscale_mode"] = self.upscale_mode.value
        d["background_mode"] = self.background_mode.value
        d["metadata_policy"] = self.metadata_policy.value
        d["conflict_policy"] = self.conflict_policy.value
        d["device"] = self.device.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        data = dict(data or {})
        try:
            data["output_format"] = OutputFormat(data.get("output_format", "png"))
        except ValueError:
            data["output_format"] = OutputFormat.PNG

        # output_width — migrate from legacy output_size if the new key is absent.
        if "output_width" not in data or data.get("output_width") in (None, "", 0):
            legacy = data.get("output_size", 4000)
            try:
                width = int(legacy)
            except (TypeError, ValueError):
                width = 4000
        else:
            try:
                width = int(data.get("output_width"))
            except (TypeError, ValueError):
                width = 4000
        data["output_width"] = max(MIN_OUTPUT_DIM, min(MAX_OUTPUT_DIM, width or 4000))

        # output_height (0 = keep aspect / width-only).
        try:
            data["output_height"] = max(
                0, min(MAX_OUTPUT_DIM, int(data.get("output_height", 0)) or 0)
            )
        except (TypeError, ValueError):
            data["output_height"] = 0

        try:
            data["fit_mode"] = FitMode(data.get("fit_mode", "width_only"))
        except ValueError:
            data["fit_mode"] = FitMode.WIDTH_ONLY

        try:
            data["quality_preset"] = QualityPreset(data.get("quality_preset", "high"))
        except ValueError:
            data["quality_preset"] = QualityPreset.HIGH

        try:
            data["png_compression"] = max(0, min(9, int(data.get("png_compression", 6))))
        except (TypeError, ValueError):
            data["png_compression"] = 6

        try:
            data["upscale_mode"] = UpscaleMode(data.get("upscale_mode", "4x"))
        except ValueError:
            data["upscale_mode"] = UpscaleMode.X4

        try:
            data["background_mode"] = BackgroundMode(
                data.get("background_mode", "transparent")
            )
        except ValueError:
            data["background_mode"] = BackgroundMode.TRANSPARENT

        data["background_color"] = _clean_hex_color(
            str(data.get("background_color") or data.get("jpg_background") or "#FFFFFF")
        )
        data["jpg_background"] = _clean_hex_color(
            str(data.get("jpg_background") or data["background_color"])
        )

        try:
            data["metadata_policy"] = MetadataPolicy(data.get("metadata_policy", "strip"))
        except ValueError:
            data["metadata_policy"] = MetadataPolicy.STRIP

        if "conflict_policy" not in data:
            data["conflict_policy"] = (
                ConflictPolicy.OVERWRITE.value
                if bool(data.get("overwrite", True))
                else ConflictPolicy.SKIP.value
            )
        try:
            data["conflict_policy"] = ConflictPolicy(data.get("conflict_policy", "overwrite"))
        except ValueError:
            data["conflict_policy"] = ConflictPolicy.OVERWRITE
        data["overwrite"] = data["conflict_policy"] is ConflictPolicy.OVERWRITE

        try:
            data["device"] = DeviceMode(data.get("device", "gpu"))
        except ValueError:
            data["device"] = DeviceMode.GPU

        for key, default, low, high in (
            ("jpg_quality", 95, 1, 100),
            ("webp_quality", 90, 1, 100),
            ("window_width", 1180, 960, 10000),
            ("window_height", 760, 640, 10000),
        ):
            try:
                data[key] = max(low, min(high, int(data.get(key, default))))
            except (TypeError, ValueError):
                data[key] = default
        data["remember_window"] = bool(data.get("remember_window", True))

        # Drop unknown keys defensively before constructing the dataclass.
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


def _clean_hex_color(value: str) -> str:
    color = (value or "#FFFFFF").strip().upper()
    if not color.startswith("#"):
        color = f"#{color}"
    if len(color) != 7:
        return "#FFFFFF"
    allowed = set("0123456789ABCDEF")
    if any(ch not in allowed for ch in color[1:]):
        return "#FFFFFF"
    return color


@dataclass(frozen=True)
class JobRequest:
    """A single, immutable processing request handed to the connector."""

    sources: tuple[str, ...]
    kind: SourceKind
    settings: Settings

    @classmethod
    def from_images(cls, images: Sequence[str], settings: Settings) -> "JobRequest":
        return cls(sources=tuple(images), kind=SourceKind.FILES, settings=settings)

    @classmethod
    def from_folder(cls, folder: str, settings: Settings) -> "JobRequest":
        return cls(sources=(folder,), kind=SourceKind.FOLDER, settings=settings)

    def resolve_image_paths(self) -> List[Path]:
        """Expand the job into concrete image paths.

        For FILES the list is used verbatim; for FOLDER it is listed (top level
        only, consistent with the behavior of the existing pipeline).
        """
        if self.kind is SourceKind.FOLDER:
            root = Path(self.sources[0])
            if not root.exists():
                return []
            return sorted(
                p for p in root.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            )
        return [Path(p) for p in self.sources if Path(p).exists()]


@dataclass(frozen=True)
class RunSummary:
    """Final report handed back to the UI when the run completes."""

    total: int
    succeeded: int
    failed: int
    elapsed_seconds: float
    failed_files: tuple[str, ...] = ()
    cancelled: bool = False

    @property
    def all_succeeded(self) -> bool:
        return self.failed == 0 and self.total > 0
