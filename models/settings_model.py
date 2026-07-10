from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

from core.enums import (
    OutputFormat, QualityPreset, UpscaleMode, BackgroundMode,
    MetadataPolicy, ConflictPolicy, FitMode, DeviceMode,
)


@dataclass
class SettingsModel:
    output_folder: str = "output/final"
    output_format: OutputFormat = OutputFormat.PNG
    output_width: int = 4000
    output_height: int = 4000
    fit_mode: FitMode = FitMode.FIT
    quality_preset: QualityPreset = QualityPreset.ULTRA
    png_compression: int = 6
    jpg_quality: int = 95
    webp_quality: int = 90
    jpg_background: str = "#FFFFFF"
    upscale_mode: UpscaleMode = UpscaleMode.AUTO
    background_mode: BackgroundMode = BackgroundMode.TRANSPARENT
    background_color: str = "#FFFFFF"
    metadata_policy: MetadataPolicy = MetadataPolicy.STRIP
    conflict_policy: ConflictPolicy = ConflictPolicy.OVERWRITE
    device: DeviceMode = DeviceMode.GPU
    batch: bool = False
    overwrite: bool = True
    naming_keep_original: bool = True
    naming_suffix: str = "_processed"
    open_output_folder: bool = True
    theme: str = "dark"
    accent: str = "#7C5CFF"

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        for key, val in result.items():
            if isinstance(val, Enum):
                result[key] = val.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SettingsModel:
        field_map = {
            "output_format": OutputFormat,
            "quality_preset": QualityPreset,
            "upscale_mode": UpscaleMode,
            "background_mode": BackgroundMode,
            "metadata_policy": MetadataPolicy,
            "conflict_policy": ConflictPolicy,
            "fit_mode": FitMode,
            "device": DeviceMode,
        }
        kwargs = {}
        for key, enum_cls in field_map.items():
            val = data.get(key)
            if val is not None:
                try:
                    kwargs[key] = enum_cls(val)
                except ValueError:
                    pass

        for key in cls.__dataclass_fields__:
            if key not in kwargs and key in data:
                kwargs[key] = data[key]

        return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})
