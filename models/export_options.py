from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.enums import OutputFormat, MetadataPolicy


@dataclass
class ExportOptions:
    output_format: OutputFormat = OutputFormat.PNG
    quality: int = 95
    png_compression: int = 6
    metadata: MetadataPolicy = MetadataPolicy.STRIP
    jpg_background: str = "#FFFFFF"
    overwrite: bool = True
    suffix: str = ""
