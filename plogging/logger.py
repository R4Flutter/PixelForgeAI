from __future__ import annotations

import logging as _logging
import sys
from typing import Any, Dict, Optional

from plogging.formatter import PipelineFormatter


class PipelineLogger:
    def __init__(self, name: str, level: str = "DEBUG") -> None:
        self._logger = _logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        handler = _logging.StreamHandler(sys.stdout)
        handler.setFormatter(PipelineFormatter())
        self._logger.addHandler(handler)

    def debug(self, msg: str, **extra: Any) -> None:
        self._logger.debug(msg, extra={"extra": extra} if extra else None)

    def info(self, msg: str, **extra: Any) -> None:
        self._logger.info(msg, extra={"extra": extra} if extra else None)

    def warning(self, msg: str, **extra: Any) -> None:
        self._logger.warning(msg, extra={"extra": extra} if extra else None)

    def error(self, msg: str, **extra: Any) -> None:
        self._logger.error(msg, extra={"extra": extra} if extra else None)

    @property
    def native(self) -> _logging.Logger:
        return self._logger


_registry: Dict[str, PipelineLogger] = {}


def get_logger(name: str) -> PipelineLogger:
    if name not in _registry:
        _registry[name] = PipelineLogger(name)
    return _registry[name]
