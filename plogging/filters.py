from __future__ import annotations

import logging
from typing import Set


class PipelineFilter(logging.Filter):
    def __init__(self, allowed_names: Set[str] | None = None) -> None:
        super().__init__()
        self._allowed = allowed_names

    def filter(self, record: logging.LogRecord) -> bool:
        if self._allowed is None:
            return True
        return any(name in record.name for name in self._allowed)

    @classmethod
    def ai_only(cls) -> PipelineFilter:
        return cls({"PIPELINE", "UPSCALE", "REMOVE_BG", "scripts."})

    @classmethod
    def app_only(cls) -> PipelineFilter:
        return cls({"pipeline", "services", "core", "features"})
