from __future__ import annotations

from pathlib import Path


class NamingRules:
    FORBIDDEN_CHARS = frozenset({'<', '>', ':', '"', '/', '\\', '|', '?', '*'})

    @staticmethod
    def sanitize_filename(name: str) -> str:
        return "".join(c if c not in NamingRules.FORBIDDEN_CHARS else "_" for c in name)

    @staticmethod
    def apply_suffix(original: str, suffix: str) -> str:
        p = Path(original)
        return f"{p.stem}{suffix}{p.suffix}"

    @staticmethod
    def max_length(name: str, limit: int = 255) -> str:
        if len(name) <= limit:
            return name
        p = Path(name)
        stem = p.stem[:limit - len(p.suffix) - 1]
        return f"{stem}{p.suffix}"
