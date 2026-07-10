from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional


class DiskCache:
    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self._dir = Path(cache_dir or Path.home() / ".cache" / "PixelForgeAI")
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, name: str) -> str:
        return hashlib.md5(name.encode()).hexdigest()

    def get(self, key: str, suffix: str = ".cache") -> Optional[str]:
        path = self._dir / f"{self._key(key)}{suffix}"
        return str(path) if path.exists() else None

    def put(self, key: str, data: bytes, suffix: str = ".cache") -> str:
        path = self._dir / f"{self._key(key)}{suffix}"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(self._dir))
        tmp.write(data)
        tmp.close()
        os.replace(tmp.name, str(path))
        return str(path)

    def clear(self) -> int:
        count = 0
        for f in self._dir.iterdir():
            f.unlink(missing_ok=True)
            count += 1
        return count
