from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from core.constants import MAX_LOG_BLOCKS
from core.enums import LogLevel


class StructuredLogger:
    def __init__(self, name: str, level: LogLevel = LogLevel.DEBUG) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level.value)

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            ))
            self._logger.addHandler(handler)

    def debug(self, msg: str, **kwargs) -> None:
        self._logger.debug(msg, extra=kwargs)

    def info(self, msg: str, **kwargs) -> None:
        self._logger.info(msg, extra=kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        self._logger.warning(msg, extra=kwargs)

    def error(self, msg: str, **kwargs) -> None:
        self._logger.error(msg, extra=kwargs)


_loggers: dict = {}


def get_logger(name: str) -> StructuredLogger:
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]
