"""
state.py
--------
Application path resolution + settings persistence.

Keeps user-adjustable settings in a JSON file under the OS-appropriate
config directory. The backend AI scripts are not touched; this only manages
GUI-facing preferences.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from backend.job import Settings


class AppPaths:
    """Centralized, platform-aware filesystem locations."""

    APP_NAME = "PixelForgeAI"

    def __init__(self) -> None:
        self.root: Path = Path(__file__).resolve().parent.parent
        self.assets: Path = self.root / "assets"
        self.themes: Path = self.root / "themes"
        self.icons: Path = self.assets / "icons"
        self.config_dir: Path = self._config_dir()
        self.settings_file: Path = self.config_dir / "settings.json"
        # Activation record (Pro). The trial is tracked separately so a customer
        # can uninstall/reinstall without dragging a half-used trial forward.
        self.license_file: Path = self.config_dir / "license.json"
        # Trial anchor + a hidden witness copy. The witness lives under cache/
        # with a neutral name so casually deleting the obvious license files
        # does not reset the trial (deleting only the anchor is detected as
        # tampering because the witness still remembers the start time).
        self.trial_lock: Path = self.config_dir / "trial.lock"
        self.witness_dir: Path = self.config_dir / "cache"
        self.trial_witness: Path = self.witness_dir / "session.dat"
        self.work_dir: Path = self.config_dir / "work"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.witness_dir.mkdir(parents=True, exist_ok=True)

    def _config_dir(self) -> Path:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = str(Path.home() / "Library" / "Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(base) / self.APP_NAME

    def theme_file(self, name: str) -> Path:
        return self.themes / f"{name}.qss"

    def asset(self, name: str) -> Path:
        return self.assets / name


_paths: AppPaths | None = None


def paths() -> AppPaths:
    global _paths
    if _paths is None:
        _paths = AppPaths()
    return _paths


def load_settings() -> Settings:
    """Load persisted settings, falling back to defaults on any failure."""
    try:
        data = json.loads(paths().settings_file.read_text(encoding="utf-8"))
        return Settings.from_dict(data)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return Settings()


def save_settings(settings: Settings) -> None:
    """Persist settings atomically. Never raises to the caller."""
    try:
        p = paths().settings_file
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass
