from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from domain.value_objects.export_options import ExportOptions, ExportProfile


class ExportPolicy:
    @staticmethod
    def resolve_output_path(source: str, output_dir: str, profile: ExportProfile) -> str:
        src = Path(source)
        name = src.stem + profile.suffix + src.suffix
        return str(Path(output_dir) / name)

    @staticmethod
    def should_overwrite(dest: str, policy: bool) -> bool:
        if not Path(dest).exists():
            return True
        return policy
