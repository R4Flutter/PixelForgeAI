"""
updater.py
----------
Placeholder auto-update architecture for PixelForgeAI.

This owns the single ``APP_VERSION`` constant used across the UI and exposes an
``UpdateChecker`` that, in production, would query an HTTPS release endpoint and
compare against ``APP_VERSION``. The placeholder is *network-aware but
fail-safe*: if no endpoint is configured (the default) it short-circuits to an
"up to date" result so the app never blocks on missing networking. Replace
``RELEASE_FEED_URL`` with the real URL when a release feed exists.

Nothing here touches the AI backend.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

# Bump in lockstep with packaging/installer.iss and the PyInstaller spec.
APP_NAME = "PixelForgeAI"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "PixelForgeAI"
APP_SUPPORT_EMAIL = "support@pixelforgeai.local"
APP_WEBSITE = "https://pixelforgeai.local"

# Set to a real JSON release-feed URL to enable live update checks. Empty == off.
RELEASE_FEED_URL = ""


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    current_version: str
    available: bool
    notes: str = ""
    download_url: str = ""

    @property
    def up_to_date(self) -> bool:
        return not self.available


class UpdateChecker:
    """Compares the installed version against a release feed.

    The placeholder never raises: any failure (no URL, network error, bad JSON,
    parse mismatch) collapses to a safe "up to date" result so callers can wire
    it straight into a UI label without try/except noise.
    """

    TIMEOUT_SECONDS = 4.0

    def check(self) -> UpdateInfo:
        if not RELEASE_FEED_URL:
            return UpdateInfo(APP_VERSION, APP_VERSION, available=False)
        try:
            req = urllib.request.Request(
                RELEASE_FEED_URL, headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_SECONDS) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return UpdateInfo(APP_VERSION, APP_VERSION, available=False)

        latest = str(data.get("version", "")).strip()
        notes = str(data.get("notes", "")).strip()
        url = str(data.get("download_url", "")).strip()
        available = bool(latest) and _parse_version(latest) > _parse_version(APP_VERSION)
        return UpdateInfo(
            latest_version=latest or APP_VERSION,
            current_version=APP_VERSION,
            available=available,
            notes=notes,
            download_url=url,
        )


def _parse_version(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in v.split("."):
        n = ""
        for ch in chunk:
            if ch.isdigit():
                n += ch
            else:
                break
        parts.append(int(n) if n else 0)
    return tuple(parts)
