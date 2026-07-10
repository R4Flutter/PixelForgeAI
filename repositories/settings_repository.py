from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from models.settings_model import SettingsModel

log = get_logger(__name__)


class SettingsRepository:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self._file_path = file_path or self._default_path()

    def _default_path(self) -> str:
        config_dir = Path.home() / ".config" / "PixelForgeAI"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "settings.json")

    def load(self) -> SettingsModel:
        path = Path(self._file_path)
        if not path.exists():
            log.info("No settings file found, using defaults")
            return SettingsModel()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SettingsModel.from_dict(data)
        except Exception as e:
            log.warning(f"Failed to load settings: {e}")
            return SettingsModel()

    def save(self, settings: SettingsModel) -> None:
        try:
            data = settings.to_dict()
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".json",
                dir=os.path.dirname(self._file_path),
                encoding="utf-8",
            )
            json.dump(data, tmp, indent=2, default=str)
            tmp.close()
            os.replace(tmp.name, self._file_path)
            log.info("Settings saved")
        except Exception as e:
            log.error(f"Failed to save settings: {e}")
