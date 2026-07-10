from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from application.interfaces.repositories import SettingsRepositoryProtocol
from common.result import Result, Success, Failure
from plogging.logger import get_logger

log = get_logger(__name__)

_SETTINGS_PATH = Path("config/settings.json")


class SettingsRepository(SettingsRepositoryProtocol):
    def __init__(self, path: Optional[str] = None) -> None:
        self._path = Path(path) if path else _SETTINGS_PATH

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with open(str(self._path), "r") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Failed to load settings: {e}")
            return {}

    def save(self, settings: Dict[str, Any]) -> Result[None]:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(self._path), "w") as f:
                json.dump(settings, f, indent=2)
            return Success(None)
        except Exception as e:
            log.error(f"Failed to save settings: {e}")
            return Failure(e)
